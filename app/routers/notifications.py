"""
Notification Screen API - List and manage user notifications.
Supports pagination, unread filter, and mark-as-read.
"""
import math
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from app.schemas import (
    Notification,
    NotificationCreate,
    NotificationUpdate,
    NotificationListResponse,
)
from app.database import get_database

router = APIRouter()


@router.get("/user/{user_id}", response_model=NotificationListResponse)
async def get_user_notifications(
    user_id: str,
    read: Optional[bool] = Query(
        None,
        description="Filter by read status: true (read only), false (unread only), omit for all",
    ),
    type_filter: Optional[str] = Query(
        None,
        alias="type",
        description="Filter by notification type: inquiry, favorite, price_alert, system, etc.",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    Notification Screen: Get paginated list of notifications for a user.
    Returns unread_count for badge. Optional filters: read (unread/read), type.
    """
    db = await get_database()
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")

    query = {"user_id": ObjectId(user_id)}
    if read is not None:
        query["read"] = read
    if type_filter:
        query["type"] = type_filter.strip().lower()

    total = await db.notifications.count_documents(query)
    unread_count = await db.notifications.count_documents(
        {"user_id": ObjectId(user_id), "read": False}
    )
    skip = (page - 1) * limit
    cursor = (
        db.notifications.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    notifications = await cursor.to_list(length=limit)

    for n in notifications:
        n["_id"] = str(n["_id"])
        n["user_id"] = str(n["user_id"])

    total_pages = math.ceil(total / limit) if total > 0 else 0
    return NotificationListResponse(
        notifications=notifications,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
        unread_count=unread_count,
    )


@router.get("/user/{user_id}/unread-count")
async def get_unread_count(user_id: str):
    """
    Get unread notification count for badge (e.g. home screen bell icon).
    """
    db = await get_database()
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")
    count = await db.notifications.count_documents(
        {"user_id": ObjectId(user_id), "read": False}
    )
    return {"success": True, "data": {"unread_count": count}}


@router.post("/", response_model=Notification, status_code=201)
async def create_notification(notification: NotificationCreate):
    """Create a notification (e.g. when inquiry is sent, someone favorites a listing)."""
    db = await get_database()
    doc = notification.dict()
    doc["user_id"] = ObjectId(doc["user_id"])
    doc["read"] = doc.get("read", False)
    doc["created_at"] = datetime.utcnow()
    result = await db.notifications.insert_one(doc)
    created = await db.notifications.find_one({"_id": result.inserted_id})
    created["_id"] = str(created["_id"])
    created["user_id"] = str(created["user_id"])
    return created


@router.patch("/{notification_id}", response_model=Notification)
async def update_notification(notification_id: str, update: NotificationUpdate):
    """Update a notification (e.g. mark as read)."""
    db = await get_database()
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(status_code=400, detail="Invalid notification ID")
    data = update.dict(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await db.notifications.update_one(
        {"_id": ObjectId(notification_id)},
        {"$set": data},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    updated = await db.notifications.find_one({"_id": ObjectId(notification_id)})
    updated["_id"] = str(updated["_id"])
    updated["user_id"] = str(updated["user_id"])
    return updated


@router.post("/user/{user_id}/mark-all-read")
async def mark_all_read(user_id: str):
    """Mark all notifications as read for a user."""
    db = await get_database()
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")
    result = await db.notifications.update_many(
        {"user_id": ObjectId(user_id), "read": False},
        {"$set": {"read": True}},
    )
    return {
        "success": True,
        "data": {"modified_count": result.modified_count},
    }


@router.get("/{notification_id}", response_model=Notification)
async def get_notification(notification_id: str):
    """Get a single notification by ID."""
    db = await get_database()
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(status_code=400, detail="Invalid notification ID")
    n = await db.notifications.find_one({"_id": ObjectId(notification_id)})
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    n["_id"] = str(n["_id"])
    n["user_id"] = str(n["user_id"])
    return n


@router.delete("/{notification_id}", status_code=204)
async def delete_notification(notification_id: str):
    """Delete a notification."""
    db = await get_database()
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(status_code=400, detail="Invalid notification ID")
    result = await db.notifications.delete_one({"_id": ObjectId(notification_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return None
