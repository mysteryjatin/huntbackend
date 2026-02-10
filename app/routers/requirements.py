"""
Post Your Requirement Screen API - Submit and list property requirements.
"""
import math
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from bson import ObjectId
from datetime import datetime
from app.schemas import Requirement, RequirementCreate
from app.database import get_database

router = APIRouter()


@router.post("/", response_model=Requirement, status_code=201)
async def submit_requirement(data: RequirementCreate):
  """
  Post Your Requirement - submit requirement form.
  """
  db = await get_database()
  doc = data.dict()
  doc["status"] = "submitted"
  doc["created_at"] = datetime.utcnow()
  if doc.get("user_id") and ObjectId.is_valid(doc["user_id"]):
    doc["user_id"] = ObjectId(doc["user_id"])
  else:
    doc["user_id"] = None
  result = await db.requirements.insert_one(doc)
  created = await db.requirements.find_one({"_id": result.inserted_id})
  created["_id"] = str(created["_id"])
  if created.get("user_id"):
    created["user_id"] = str(created["user_id"])
  return created


@router.get("/user/{user_id}")
async def get_user_requirements(
  user_id: str,
  page: int = Query(1, ge=1),
  limit: int = Query(20, ge=1, le=100),
):
  """
  List requirements posted by a user (paginated).
  """
  db = await get_database()
  if not ObjectId.is_valid(user_id):
    raise HTTPException(status_code=400, detail="Invalid user ID")
  query = {"user_id": ObjectId(user_id)}
  total = await db.requirements.count_documents(query)
  skip = (page - 1) * limit
  cursor = (
    db.requirements.find(query)
    .sort("created_at", -1)
    .skip(skip)
    .limit(limit)
  )
  items = await cursor.to_list(length=limit)
  for doc in items:
    doc["_id"] = str(doc["_id"])
    if doc.get("user_id"):
      doc["user_id"] = str(doc["user_id"])
  total_pages = math.ceil(total / limit) if total > 0 else 0
  return {
    "success": True,
    "data": {
      "requirements": items,
      "total": total,
      "page": page,
      "limit": limit,
      "total_pages": total_pages,
      "has_next": page < total_pages,
      "has_prev": page > 1,
    },
  }


@router.get("/{requirement_id}", response_model=Requirement)
async def get_requirement(requirement_id: str):
  """
  Get a single requirement by ID.
  """
  db = await get_database()
  if not ObjectId.is_valid(requirement_id):
    raise HTTPException(status_code=400, detail="Invalid requirement ID")
  doc = await db.requirements.find_one({"_id": ObjectId(requirement_id)})
  if not doc:
    raise HTTPException(status_code=404, detail="Requirement not found")
  doc["_id"] = str(doc["_id"])
  if doc.get("user_id"):
    doc["user_id"] = str(doc["user_id"])
  return doc

