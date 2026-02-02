import math
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from app.schemas import Favorite, FavoriteCreate, PropertyListResponse
from app.database import get_database

router = APIRouter()


@router.post("/", response_model=Favorite, status_code=201)
async def create_favorite(favorite: FavoriteCreate):
    """Add a property to favorites"""
    db = await get_database()
    
    # Validate property exists
    if not ObjectId.is_valid(favorite.property_id):
        raise HTTPException(status_code=400, detail="Invalid property ID")
    property_exists = await db.properties.find_one({"_id": ObjectId(favorite.property_id)})
    if not property_exists:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Validate user exists
    if not ObjectId.is_valid(favorite.user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")
    user_exists = await db.users.find_one({"_id": ObjectId(favorite.user_id)})
    if not user_exists:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already favorited
    existing_favorite = await db.favorites.find_one({
        "user_id": ObjectId(favorite.user_id),
        "property_id": ObjectId(favorite.property_id)
    })
    if existing_favorite:
        raise HTTPException(status_code=400, detail="Property already in favorites")
    
    favorite_dict = favorite.dict()
    favorite_dict["property_id"] = ObjectId(favorite_dict["property_id"])
    favorite_dict["user_id"] = ObjectId(favorite_dict["user_id"])
    favorite_dict["created_at"] = datetime.utcnow()
    
    result = await db.favorites.insert_one(favorite_dict)
    created_favorite = await db.favorites.find_one({"_id": result.inserted_id})
    created_favorite["_id"] = str(created_favorite["_id"])
    created_favorite["property_id"] = str(created_favorite["property_id"])
    created_favorite["user_id"] = str(created_favorite["user_id"])
    return created_favorite


@router.get("/user/{user_id}/shortlist", response_model=PropertyListResponse)
async def get_user_shortlist(
    user_id: str,
    transaction_type: Optional[str] = Query(
        None,
        description="Filter by Rent or Buy: 'rent' or 'sale'",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(12, ge=1, le=100, description="Items per page"),
):
    """
    ShortList (Rent/Buy): Get user's shortlisted properties with full details.
    Optionally filter by transaction_type: 'rent' (Rent) or 'sale' (Buy).
    Returns paginated list of property objects for the ShortList screen.
    """
    db = await get_database()
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")

    # Get user's favorite property IDs in order (newest first)
    cursor = db.favorites.find({"user_id": ObjectId(user_id)}).sort("created_at", -1)
    favorites = await cursor.to_list(length=1000)
    property_ids = [f["property_id"] for f in favorites]

    if not property_ids:
        return PropertyListResponse(
            properties=[],
            total=0,
            page=page,
            limit=limit,
            total_pages=0,
            has_next=False,
            has_prev=False,
        )

    # Build property query: _id in list and optional transaction_type
    query = {"_id": {"$in": property_ids}}
    if transaction_type:
        query["transaction_type"] = transaction_type.lower()

    total = await db.properties.count_documents(query)
    skip = (page - 1) * limit
    cursor_props = (
        db.properties.find(query)
        .sort("posted_at", -1)
        .skip(skip)
        .limit(limit)
    )
    properties = await cursor_props.to_list(length=limit)

    # Preserve shortlist order (by favorite created_at): sort by order in property_ids
    id_order = {pid: i for i, pid in enumerate(property_ids)}
    properties.sort(key=lambda p: id_order.get(p["_id"], 999999))

    for prop in properties:
        prop["_id"] = str(prop["_id"])
        prop["owner_id"] = str(prop["owner_id"])

    total_pages = math.ceil(total / limit) if total > 0 else 0
    return PropertyListResponse(
        properties=properties,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )


@router.get("/user/{user_id}", response_model=List[Favorite])
async def get_user_favorites(user_id: str):
    """Get all favorites for a specific user"""
    db = await get_database()
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    cursor = db.favorites.find({"user_id": ObjectId(user_id)}).sort("created_at", -1)
    favorites = await cursor.to_list(length=100)
    
    for favorite in favorites:
        favorite["_id"] = str(favorite["_id"])
        favorite["property_id"] = str(favorite["property_id"])
        favorite["user_id"] = str(favorite["user_id"])
    
    return favorites


@router.get("/{favorite_id}", response_model=Favorite)
async def get_favorite(favorite_id: str):
    """Get a specific favorite by ID"""
    db = await get_database()
    if not ObjectId.is_valid(favorite_id):
        raise HTTPException(status_code=400, detail="Invalid favorite ID")
    
    favorite = await db.favorites.find_one({"_id": ObjectId(favorite_id)})
    if not favorite:
        raise HTTPException(status_code=404, detail="Favorite not found")
    
    favorite["_id"] = str(favorite["_id"])
    favorite["property_id"] = str(favorite["property_id"])
    favorite["user_id"] = str(favorite["user_id"])
    return favorite


@router.delete("/{favorite_id}", status_code=204)
async def delete_favorite(favorite_id: str):
    """Remove a property from favorites"""
    db = await get_database()
    if not ObjectId.is_valid(favorite_id):
        raise HTTPException(status_code=400, detail="Invalid favorite ID")
    
    result = await db.favorites.delete_one({"_id": ObjectId(favorite_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Favorite not found")
    
    return None


@router.delete("/user/{user_id}/property/{property_id}", status_code=204)
async def remove_favorite_by_property(user_id: str, property_id: str):
    """Remove a specific property from user's favorites"""
    db = await get_database()
    if not ObjectId.is_valid(user_id) or not ObjectId.is_valid(property_id):
        raise HTTPException(status_code=400, detail="Invalid user ID or property ID")
    
    result = await db.favorites.delete_one({
        "user_id": ObjectId(user_id),
        "property_id": ObjectId(property_id)
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Favorite not found")
    
    return None



