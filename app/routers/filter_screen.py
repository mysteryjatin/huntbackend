"""
Filter Screen API - Returns all filter options for the property search/filter UI.
Used to populate dropdowns, sliders, and checkboxes on the filter screen.
"""
import datetime
from fastapi import APIRouter
from typing import List, Optional
from app.database import get_database

router = APIRouter()


@router.get("/")
async def get_filter_screen_options(
    transaction_type: Optional[str] = None,
):
    """
    Get all filter options for the Filter Screen UI.
    Returns distinct values from properties (cities, localities, price/area ranges, etc.)
    so the frontend can populate filter dropdowns and sliders.
    Optionally pass transaction_type to get options scoped to sale or rent only.
    """
    db = await get_database()
    match_stage = {}
    if transaction_type:
        match_stage["transaction_type"] = transaction_type.lower()

    pipeline = [
        {"$match": match_stage} if match_stage else {"$match": {}},
        {"$facet": {
            # Distinct transaction types
            "transaction_types": [
                {"$group": {"_id": "$transaction_type"}},
                {"$sort": {"_id": 1}},
                {"$project": {"value": "$_id", "_id": 0}}
            ],
            # Distinct property categories
            "property_categories": [
                {"$match": {"property_category": {"$exists": True, "$ne": None, "$ne": ""}}},
                {"$group": {"_id": "$property_category"}},
                {"$sort": {"_id": 1}},
                {"$project": {"value": "$_id", "_id": 0}}
            ],
            # Distinct property subtypes
            "property_subtypes": [
                {"$match": {"property_subtype": {"$exists": True, "$ne": None, "$ne": ""}}},
                {"$group": {"_id": "$property_subtype"}},
                {"$sort": {"_id": 1}},
                {"$project": {"value": "$_id", "_id": 0}}
            ],
            # Distinct furnishing options
            "furnishing_options": [
                {"$match": {"furnishing": {"$exists": True, "$ne": None, "$ne": ""}}},
                {"$group": {"_id": "$furnishing"}},
                {"$sort": {"_id": 1}},
                {"$project": {"value": "$_id", "_id": 0}}
            ],
            # Distinct facing options
            "facing_options": [
                {"$match": {"facing": {"$exists": True, "$ne": None, "$ne": ""}}},
                {"$group": {"_id": "$facing"}},
                {"$sort": {"_id": 1}},
                {"$project": {"value": "$_id", "_id": 0}}
            ],
            # Distinct cities from location
            "cities": [
                {"$match": {"location.city": {"$exists": True, "$ne": None, "$ne": ""}}},
                {"$group": {"_id": "$location.city"}},
                {"$sort": {"_id": 1}},
                {"$project": {"value": "$_id", "_id": 0}}
            ],
            # Distinct localities (with city for grouping if needed)
            "localities": [
                {"$match": {"location.locality": {"$exists": True, "$ne": None, "$ne": ""}}},
                {"$group": {"_id": {"locality": "$location.locality", "city": "$location.city"}}},
                {"$sort": {"_id.city": 1, "_id.locality": 1}},
                {"$project": {"value": "$_id.locality", "city": "$_id.city", "_id": 0}}
            ],
            # Price range (min, max)
            "price_range": [
                {"$group": {
                    "_id": None,
                    "min": {"$min": "$price"},
                    "max": {"$max": "$price"}
                }},
                {"$project": {"_id": 0, "min": 1, "max": 1}}
            ],
            # Area range (min, max sqft)
            "area_range": [
                {"$match": {"area_sqft": {"$exists": True, "$gt": 0}}},
                {"$group": {
                    "_id": None,
                    "min": {"$min": "$area_sqft"},
                    "max": {"$max": "$area_sqft"}
                }},
                {"$project": {"_id": 0, "min": 1, "max": 1}}
            ],
            # Distinct bedrooms
            "bedrooms": [
                {"$match": {"bedrooms": {"$exists": True, "$gte": 0}}},
                {"$group": {"_id": "$bedrooms"}},
                {"$sort": {"_id": 1}},
                {"$project": {"value": "$_id", "_id": 0}}
            ],
            # Distinct bathrooms
            "bathrooms": [
                {"$match": {"bathrooms": {"$exists": True, "$gte": 0}}},
                {"$group": {"_id": "$bathrooms"}},
                {"$sort": {"_id": 1}},
                {"$project": {"value": "$_id", "_id": 0}}
            ],
            # Distinct possession status
            "possession_status": [
                {"$match": {"possession_status": {"$exists": True, "$ne": None, "$ne": ""}}},
                {"$group": {"_id": "$possession_status"}},
                {"$sort": {"_id": 1}},
                {"$project": {"value": "$_id", "_id": 0}}
            ],
            # Distinct age of construction
            "age_of_construction": [
                {"$match": {"age_of_construction": {"$exists": True, "$ne": None, "$ne": ""}}},
                {"$group": {"_id": "$age_of_construction"}},
                {"$sort": {"_id": 1}},
                {"$project": {"value": "$_id", "_id": 0}}
            ],
            # Distinct availability years (for dropdown)
            "availability_years": [
                {"$match": {"availability_year": {"$exists": True, "$ne": None}}},
                {"$group": {"_id": "$availability_year"}},
                {"$sort": {"_id": -1}},
                {"$project": {"value": "$_id", "_id": 0}}
            ],
        }}
    ]

    cursor = db.properties.aggregate(pipeline)
    result = await cursor.to_list(length=1)
    if not result:
        return _empty_filter_response()

    facet = result[0]

    def to_values(arr: list) -> List:
        return [x["value"] for x in arr if x.get("value") is not None]

    def localities_for_ui(arr: list):
        return [{"value": x.get("value"), "city": x.get("city")} for x in arr if x.get("value")]

    price_range = facet.get("price_range") or []
    area_range = facet.get("area_range") or []

    pr = price_range[0] if price_range else {"min": 0, "max": 0}
    ar = area_range[0] if area_range else {"min": 0, "max": 0}
    # Ensure valid ranges so frontend sliders never get max < min (e.g. 0–0)
    pr_min = pr.get("min") if pr.get("min") is not None else 0
    pr_max = pr.get("max") if pr.get("max") is not None else 0
    if pr_max < pr_min or (pr_min == 0 and pr_max == 0):
        pr = {"min": 0, "max": 100}  # default 0–100 Lacs for budget slider
    ar_min = ar.get("min") if ar.get("min") is not None else 0
    ar_max = ar.get("max") if ar.get("max") is not None else 0
    if ar_max < ar_min or (ar_min == 0 and ar_max == 0):
        ar = {"min": 0, "max": 5000}  # default 0–5000 sqft for area slider

    # Possession status options (full list for Filter screen UI)
    possession_status_options = [
        {"value": "under_construction", "label": "Under Construction"},
        {"value": "ready_to_move", "label": "Ready to move"},
    ]

    # Age of construction options (full list for Filter screen UI)
    age_of_construction_options = [
        {"value": "new_construction", "label": "New Construction"},
        {"value": "less_than_5_years", "label": "Less than 5 Years"},
        {"value": "5_to_10_years", "label": "5 to 10 Years"},
        {"value": "10_to_15_years", "label": "10 to 15 Years"},
        {"value": "15_to_20_years", "label": "15 to 20 Years"},
        {"value": "15_to_20_plus_years", "label": "15 to 20+ Years"},
    ]

    # Availability: months 1-12 (always), years from DB or default next 6 years
    current_year = datetime.datetime.utcnow().year
    availability_years_data = to_values(facet.get("availability_years") or [])
    availability_years = sorted(availability_years_data, reverse=True) if availability_years_data else [
        current_year + i for i in range(0, 6)
    ]
    availability_months = [
        {"value": i, "label": datetime.datetime(2000, i, 1).strftime("%B")} for i in range(1, 13)
    ]

    payload = {
        "transaction_types": to_values(facet.get("transaction_types") or []),
        "property_categories": to_values(facet.get("property_categories") or []),
        "property_subtypes": to_values(facet.get("property_subtypes") or []),
        "furnishing_options": to_values(facet.get("furnishing_options") or []),
        "facing_options": to_values(facet.get("facing_options") or []),
        "cities": to_values(facet.get("cities") or []),
        "localities": localities_for_ui(facet.get("localities") or []),
        "price_range": pr,
        "area_range": ar,
        "bedrooms": to_values(facet.get("bedrooms") or []),
        "bathrooms": to_values(facet.get("bathrooms") or []),
        "store_room_options": [True, False],
        "servant_room_options": [True, False],
        "possession_status_options": possession_status_options,
        "availability_months": availability_months,
        "availability_years": availability_years,
        "age_of_construction_options": age_of_construction_options,
    }
    # Return with success + data so frontend can use response.data or response directly
    return {"success": True, "data": payload}


def _empty_filter_response() -> dict:
    """Return empty filter options when no properties exist. Ranges use safe defaults for sliders."""
    current_year = datetime.datetime.utcnow().year
    payload = {
        "transaction_types": [],
        "property_categories": [],
        "property_subtypes": [],
        "furnishing_options": [],
        "facing_options": [],
        "cities": [],
        "localities": [],
        "price_range": {"min": 0, "max": 100},
        "area_range": {"min": 0, "max": 5000},
        "bedrooms": [],
        "bathrooms": [],
        "store_room_options": [True, False],
        "servant_room_options": [True, False],
        "possession_status_options": [
            {"value": "under_construction", "label": "Under Construction"},
            {"value": "ready_to_move", "label": "Ready to move"},
        ],
        "availability_months": [
            {"value": i, "label": datetime.datetime(2000, i, 1).strftime("%B")} for i in range(1, 13)
        ],
        "availability_years": [current_year + i for i in range(0, 6)],
        "age_of_construction_options": [
            {"value": "new_construction", "label": "New Construction"},
            {"value": "less_than_5_years", "label": "Less than 5 Years"},
            {"value": "5_to_10_years", "label": "5 to 10 Years"},
            {"value": "10_to_15_years", "label": "10 to 15 Years"},
            {"value": "15_to_20_years", "label": "15 to 20 Years"},
            {"value": "15_to_20_plus_years", "label": "15 to 20+ Years"},
        ],
    }
    return {"success": True, "data": payload}