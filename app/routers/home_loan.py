"""
Home Loan Screen API - Submit and list home loan applications.
Stores application data from the Apply Loan form (loan type, name, email, phone, address).
"""
import math
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from app.schemas import HomeLoanApplication, HomeLoanApplicationCreate
from app.database import get_database

router = APIRouter()

VALID_LOAN_TYPES = {"home loan", "commercial loan", "residential loan"}


@router.post("/", response_model=HomeLoanApplication, status_code=201)
async def submit_home_loan_application(data: HomeLoanApplicationCreate):
    """
    Home Loan Screen – Submit application. Stores in DB.
    loan_type: "Home Loan" | "Commercial Loan" | "Residential Loan"
    """
    loan_type_lower = data.loan_type.strip().lower()
    if loan_type_lower not in VALID_LOAN_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"loan_type must be one of: Home Loan, Commercial Loan, Residential Loan",
        )
    db = await get_database()
    doc = data.dict()
    doc["loan_type"] = data.loan_type.strip()
    doc["status"] = "submitted"
    doc["created_at"] = datetime.utcnow()
    if doc.get("user_id"):
        if ObjectId.is_valid(doc["user_id"]):
            doc["user_id"] = ObjectId(doc["user_id"])
        else:
            doc["user_id"] = None
    else:
        doc["user_id"] = None
    result = await db.home_loan_applications.insert_one(doc)
    created = await db.home_loan_applications.find_one({"_id": result.inserted_id})
    created["_id"] = str(created["_id"])
    if created.get("user_id"):
        created["user_id"] = str(created["user_id"])
    return created


@router.get("/user/{user_id}")
async def get_user_applications(
    user_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """List home loan applications for a user (paginated)."""
    db = await get_database()
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")
    query = {"user_id": ObjectId(user_id)}
    total = await db.home_loan_applications.count_documents(query)
    skip = (page - 1) * limit
    cursor = (
        db.home_loan_applications.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    applications = await cursor.to_list(length=limit)
    for a in applications:
        a["_id"] = str(a["_id"])
        if a.get("user_id"):
            a["user_id"] = str(a["user_id"])
    total_pages = math.ceil(total / limit) if total > 0 else 0
    return {
        "success": True,
        "data": {
            "applications": applications,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }


@router.get("/{application_id}", response_model=HomeLoanApplication)
async def get_application(application_id: str):
    """Get a single home loan application by ID."""
    db = await get_database()
    if not ObjectId.is_valid(application_id):
        raise HTTPException(status_code=400, detail="Invalid application ID")
    app = await db.home_loan_applications.find_one({"_id": ObjectId(application_id)})
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    app["_id"] = str(app["_id"])
    if app.get("user_id"):
        app["user_id"] = str(app["user_id"])
    return app
