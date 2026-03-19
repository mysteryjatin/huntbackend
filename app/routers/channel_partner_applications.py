"""
Public lead form: Channel Partner Application.
Stores partnership enquiries with applicant details.
No authentication required — anyone can apply.
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
from app.schemas import ChannelPartnerApplication, ChannelPartnerApplicationCreate
from app.database import get_database

router = APIRouter()


@router.post("/", response_model=ChannelPartnerApplication, status_code=201)
async def create_channel_partner_application(data: ChannelPartnerApplicationCreate):
    """
    Submit a channel partner application (public — no login required).
    """
    db = await get_database()

    doc = {
        "full_name": data.full_name.strip(),
        "mobile": data.mobile.strip(),
        "email": str(data.email).strip().lower(),
        "company_name": (data.company_name or "").strip() or None,
        "industry_type": (data.industry_type or "").strip() or None,
        "message": (data.message or "").strip() or None,
        "status": "new",
        "created_at": datetime.utcnow(),
    }

    result = await db.channel_partner_applications.insert_one(doc)
    created = await db.channel_partner_applications.find_one({"_id": result.inserted_id})
    created["_id"] = str(created["_id"])
    return created


@router.get("/", status_code=200)
async def list_channel_partner_applications(page: int = 1, limit: int = 20):
    """
    List all channel partner applications (admin use).
    """
    db = await get_database()
    skip = (page - 1) * limit
    cursor = db.channel_partner_applications.find().sort("created_at", -1).skip(skip).limit(limit)
    items = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        items.append(doc)
    total = await db.channel_partner_applications.count_documents({})
    return {"total": total, "page": page, "limit": limit, "items": items}
