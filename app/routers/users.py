from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from app.schemas import User, UserCreate, UserUpdate
from app.database import get_database
from app.upload_urls import canonical_client_image_url
import hashlib
import math

router = APIRouter()


def hash_password(password: str) -> str:
    """Simple password hashing (in production, use bcrypt)"""
    return hashlib.sha256(password.encode()).hexdigest()


@router.post("/", response_model=User, status_code=201)
async def create_user(user: UserCreate):
    """Create a new user"""
    db = await get_database()
    
    user_dict = user.dict()
    
    # Normalize/clean optional phone: if it's empty, don't store it at all.
    # This avoids hitting the unique index on phone with the same empty value ("")
    # for every social-login user who hasn't added a phone yet.
    phone_value = user_dict.get("phone")
    if not phone_value:
        user_dict.pop("phone", None)

    # Ensure avatar_url is never null; use empty string as default
    if not user_dict.get("avatar_url"):
        user_dict["avatar_url"] = ""

    # Check if email already exists
    existing_user = await db.users.find_one({"email": user_dict["email"]})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_dict["password"] = hash_password(user_dict.pop("password"))
    user_dict["created_at"] = datetime.utcnow()
    
    result = await db.users.insert_one(user_dict)
    created_user = await db.users.find_one({"_id": result.inserted_id})
    created_user["_id"] = str(created_user["_id"])
    created_user.pop("password", None)  # Don't return password
    return created_user


@router.get("/", response_model=List[User])
async def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    user_type: Optional[str] = None
):
    """Get all users with optional filter"""
    db = await get_database()
    query = {}
    
    if user_type:
        query["user_type"] = user_type
    
    cursor = db.users.find(query).skip(skip).limit(limit).sort("created_at", -1)
    users = await cursor.to_list(length=limit)
    
    for user in users:
        user["_id"] = str(user["_id"])
        user.pop("password", None)  # Don't return password
    
    return users


@router.get("/{user_id}", response_model=User)
async def get_user(user_id: str):
    """Get a specific user by ID"""
    db = await get_database()
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")

    # Some older records may store `_id` as a string instead of ObjectId.
    # Try both representations for better compatibility.
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        user = await db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user["_id"] = str(user["_id"])
    user.pop("password", None)  # Don't return password
    return user


@router.get("/profile/{user_id}", response_model=User)
async def get_profile(user_id: str):
    """Get a user's profile data for edit profile screen"""
    db = await get_database()
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")

    # Compatibility: allow `_id` stored as string in some environments.
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        user = await db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Convert ObjectId to string and hide password field
    user["_id"] = str(user["_id"])
    user.pop("password", None)
    return user


@router.put("/{user_id}", response_model=User)
async def update_user(user_id: str, user_update: UserUpdate):
    """Update a user"""
    db = await get_database()
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    update_data = user_update.dict(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    # Check if email is being updated and already exists
    if "email" in update_data:
        existing_user = await db.users.find_one({"email": update_data["email"]})
        if existing_user and str(existing_user["_id"]) != user_id:
            raise HTTPException(status_code=400, detail="Email already registered")
    
    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    updated_user = await db.users.find_one({"_id": ObjectId(user_id)})
    updated_user["_id"] = str(updated_user["_id"])
    updated_user.pop("password", None)  # Don't return password
    return updated_user


@router.put("/profile/{user_id}", response_model=User)
async def update_profile(user_id: str, user_update: UserUpdate):
    """
    Update a user's profile data.
    Intended for the Edit Profile screen – allows updating name, email, phone, and user_type.
    """
    db = await get_database()
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")

    update_data = user_update.dict(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Check if email is being updated and already exists for another user
    if "email" in update_data:
        existing_user = await db.users.find_one({"email": update_data["email"]})
        if existing_user and str(existing_user["_id"]) != user_id:
            raise HTTPException(status_code=400, detail="Email already registered")

    result = await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    updated_user = await db.users.find_one({"_id": ObjectId(user_id)})
    updated_user["_id"] = str(updated_user["_id"])
    updated_user.pop("password", None)
    return updated_user


@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: str):
    """Delete a user"""
    db = await get_database()
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    result = await db.users.delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return None


@router.get("/agents/search", response_model=dict)
async def search_agents(
    city: Optional[str] = Query(None, description="Filter by city (e.g., Delhi, Noida, Bangalore)"),
    location: Optional[str] = Query(None, description="Search by location/locality"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page")
):
    """
    Search Agents - Search for real estate agents.
    Filters users by user_type='agent' or is_real_estate_agent=true.
    Supports filtering by city and location search.
    """
    db = await get_database()

    # Must be an agent AND match optional city/location filters
    agent_filter: dict = {
        "$or": [
            {"user_type": "agent"},
            {"is_real_estate_agent": True},
        ]
    }
    parts: List[dict] = [agent_filter]

    if city and city.strip():
        c = city.strip()
        parts.append(
            {
                "$or": [
                    {"city": {"$regex": c, "$options": "i"}},
                    {"address": {"$regex": c, "$options": "i"}},
                    {"location.city": {"$regex": c, "$options": "i"}},
                    {"dealing_in": {"$regex": c, "$options": "i"}},
                ]
            }
        )

    if location and location.strip():
        loc = location.strip()
        parts.append(
            {
                "$or": [
                    {"address": {"$regex": loc, "$options": "i"}},
                    {"locality": {"$regex": loc, "$options": "i"}},
                    {"location.locality": {"$regex": loc, "$options": "i"}},
                    {"city": {"$regex": loc, "$options": "i"}},
                    {"dealing_in": {"$regex": loc, "$options": "i"}},
                ]
            }
        )

    query: dict = {"$and": parts} if len(parts) > 1 else agent_filter
    
    # Count total agents
    total = await db.users.count_documents(query)
    
    # Calculate pagination
    skip = (page - 1) * limit
    
    # Fetch agents
    cursor = (
        db.users.find(query)
        .skip(skip)
        .limit(limit)
        .sort("created_at", -1)  # Sort by newest first
    )
    
    agents = await cursor.to_list(length=limit)
    
    # Format response
    formatted_agents = []
    for agent in agents:
        # Extract year from created_at for "operating since"
        operating_since = None
        if agent.get("created_at"):
            if isinstance(agent["created_at"], datetime):
                operating_since = str(agent["created_at"].year)
            else:
                # Handle string dates
                try:
                    operating_since = str(datetime.fromisoformat(str(agent["created_at"])).year)
                except:
                    operating_since = "2020"  # Default fallback
        
        # Get dealing_in city or use city field or default
        dealing_in = (
            agent.get("dealing_in") or 
            agent.get("city") or 
            agent.get("location", {}).get("city") or 
            "N/A"
        )
        
        # Get address or construct from available fields
        address = (
            agent.get("address") or
            agent.get("location", {}).get("address") or
            f"{agent.get('locality', '')}, {dealing_in}".strip(", ")
        )
        
        avatar = agent.get("avatar_url") or agent.get("profile_image") or ""
        if avatar:
            avatar = canonical_client_image_url(avatar) or avatar
        formatted_agent = {
            "_id": str(agent["_id"]),
            "name": agent.get("name", "Agent"),
            "email": agent.get("email", ""),
            "phone": agent.get("phone", ""),
            "address": address,
            "city": agent.get("city") or dealing_in,
            "dealing_in": dealing_in,
            "operating_since": operating_since or "2020",
            "avatar_url": avatar,
            "user_type": agent.get("user_type", "agent"),
            "created_at": agent.get("created_at").isoformat() if agent.get("created_at") else None
        }
        formatted_agents.append(formatted_agent)
    
    total_pages = math.ceil(total / limit) if total > 0 else 0
    
    return {
        "success": True,
        "data": {
            "agents": formatted_agents,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    }



