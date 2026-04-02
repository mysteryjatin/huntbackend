"""
Public lead form: Share Your Success Story (website testimonials page).
Stores submissions with optional image URL. No authentication required.
"""
from datetime import datetime

from fastapi import APIRouter

from app.database import get_database
from app.schemas import SuccessStory, SuccessStoryCreate

router = APIRouter()


@router.post("/", response_model=SuccessStory, status_code=201)
async def create_success_story(data: SuccessStoryCreate):
    """Submit a success story from the website."""
    db = await get_database()

    doc = {
        "first_name": data.first_name.strip(),
        "last_name": data.last_name.strip(),
        "email": str(data.email).strip().lower(),
        "phone": data.phone.strip(),
        "state": (data.state or "").strip() or None,
        "city": (data.city or "").strip() or None,
        "story": data.story.strip(),
        "consent_ads": bool(data.consent_ads),
        "image_url": (data.image_url or "").strip() or None,
        "user_id": (data.user_id or "").strip() or None,
        "status": "new",
        "created_at": datetime.utcnow(),
    }

    result = await db.success_stories.insert_one(doc)
    created = await db.success_stories.find_one({"_id": result.inserted_id})
    created["_id"] = str(created["_id"])
    return created


@router.get("/", status_code=200)
async def list_success_stories(page: int = 1, limit: int = 20):
    """List success stories (admin use)."""
    db = await get_database()
    skip = (page - 1) * limit
    cursor = db.success_stories.find().sort("created_at", -1).skip(skip).limit(limit)
    items = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        items.append(doc)
    total = await db.success_stories.count_documents({})
    return {"total": total, "page": page, "limit": limit, "items": items}
