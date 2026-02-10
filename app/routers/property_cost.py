"""
Property Cost Screen API - Submit and list property cost calculations.
Stores estimate form + Annexure I/II/III breakdown and grand total.
"""
import math
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from app.schemas import (
    PropertyCostCalculation,
    PropertyCostCalculationCreate,
)
from app.database import get_database

router = APIRouter()


def _row_sum(rows: List[dict]) -> float:
    return sum((r.get("price") or 0) * (r.get("units") or 0) for r in rows)


def _grand_total(doc: dict) -> float:
    return (
        _row_sum(doc.get("annexure_i") or [])
        + _row_sum(doc.get("annexure_ii") or [])
        + _row_sum(doc.get("annexure_iii") or [])
    )


def _serialize(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    if doc.get("user_id"):
        doc["user_id"] = str(doc["user_id"])
    return doc


@router.post("/", response_model=PropertyCostCalculation, status_code=201)
async def submit_property_cost(data: PropertyCostCalculationCreate):
    """
    Property Cost Screen – Submit calculation. Stores in DB and computes grand_total.
    """
    db = await get_database()
    doc = data.dict()
    # data.dict() already serializes annexure lists as list of dicts
    doc["grand_total"] = _grand_total(doc)
    doc["created_at"] = datetime.utcnow()
    if doc.get("user_id") and ObjectId.is_valid(doc["user_id"]):
        doc["user_id"] = ObjectId(doc["user_id"])
    else:
        doc["user_id"] = None
    result = await db.property_cost_calculations.insert_one(doc)
    created = await db.property_cost_calculations.find_one({"_id": result.inserted_id})
    return _serialize(created)


@router.get("/user/{user_id}")
async def get_user_calculations(
    user_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """List property cost calculations for a user (paginated), newest first."""
    db = await get_database()
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")
    query = {"user_id": ObjectId(user_id)}
    total = await db.property_cost_calculations.count_documents(query)
    skip = (page - 1) * limit
    cursor = (
        db.property_cost_calculations.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    items = await cursor.to_list(length=limit)
    for doc in items:
        _serialize(doc)
    total_pages = math.ceil(total / limit) if total > 0 else 0
    return {
        "success": True,
        "data": {
            "calculations": items,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }


@router.get("/{calculation_id}", response_model=PropertyCostCalculation)
async def get_calculation(calculation_id: str):
    """Get a single property cost calculation by ID."""
    db = await get_database()
    if not ObjectId.is_valid(calculation_id):
        raise HTTPException(status_code=400, detail="Invalid calculation ID")
    doc = await db.property_cost_calculations.find_one({"_id": ObjectId(calculation_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Calculation not found")
    return _serialize(doc)
