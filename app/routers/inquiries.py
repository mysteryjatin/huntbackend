from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from app.schemas import Inquiry, InquiryCreate, InquiryUpdate
from app.database import get_database

router = APIRouter()


@router.post("/", response_model=Inquiry, status_code=201)
async def create_inquiry(inquiry: InquiryCreate):
    """Create a new inquiry"""
    db = await get_database()
    
    # Validate property exists
    if not ObjectId.is_valid(inquiry.property_id):
        raise HTTPException(status_code=400, detail="Invalid property ID")
    property_exists = await db.properties.find_one({"_id": ObjectId(inquiry.property_id)})
    if not property_exists:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Validate user exists
    if not ObjectId.is_valid(inquiry.user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")
    user_exists = await db.users.find_one({"_id": ObjectId(inquiry.user_id)})
    if not user_exists:
        raise HTTPException(status_code=404, detail="User not found")
    
    inquiry_dict = inquiry.dict()
    inquiry_dict["property_id"] = ObjectId(inquiry_dict["property_id"])
    inquiry_dict["user_id"] = ObjectId(inquiry_dict["user_id"])
    inquiry_dict["status"] = "pending"
    inquiry_dict["created_at"] = datetime.utcnow()
    
    result = await db.inquiries.insert_one(inquiry_dict)
    created_inquiry = await db.inquiries.find_one({"_id": result.inserted_id})
    created_inquiry["_id"] = str(created_inquiry["_id"])
    created_inquiry["property_id"] = str(created_inquiry["property_id"])
    created_inquiry["user_id"] = str(created_inquiry["user_id"])
    return created_inquiry


@router.get("/", response_model=List[Inquiry])
async def get_inquiries(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    property_id: Optional[str] = None,
    user_id: Optional[str] = None,
    status: Optional[str] = None
):
    """Get all inquiries with optional filters"""
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
    
    if status:
        query["status"] = status
    
    cursor = db.inquiries.find(query).skip(skip).limit(limit).sort("created_at", -1)
    inquiries = await cursor.to_list(length=limit)
    
    for inquiry in inquiries:
        inquiry["_id"] = str(inquiry["_id"])
        inquiry["property_id"] = str(inquiry["property_id"])
        inquiry["user_id"] = str(inquiry["user_id"])
    
    return inquiries


@router.get("/{inquiry_id}", response_model=Inquiry)
async def get_inquiry(inquiry_id: str):
    """Get a specific inquiry by ID"""
    db = await get_database()
    if not ObjectId.is_valid(inquiry_id):
        raise HTTPException(status_code=400, detail="Invalid inquiry ID")
    
    inquiry = await db.inquiries.find_one({"_id": ObjectId(inquiry_id)})
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    
    inquiry["_id"] = str(inquiry["_id"])
    inquiry["property_id"] = str(inquiry["property_id"])
    inquiry["user_id"] = str(inquiry["user_id"])
    return inquiry


@router.put("/{inquiry_id}", response_model=Inquiry)
async def update_inquiry(inquiry_id: str, inquiry_update: InquiryUpdate):
    """Update an inquiry"""
    db = await get_database()
    if not ObjectId.is_valid(inquiry_id):
        raise HTTPException(status_code=400, detail="Invalid inquiry ID")
    
    update_data = inquiry_update.dict(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    # If status is being updated to "completed", set completed_at
    if update_data.get("status") == "completed":
        update_data["completed_at"] = datetime.utcnow()
    
    result = await db.inquiries.update_one(
        {"_id": ObjectId(inquiry_id)},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    
    updated_inquiry = await db.inquiries.find_one({"_id": ObjectId(inquiry_id)})
    updated_inquiry["_id"] = str(updated_inquiry["_id"])
    updated_inquiry["property_id"] = str(updated_inquiry["property_id"])
    updated_inquiry["user_id"] = str(updated_inquiry["user_id"])
    return updated_inquiry


@router.delete("/{inquiry_id}", status_code=204)
async def delete_inquiry(inquiry_id: str):
    """Delete an inquiry"""
    db = await get_database()
    if not ObjectId.is_valid(inquiry_id):
        raise HTTPException(status_code=400, detail="Invalid inquiry ID")
    
    result = await db.inquiries.delete_one({"_id": ObjectId(inquiry_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    
    return None



