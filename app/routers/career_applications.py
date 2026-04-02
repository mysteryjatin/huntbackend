"""
Public lead form: Career Application.
Stores job applications with applicant details and resume link.
No authentication required — anyone can apply.
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
from app.schemas import CareerApplication, CareerApplicationCreate
from app.database import get_database

router = APIRouter()


@router.post("/", response_model=CareerApplication, status_code=201)
async def create_career_application(data: CareerApplicationCreate):
    """
    Submit a career application (public — no login required).
    """
    db = await get_database()

    doc = {
        "first_name": data.first_name.strip(),
        "last_name": data.last_name.strip(),
        "email": str(data.email).strip().lower(),
        "mobile": data.mobile.strip(),
        "state": (data.state or "").strip() or None,
        "city": (data.city or "").strip() or None,
        "job_category": (data.job_category or "").strip() or None,
        "experience_years": data.experience_years,
        "experience_months": data.experience_months,
        "resume_url": (data.resume_url or "").strip() or None,
        "self_description": (data.self_description or "").strip() or None,
        "position_discovery": (data.position_discovery or "").strip() or None,
        "status": "new",
        "created_at": datetime.utcnow(),
    }

    result = await db.career_applications.insert_one(doc)
    created = await db.career_applications.find_one({"_id": result.inserted_id})
    created["_id"] = str(created["_id"])
    return created


@router.get("/", status_code=200)
async def list_career_applications(page: int = 1, limit: int = 20):
    """
    List all career applications (admin use).
    """
    db = await get_database()
    skip = (page - 1) * limit
    cursor = db.career_applications.find().sort("created_at", -1).skip(skip).limit(limit)
    items = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        items.append(doc)
    total = await db.career_applications.count_documents({})
    return {"total": total, "page": page, "limit": limit, "items": items}
