"""
Home Screen API - Returns sectioned property data for the home screen.
Sections: Top Selling Projects (in city), Recommend Your Location, Property for Rent.
Each property includes id, title, location, price, price_display, image_url, etc. for cards.
"""
from fastapi import APIRouter, Query
from typing import Optional, List, Any
from bson import ObjectId
from app.database import get_database

router = APIRouter()

# Default city for "Top Selling Projects in {city}"
DEFAULT_CITY = "Chennai"
SECTION_LIMIT = 10


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


def _property_card_doc(prop: dict, base_url: str = "") -> dict:
    """Build a single property object for home card: id, title, location, price, price_display, image_url, tag, etc."""
    loc = prop.get("location") or {}
    locality = (loc.get("locality") or "").strip()
    city = (loc.get("city") or "").strip()
    location_str = f"{locality}, {city}" if locality and city else (locality or city or "N/A")

    transaction_type = (prop.get("transaction_type") or "sale").lower()
    price = float(prop.get("price") or 0)
    price_display = _format_price_display(price, transaction_type)

    images = prop.get("images") or []
    first_image = None
    if images:
        first = images[0]
        url = first.get("url") if isinstance(first, dict) else str(first)
        if url and (url.startswith("http") or url.startswith("/")):
            first_image = url if url.startswith("http") else f"{base_url.rstrip('/')}{url}"

    # For rent, optional details line e.g. "3BHK | Anna Nagar, Chennai"
    bedrooms = prop.get("bedrooms")
    details = f"{bedrooms} BHK" if bedrooms and bedrooms > 0 else None
    if transaction_type == "rent" and details:
        location_str = f"{details} | {location_str}"

    return {
        "_id": str(prop["_id"]),
        "owner_id": str(prop.get("owner_id", "")),
        "title": (prop.get("title") or "Property").strip(),
        "transaction_type": transaction_type,
        "tag": "Rent" if transaction_type == "rent" else "Sell",
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
    limit: int = Query(SECTION_LIMIT, ge=1, le=20, description="Max properties per section"),
):
    """
    Home Screen: Get sectioned data for Top Selling Projects, Recommend Your Location, and Property for Rent.
    Each section has a title and list of properties with id, title, location, price, price_display, image_url, etc.
    """
    db = await get_database()
    base_url = "http://72.61.237.178:8000"  # For relative image URLs; could be from config
    city_filter = (city or DEFAULT_CITY).strip() or DEFAULT_CITY

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

    # 1) Top Selling Projects in {city} — sale, in city, recent
    top_match = {
        "transaction_type": "sale",
        "location.city": {"$regex": city_filter, "$options": "i"},
    }
    top_cursor = (
        db.properties.find(top_match)
        .sort("posted_at", -1)
        .limit(limit)
    )
    top_props = await top_cursor.to_list(length=limit)
    top_selling = [_property_card_doc(p, base_url) for p in top_props]
    add_favorite(top_selling)

    # 2) Recommend Your Location — sale, same city or no city filter, different order (e.g. by price desc or views)
    rec_match = {"transaction_type": "sale"}
    rec_cursor = (
        db.properties.find(rec_match)
        .sort("posted_at", -1)
        .limit(limit)
    )
    rec_props = await rec_cursor.to_list(length=limit)
    recommend = [_property_card_doc(p, base_url) for p in rec_props]
    add_favorite(recommend)

    # 3) Property for Rent
    rent_match = {"transaction_type": "rent"}
    rent_cursor = (
        db.properties.find(rent_match)
        .sort("posted_at", -1)
        .limit(limit)
    )
    rent_props = await rent_cursor.to_list(length=limit)
    for_rent = [_property_card_doc(p, base_url) for p in rent_props]
    add_favorite(for_rent)

    return {
        "success": True,
        "data": {
            "top_selling_projects": {
                "section_title": f"Top Selling Projects in {city_filter}",
                "city": city_filter,
                "properties": top_selling,
            },
            "recommend_your_location": {
                "section_title": "Recommend Your Location",
                "properties": recommend,
            },
            "property_for_rent": {
                "section_title": "Property for Rent",
                "properties": for_rent,
            },
        },
    }
