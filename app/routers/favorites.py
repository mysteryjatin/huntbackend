from fastapi import APIRouter, HTTPException, Query
from typing import List
from bson import ObjectId
from datetime import datetime
from app.schemas import Favorite, FavoriteCreate
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


