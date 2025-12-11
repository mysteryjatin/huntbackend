from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from app.schemas import Property, PropertyCreate, PropertyUpdate, PropertySearchParams
from app.database import get_database

router = APIRouter()


@router.post("/", response_model=Property, status_code=201)
async def create_property(property: PropertyCreate):
    """Create a new property listing"""
    db = await get_database()
    property_dict = property.dict()
    property_dict["owner_id"] = ObjectId(property_dict["owner_id"])
    property_dict["posted_at"] = datetime.utcnow()
    
    # Convert nested objects
    if "images" in property_dict:
        property_dict["images"] = [img.dict() for img in property.images]
    
    result = await db.properties.insert_one(property_dict)
    created_property = await db.properties.find_one({"_id": result.inserted_id})
    created_property["_id"] = str(created_property["_id"])
    created_property["owner_id"] = str(created_property["owner_id"])
    return created_property


@router.get("/", response_model=List[Property])
async def get_properties(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    transaction_type: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_bedrooms: Optional[int] = None,
    min_bathrooms: Optional[int] = None,
    city: Optional[str] = None,
    locality: Optional[str] = None,
    furnishing: Optional[str] = None
):
    """Get all properties with optional filters"""
    db = await get_database()
    query = {}
    
    if transaction_type:
        query["transaction_type"] = transaction_type
    if min_price is not None or max_price is not None:
        query["price"] = {}
        if min_price is not None:
            query["price"]["$gte"] = min_price
        if max_price is not None:
            query["price"]["$lte"] = max_price
    if min_bedrooms is not None:
        query["bedrooms"] = {"$gte": min_bedrooms}
    if min_bathrooms is not None:
        query["bathrooms"] = {"$gte": min_bathrooms}
    if city:
        query["location.city"] = {"$regex": city, "$options": "i"}
    if locality:
        query["location.locality"] = {"$regex": locality, "$options": "i"}
    if furnishing:
        query["furnishing"] = furnishing
    
    cursor = db.properties.find(query).skip(skip).limit(limit).sort("posted_at", -1)
    properties = await cursor.to_list(length=limit)
    
    for prop in properties:
        prop["_id"] = str(prop["_id"])
        prop["owner_id"] = str(prop["owner_id"])
    
    return properties


@router.get("/search", response_model=List[Property])
async def search_properties(
    text: Optional[str] = None,
    longitude: Optional[float] = None,
    latitude: Optional[float] = None,
    max_distance: int = Query(5000, ge=1),
    transaction_type: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_bedrooms: Optional[int] = None,
    min_bathrooms: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100)
):
    """Advanced search with text search and geo search"""
    db = await get_database()
    query = {}
    
    # Text search
    if text:
        query["$text"] = {"$search": text}
    
    # Geo search
    if longitude is not None and latitude is not None:
        query["location.geo"] = {
            "$near": {
                "$geometry": {
                    "type": "Point",
                    "coordinates": [longitude, latitude]
                },
                "$maxDistance": max_distance
            }
        }
    
    # Additional filters
    if transaction_type:
        query["transaction_type"] = transaction_type
    if min_price is not None or max_price is not None:
        query["price"] = {}
        if min_price is not None:
            query["price"]["$gte"] = min_price
        if max_price is not None:
            query["price"]["$lte"] = max_price
    if min_bedrooms is not None:
        query["bedrooms"] = {"$gte": min_bedrooms}
    if min_bathrooms is not None:
        query["bathrooms"] = {"$gte": min_bathrooms}
    
    cursor = db.properties.find(query).skip(skip).limit(limit)
    properties = await cursor.to_list(length=limit)
    
    for prop in properties:
        prop["_id"] = str(prop["_id"])
        prop["owner_id"] = str(prop["owner_id"])
    
    return properties


@router.get("/{property_id}", response_model=Property)
async def get_property(property_id: str):
    """Get a specific property by ID"""
    db = await get_database()
    if not ObjectId.is_valid(property_id):
        raise HTTPException(status_code=400, detail="Invalid property ID")
    
    property = await db.properties.find_one({"_id": ObjectId(property_id)})
    if not property:
        raise HTTPException(status_code=404, detail="Property not found")
    
    property["_id"] = str(property["_id"])
    property["owner_id"] = str(property["owner_id"])
    return property


@router.put("/{property_id}", response_model=Property)
async def update_property(property_id: str, property_update: PropertyUpdate):
    """Update a property"""
    db = await get_database()
    if not ObjectId.is_valid(property_id):
        raise HTTPException(status_code=400, detail="Invalid property ID")
    
    update_data = property_update.dict(exclude_unset=True)
    
    if "images" in update_data and update_data["images"]:
        update_data["images"] = [img.dict() if hasattr(img, 'dict') else img for img in update_data["images"]]
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    result = await db.properties.update_one(
        {"_id": ObjectId(property_id)},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Property not found")
    
    updated_property = await db.properties.find_one({"_id": ObjectId(property_id)})
    updated_property["_id"] = str(updated_property["_id"])
    updated_property["owner_id"] = str(updated_property["owner_id"])
    return updated_property


@router.delete("/{property_id}", status_code=204)
async def delete_property(property_id: str):
    """Delete a property"""
    db = await get_database()
    if not ObjectId.is_valid(property_id):
        raise HTTPException(status_code=400, detail="Invalid property ID")
    
    result = await db.properties.delete_one({"_id": ObjectId(property_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Property not found")
    
    return None


@router.get("/owner/{owner_id}", response_model=List[Property])
async def get_properties_by_owner(owner_id: str):
    """Get all properties by a specific owner"""
    db = await get_database()
    if not ObjectId.is_valid(owner_id):
        raise HTTPException(status_code=400, detail="Invalid owner ID")
    
    cursor = db.properties.find({"owner_id": ObjectId(owner_id)}).sort("posted_at", -1)
    properties = await cursor.to_list(length=100)
    
    for prop in properties:
        prop["_id"] = str(prop["_id"])
        prop["owner_id"] = str(prop["owner_id"])
    
    return properties


