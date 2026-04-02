"""
Home Screen API - Returns sectioned property data for the home screen.
Sections: Top Selling Projects (in city), Recommend Your Location, Property for Rent.
Each property includes id, title, location, price, price_display, image_url, etc. for cards.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from typing import Optional, List, Any
from bson import ObjectId
from app.database import get_database
from app.upload_urls import canonical_client_image_url, get_public_origin

router = APIRouter()

# Default city for "Top Selling Projects in {city}"
DEFAULT_CITY = "Chennai"
SECTION_LIMIT = 10


def _listing_tag_label(transaction_type: str, possession_status: Optional[str]) -> str:
    """
    Short label for property cards: Rent | New | Resale.
    Matches posting flow: sale + under_construction → New; sale + ready_to_move → Resale; rent → Rent.
    """
    tx = (transaction_type or "sale").strip().lower()
    if tx == "rent":
        return "Rent"
    pos = (possession_status or "").strip().lower().replace(" ", "_")
    if "under_construction" in pos:
        return "New"
    return "Resale"


def _is_new_listing(posted_at) -> bool:
    """True if listing was posted within the last 14 days (for NEW badge on rent cards)."""
    if posted_at is None:
        return False
    try:
        if not isinstance(posted_at, datetime):
            return False
        now = datetime.now(timezone.utc)
        p = posted_at
        if p.tzinfo is None:
            p = p.replace(tzinfo=timezone.utc)
        return (now - p) <= timedelta(days=14)
    except Exception:
        return False


def _furnishing_label(furnishing: Optional[str]) -> Optional[str]:
    """Short badge text for rent cards (FURNISHED, etc.)."""
    f = (furnishing or "").strip().lower()
    if f in ("furnished", "fully-furnished"):
        return "FURNISHED"
    if f == "semi-furnished":
        return "SEMI-FURNISHED"
    if f == "unfurnished":
        return "UNFURNISHED"
    return None


def _format_price_display(price: float, transaction_type: str) -> str:
    """Format price for UI: sale in Lacs (₹45L), rent as monthly (₹15,000)."""
    if transaction_type == "rent":
        if price >= 1000:
            return f"₹{int(price):,}"
        return f"₹{int(price)}"
    # Sale: show in Lacs
    lacs = price / 100_000
    if lacs >= 100:
        return f"₹{int(lacs / 100)}Cr"
    if lacs >= 1:
        return f"₹{int(lacs)}L"
    return f"₹{int(price):,}"


def _property_card_doc(prop: dict) -> dict:
    """Build a single property object for home card: id, title, location, price, price_display, image_url, tag, etc."""
    loc = prop.get("location") or {}
    locality = (loc.get("locality") or "").strip()
    city = (loc.get("city") or "").strip()
    location_str = f"{locality}, {city}" if locality and city else (locality or city or "N/A")

    transaction_type = (prop.get("transaction_type") or "sale").lower()
    possession_status = prop.get("possession_status")
    price = float(prop.get("price") or 0)
    price_display = _format_price_display(price, transaction_type)
    listing_tag = _listing_tag_label(transaction_type, possession_status)

    images = prop.get("images") or []
    first_image = None
    if images:
        first = images[0]
        url = first.get("url") if isinstance(first, dict) else str(first)
        if url:
            first_image = canonical_client_image_url(url) or url

    # For rent, optional details line e.g. "3BHK | Anna Nagar, Chennai"
    bedrooms = prop.get("bedrooms")
    details = f"{bedrooms} BHK" if bedrooms and bedrooms > 0 else None
    if transaction_type == "rent" and details:
        location_str = f"{details} | {location_str}"

    furn_label = _furnishing_label(prop.get("furnishing"))
    posted = prop.get("posted_at")
    new_badge = _is_new_listing(posted) if transaction_type == "rent" else False

    return {
        "_id": str(prop["_id"]),
        "owner_id": str(prop.get("owner_id", "")),
        "title": (prop.get("title") or "Property").strip(),
        "transaction_type": transaction_type,
        "possession_status": possession_status,
        "tag": listing_tag,
        "listing_tag": listing_tag,
        "furnishing_label": furn_label,
        "is_new_listing": new_badge,
        "price": price,
        "price_display": price_display,
        "location": location_str,
        "locality": locality,
        "city": city,
        "image_url": first_image,
        "bedrooms": bedrooms,
        "bathrooms": prop.get("bathrooms"),
        "area_sqft": prop.get("area_sqft"),
        "details": details,
        "posted_at": prop.get("posted_at").isoformat() if prop.get("posted_at") else None,
    }


@router.get("/")
async def get_home_sections(
    city: Optional[str] = Query(
        None,
        description="City for 'Top Selling Projects in {city}' (default: Chennai)",
    ),
    user_id: Optional[str] = Query(
        None,
        description="Optional: user ID to compute is_favorite per property",
    ),
    transaction_type: Optional[str] = Query(
        "all",
        description="Filter by tab: all | buy | rent | projects | residential | commercial",
    ),
    limit: int = Query(SECTION_LIMIT, ge=1, le=20, description="Max properties per section"),
):
    """
    Home Screen: Get sectioned data for Top Selling Projects, Recommend Your Location, and Property for Rent.
    transaction_type: all | buy (sale only) | rent (rent only) | projects (under_construction) | residential | commercial.
    """
    db = await get_database()
    city_filter = (city or DEFAULT_CITY).strip() or DEFAULT_CITY
    filter_type = (transaction_type or "all").strip().lower()

    # Favorite IDs for user (optional)
    favorite_ids = set()
    if user_id and user_id.strip() and ObjectId.is_valid(user_id.strip()):
        fav_cursor = db.favorites.find(
            {"user_id": ObjectId(user_id.strip())},
            projection={"property_id": 1},
        )
        for doc in await fav_cursor.to_list(length=500):
            pid = doc.get("property_id")
            if pid:
                favorite_ids.add(str(pid))

    def add_favorite(doc_list: List[dict]) -> None:
        for d in doc_list:
            d["is_favorite"] = d.get("_id") in favorite_ids

    # Extra filters for category tabs
    category_filter = {}  # e.g. {"property_category": "residential"}
    if filter_type == "residential":
        category_filter["property_category"] = {"$regex": r"^residential$", "$options": "i"}
    elif filter_type == "commercial":
        category_filter["property_category"] = {"$regex": r"^commercial$", "$options": "i"}

    # projects = under_construction only (single section)
    if filter_type == "projects":
        match = {"possession_status": {"$regex": r"under_construction", "$options": "i"}, **category_filter}
        proj_cursor = (
            db.properties.find(match)
            .sort("posted_at", -1)
            .limit(limit)
        )
        proj_props = await proj_cursor.to_list(length=limit)
        top_selling = [_property_card_doc(p) for p in proj_props]
        add_favorite(top_selling)
        return {
            "success": True,
            "data": {
                "transaction_type": filter_type,
                "top_selling_projects": {
                    "section_title": "Projects",
                    "city": city_filter,
                    "properties": top_selling,
                },
                "recommend_your_location": {
                    "section_title": "Recommend Your Location",
                    "section_subtitle": "Latest sale listings from our database — new projects and resale homes.",
                    "properties": [],
                },
                "property_for_rent": {"section_title": "Property for Rent", "properties": []},
            },
        }

    # all | buy | rent (optionally with residential/commercial when filter is residential/commercial)
    show_sale = filter_type not in ("rent",)
    show_rent = filter_type not in ("buy",)

    # For "residential" / "commercial" we show both sale and rent filtered by category
    if filter_type in ("residential", "commercial"):
        show_sale = True
        show_rent = True

    top_selling = []
    recommend = []
    for_rent = []

    if show_sale:
        top_match = {
            "transaction_type": "sale",
            "location.city": {"$regex": city_filter, "$options": "i"},
            **category_filter,
        }
        top_cursor = (
            db.properties.find(top_match)
            .sort("posted_at", -1)
            .limit(limit)
        )
        top_props = await top_cursor.to_list(length=limit)
        top_selling = [_property_card_doc(p) for p in top_props]
        add_favorite(top_selling)

        rec_match = {"transaction_type": "sale", **category_filter}
        rec_cursor = (
            db.properties.find(rec_match)
            .sort("posted_at", -1)
            .limit(limit)
        )
        rec_props = await rec_cursor.to_list(length=limit)
        recommend = [_property_card_doc(p) for p in rec_props]
        add_favorite(recommend)

    if show_rent:
        rent_match = {"transaction_type": "rent", **category_filter}
        rent_cursor = (
            db.properties.find(rent_match)
            .sort("posted_at", -1)
            .limit(limit)
        )
        rent_props = await rent_cursor.to_list(length=limit)
        for_rent = [_property_card_doc(p) for p in rent_props]
        add_favorite(for_rent)

    return {
        "success": True,
        "data": {
            "transaction_type": filter_type,
            "top_selling_projects": {
                "section_title": f"Top Selling Projects in {city_filter}",
                "city": city_filter,
                "properties": top_selling,
            },
            "recommend_your_location": {
                "section_title": "Recommend Your Location",
                "section_subtitle": "Latest sale listings from our database — new projects and resale homes.",
                "properties": recommend,
            },
            "property_for_rent": {
                "section_title": "Property for Rent",
                "properties": for_rent,
            },
        },
    }
