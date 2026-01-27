from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
import math
from app.schemas import Property, PropertyCreate, PropertyUpdate, PropertySearchParams, PropertyListResponse
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


@router.get("/", response_model=PropertyListResponse)
async def get_properties(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    limit: int = Query(12, ge=1, le=100, description="Number of items per page"),
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type: 'sale' or 'rent'"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price filter"),
    min_bedrooms: Optional[int] = Query(None, ge=0, description="Minimum number of bedrooms"),
    min_bathrooms: Optional[int] = Query(None, ge=0, description="Minimum number of bathrooms"),
    city: Optional[str] = Query(None, description="Filter by city name"),
    locality: Optional[str] = Query(None, description="Filter by locality name"),
    furnishing: Optional[str] = Query(None, description="Filter by furnishing: 'furnished', 'semi-furnished', or 'unfurnished'"),
    property_category: Optional[str] = Query(None, description="Filter by property category: 'residential', 'commercial', or 'agricultural'"),
    property_subtype: Optional[str] = Query(None, description="Filter by property subtype"),
    facing: Optional[str] = Query(None, description="Filter by facing direction"),
    min_area: Optional[float] = Query(None, ge=0, description="Minimum area in sqft"),
    max_area: Optional[float] = Query(None, ge=0, description="Maximum area in sqft"),
    store_room: Optional[bool] = Query(None, description="Filter by store room availability"),
    servant_room: Optional[bool] = Query(None, description="Filter by servant room availability"),
    sort_by: Optional[str] = Query("posted_at", description="Sort field: 'posted_at', 'price', 'area_sqft'"),
    sort_order: Optional[str] = Query("desc", description="Sort order: 'asc' or 'desc'")
):
    """
    Get all properties with advanced filters, sorting, and pagination.
    Perfect for property listing pages with search and filter functionality.
    """
    db = await get_database()
    query = {}
    
    # Basic filters
    if transaction_type:
        query["transaction_type"] = transaction_type.lower()
    if property_category:
        query["property_category"] = property_category.lower()
    if property_subtype:
        query["property_subtype"] = property_subtype
    if furnishing:
        query["furnishing"] = furnishing.lower()
    if facing:
        query["facing"] = facing
    
    # Price filter
    if min_price is not None or max_price is not None:
        query["price"] = {}
        if min_price is not None:
            query["price"]["$gte"] = min_price
        if max_price is not None:
            query["price"]["$lte"] = max_price
    
    # Area filter
    if min_area is not None or max_area is not None:
        query["area_sqft"] = {}
        if min_area is not None:
            query["area_sqft"]["$gte"] = min_area
        if max_area is not None:
            query["area_sqft"]["$lte"] = max_area
    
    # Bedrooms and bathrooms
    if min_bedrooms is not None:
        query["bedrooms"] = {"$gte": min_bedrooms}
    if min_bathrooms is not None:
        query["bathrooms"] = {"$gte": min_bathrooms}
    
    # Location filters
    if city:
        query["location.city"] = {"$regex": city, "$options": "i"}
    if locality:
        query["location.locality"] = {"$regex": locality, "$options": "i"}
    
    # Room filters
    if store_room is not None:
        query["store_room"] = store_room
    if servant_room is not None:
        query["servant_room"] = servant_room
    
    # Calculate skip for pagination
    skip = (page - 1) * limit
    
    # Sorting
    sort_field = sort_by if sort_by in ["posted_at", "price", "area_sqft"] else "posted_at"
    sort_direction = -1 if sort_order.lower() == "desc" else 1
    sort_criteria = [(sort_field, sort_direction)]
    
    # Get total count for pagination
    total = await db.properties.count_documents(query)
    
    # Fetch properties
    cursor = db.properties.find(query).sort(sort_criteria).skip(skip).limit(limit)
    properties = await cursor.to_list(length=limit)
    
    # Convert ObjectIds to strings
    for prop in properties:
        prop["_id"] = str(prop["_id"])
        prop["owner_id"] = str(prop["owner_id"])
    
    # Calculate pagination metadata
    total_pages = math.ceil(total / limit) if total > 0 else 0
    has_next = page < total_pages
    has_prev = page > 1
    
    return PropertyListResponse(
        properties=properties,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )


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



