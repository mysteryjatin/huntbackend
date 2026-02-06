"""
Order History Screen API - List and manage user orders (subscription/plan purchases).
"""
import math
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from app.schemas import Order, OrderCreate, OrderUpdate, OrderListResponse
from app.database import get_database

router = APIRouter()


def _order_title(plan_name: str, amount: float, order_id: str) -> str:
    """Build title like 'Owner-Gold -3500 / 114107135936' for Order History card."""
    id_suffix = order_id[-9:] if len(order_id) >= 9 else order_id
    amt = int(amount) if amount == int(amount) else amount
    return f"Owner-{plan_name} -{amt} / {id_suffix}"


@router.get("/user/{user_id}", response_model=OrderListResponse)
async def get_user_orders(
    user_id: str,
    status: Optional[str] = Query(
        None,
        description="Filter by status: pending, success, invalid, cancelled, refunded",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    Order History Screen: Get paginated list of orders for a user.
    Optional status filter. Orders sorted by created_at descending.
    """
    db = await get_database()
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")

    query = {"user_id": ObjectId(user_id)}
    if status:
        query["status"] = status.strip().lower()

    total = await db.orders.count_documents(query)
    skip = (page - 1) * limit
    cursor = (
        db.orders.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    orders = await cursor.to_list(length=limit)

    for o in orders:
        o["_id"] = str(o["_id"])
        o["user_id"] = str(o["user_id"])
        o["title"] = _order_title(
            o.get("plan_name", ""),
            o.get("amount", 0),
            o.get("order_number") or o["_id"],
        )

    total_pages = math.ceil(total / limit) if total > 0 else 0
    return OrderListResponse(
        orders=orders,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )


@router.post("/", response_model=Order, status_code=201)
async def create_order(order: OrderCreate):
    """Create an order (e.g. when user purchases a subscription plan)."""
    db = await get_database()
    doc = order.dict()
    doc["user_id"] = ObjectId(doc["user_id"])
    doc["created_at"] = datetime.utcnow()
    if not doc.get("order_number"):
        doc["order_number"] = str(ObjectId())[-9:]
    result = await db.orders.insert_one(doc)
    created = await db.orders.find_one({"_id": result.inserted_id})
    created["_id"] = str(created["_id"])
    created["user_id"] = str(created["user_id"])
    created["title"] = _order_title(
        created.get("plan_name", ""),
        created.get("amount", 0),
        created.get("order_number", created["_id"]),
    )
    return created


@router.get("/{order_id}", response_model=Order)
async def get_order(order_id: str):
    """Get a single order by ID."""
    db = await get_database()
    if not ObjectId.is_valid(order_id):
        raise HTTPException(status_code=400, detail="Invalid order ID")
    o = await db.orders.find_one({"_id": ObjectId(order_id)})
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    o["_id"] = str(o["_id"])
    o["user_id"] = str(o["user_id"])
    o["title"] = _order_title(
        o.get("plan_name", ""),
        o.get("amount", 0),
        o.get("order_number") or o["_id"],
    )
    return o


@router.patch("/{order_id}", response_model=Order)
async def update_order(order_id: str, update: OrderUpdate):
    """Update an order (e.g. set status to success after payment)."""
    db = await get_database()
    if not ObjectId.is_valid(order_id):
        raise HTTPException(status_code=400, detail="Invalid order ID")
    data = update.dict(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await db.orders.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": data},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    o = await db.orders.find_one({"_id": ObjectId(order_id)})
    o["_id"] = str(o["_id"])
    o["user_id"] = str(o["user_id"])
    o["title"] = _order_title(
        o.get("plan_name", ""),
        o.get("amount", 0),
        o.get("order_number") or o["_id"],
    )
    return o
