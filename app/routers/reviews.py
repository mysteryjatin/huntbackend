from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from app.schemas import Review, ReviewCreate, ReviewUpdate
from app.database import get_database

router = APIRouter()


@router.post("/", response_model=Review, status_code=201)
async def create_review(review: ReviewCreate):
    """Create a new review"""
    db = await get_database()
    
    # Validate property exists
    if not ObjectId.is_valid(review.property_id):
        raise HTTPException(status_code=400, detail="Invalid property ID")
    property_exists = await db.properties.find_one({"_id": ObjectId(review.property_id)})
    if not property_exists:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Validate user exists
    if not ObjectId.is_valid(review.user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")
    user_exists = await db.users.find_one({"_id": ObjectId(review.user_id)})
    if not user_exists:
        raise HTTPException(status_code=404, detail="User not found")
    
    review_dict = review.dict()
    review_dict["property_id"] = ObjectId(review_dict["property_id"])
    review_dict["user_id"] = ObjectId(review_dict["user_id"])
    review_dict["created_at"] = datetime.utcnow()
    
    result = await db.reviews.insert_one(review_dict)
    created_review = await db.reviews.find_one({"_id": result.inserted_id})
    created_review["_id"] = str(created_review["_id"])
    created_review["property_id"] = str(created_review["property_id"])
    created_review["user_id"] = str(created_review["user_id"])
    return created_review


@router.get("/", response_model=List[Review])
async def get_reviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    property_id: Optional[str] = None,
    user_id: Optional[str] = None
):
    """Get all reviews with optional filters"""
    db = await get_database()
    query = {}
    
    if property_id:
        if not ObjectId.is_valid(property_id):
            raise HTTPException(status_code=400, detail="Invalid property ID")
        query["property_id"] = ObjectId(property_id)
    
    if user_id:
        if not ObjectId.is_valid(user_id):
            raise HTTPException(status_code=400, detail="Invalid user ID")
        query["user_id"] = ObjectId(user_id)
    
    cursor = db.reviews.find(query).skip(skip).limit(limit).sort("created_at", -1)
    reviews = await cursor.to_list(length=limit)
    
    for review in reviews:
        review["_id"] = str(review["_id"])
        review["property_id"] = str(review["property_id"])
        review["user_id"] = str(review["user_id"])
    
    return reviews


@router.get("/{review_id}", response_model=Review)
async def get_review(review_id: str):
    """Get a specific review by ID"""
    db = await get_database()
    if not ObjectId.is_valid(review_id):
        raise HTTPException(status_code=400, detail="Invalid review ID")
    
    review = await db.reviews.find_one({"_id": ObjectId(review_id)})
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    review["_id"] = str(review["_id"])
    review["property_id"] = str(review["property_id"])
    review["user_id"] = str(review["user_id"])
    return review


@router.put("/{review_id}", response_model=Review)
async def update_review(review_id: str, review_update: ReviewUpdate):
    """Update a review"""
    db = await get_database()
    if not ObjectId.is_valid(review_id):
        raise HTTPException(status_code=400, detail="Invalid review ID")
    
    update_data = review_update.dict(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    result = await db.reviews.update_one(
        {"_id": ObjectId(review_id)},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Review not found")
    
    updated_review = await db.reviews.find_one({"_id": ObjectId(review_id)})
    updated_review["_id"] = str(updated_review["_id"])
    updated_review["property_id"] = str(updated_review["property_id"])
    updated_review["user_id"] = str(updated_review["user_id"])
    return updated_review


@router.delete("/{review_id}", status_code=204)
async def delete_review(review_id: str):
    """Delete a review"""
    db = await get_database()
    if not ObjectId.is_valid(review_id):
        raise HTTPException(status_code=400, detail="Invalid review ID")
    
    result = await db.reviews.delete_one({"_id": ObjectId(review_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Review not found")
    
    return None


@router.get("/property/{property_id}", response_model=List[Review])
async def get_property_reviews(property_id: str):
    """Get all reviews for a specific property"""
    db = await get_database()
    if not ObjectId.is_valid(property_id):
        raise HTTPException(status_code=400, detail="Invalid property ID")
    
    cursor = db.reviews.find({"property_id": ObjectId(property_id)}).sort("created_at", -1)
    reviews = await cursor.to_list(length=100)
    
    for review in reviews:
        review["_id"] = str(review["_id"])
        review["property_id"] = str(review["property_id"])
        review["user_id"] = str(review["user_id"])
    
    return reviews


