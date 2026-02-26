"""
Subscription Plans API - Returns all subscription plan tiers for the Subscription Plan Screen.
Plans: Metal (Free), Bronze, Silver, Gold, Platinum.
Optionally pass user_id to get current_plan_id and is_current on each plan.
After spin: Platinum = Active Plan, rest = Downgrade. Use POST /activate-spin-reward to set user's plan to Platinum.
"""
from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional
from bson import ObjectId
from app.database import get_database

router = APIRouter()

# Plan definitions matching frontend subscription_plans_screen.dart (Metal, Bronze, Silver, Gold, Platinum)
SUBSCRIPTION_PLANS = [
    {
        "id": "metal",
        "name": "Metal",
        "duration_days": 30,
        "duration_label": "30 Days",
        "price_amount": 0,
        "price_display": "Free",
        "currency": "INR",
        "features": [
            "1 Listing",
            "Free Posting",
            "Photos Posting (Upto 5MB)",
        ],
        "button_label": "Downgrade",
        "image_slug": "metal",
        "colors": ["#A4A4A4", "#A3A2A2"],
        "text_color": "#000000",
        "is_dark": False,
        "sort_order": 1,
    },
    {
        "id": "bronze",
        "name": "Bronze",
        "duration_days": 60,
        "duration_label": "60 Days",
        "price_amount": 730,
        "price_display": "₹ 730",
        "currency": "INR",
        "features": [
            "5 Listing",
            "Chat Option",
            "Expert Property Description",
            "Buyer Contacts",
        ],
        "button_label": "Downgrade",
        "image_slug": "bronze",
        "colors": ["#A35C2C", "#CF895A"],
        "text_color": "#FFFFFF",
        "is_dark": False,
        "sort_order": 2,
    },
    {
        "id": "silver",
        "name": "Silver",
        "duration_days": 90,
        "duration_label": "90 Days",
        "price_amount": 1400,
        "price_display": "₹ 1400",
        "currency": "INR",
        "features": [
            "5 Listing",
            "Email Alerts",
            "Chat Option",
            "Get Buyer Contacts",
            "Expert Property Description",
        ],
        "button_label": "Active Plan",
        "image_slug": "sliver",
        "colors": ["#EDECEA", "#BEBDBC"],
        "text_color": "#000000",
        "is_dark": False,
        "sort_order": 3,
    },
    {
        "id": "gold",
        "name": "Gold",
        "duration_days": 120,
        "duration_label": "120 Days",
        "price_amount": 3500,
        "price_display": "₹ 3500",
        "currency": "INR",
        "features": [
            "7 Listing",
            "Video Posting",
            "SMS & Email Alerts",
            "Verified Tag",
            "Premium Visibility",
        ],
        "button_label": "Upgrade to Gold",
        "image_slug": "gold",
        "colors": ["#F6ECA5", "#D79E08"],
        "text_color": "#000000",
        "is_dark": False,
        "sort_order": 4,
    },
    {
        "id": "platinum",
        "name": "Platinum",
        "duration_days": 150,
        "duration_label": "150 Days",
        "price_amount": 5000,
        "price_display": "₹ 5000",
        "currency": "INR",
        "features": [
            "9 Listing",
            "All Gold Features",
            "Top Search Rank",
            "Dedicated Relationship Manager",
            "Social Media Promotion",
        ],
        "button_label": "Upgrade to Platinum",
        "image_slug": "platinum",
        "colors": ["#315A81", "#1E2B4B"],
        "text_color": "#FFFFFF",
        "is_dark": True,
        "sort_order": 5,
    },
]


def _get_plans_with_current(current_plan_id: Optional[str]) -> List[dict]:
    """Return plan list: current plan = 'Active Plan', all others = 'Downgrade' (e.g. after spin, Platinum = Active, rest = Downgrade)."""
    plans = []
    valid_ids = {p["id"] for p in SUBSCRIPTION_PLANS}
    current = (current_plan_id or "metal").lower().strip()
    if current not in valid_ids:
        current = "metal"
    for p in SUBSCRIPTION_PLANS:
        plan = dict(p)
        plan["is_current"] = plan["id"] == current
        if plan["is_current"]:
            plan["button_label"] = "Active Plan"
        else:
            plan["button_label"] = "Downgrade"
        plans.append(plan)
    return plans


@router.get("/")
async def get_subscription_plans(
    user_id: Optional[str] = Query(None, description="Optional: get current plan and mark is_current"),
):
    """
    Subscription Plan Screen: Get all subscription plans (Metal, Bronze, Silver, Gold, Platinum).
    Optionally pass user_id to get current_plan_id and is_current on each plan for the logged-in user.
    """
    current_plan_id = "metal"
    if user_id:
        db = await get_database()
        if ObjectId.is_valid(user_id):
            user = await db.users.find_one({"_id": ObjectId(user_id)})
            if user and user.get("subscription_plan_id"):
                current_plan_id = (user["subscription_plan_id"] or "metal").strip().lower()
        else:
            raise HTTPException(status_code=400, detail="Invalid user ID")

    plans = _get_plans_with_current(current_plan_id)
    return {
        "success": True,
        "data": {
            "plans": plans,
            "current_plan_id": current_plan_id,
            "header": {
                "title": "Choose your growth partner",
                "subtitle": "Upgrade to higher tiers for better visibility and faster leads.",
            },
            "footer": {
                "secure_note": "Secure payment   |   Cancel anytime.",
                "help_text": "Need help? Contact our support team.",
            },
        },
    }


# Plan ID granted when user wins the spin (Platinum)
SPIN_REWARD_PLAN_ID = "platinum"


@router.post("/activate-spin-reward")
async def activate_spin_reward(
    user_id: str = Body(..., embed=True, description="Logged-in user ID to activate Platinum plan from spin"),
):
    """
    Activate spin reward: set the user's subscription plan to Platinum (e.g. after spin wheel lands on Platinum).
    Subscription plans screen will then show Platinum as Active Plan and rest as Downgrade.
    """
    if not user_id or not user_id.strip():
        raise HTTPException(status_code=400, detail="user_id is required")
    if not ObjectId.is_valid(user_id.strip()):
        raise HTTPException(status_code=400, detail="Invalid user ID")
    db = await get_database()
    uid = ObjectId(user_id.strip())
    result = await db.users.update_one(
        {"_id": uid},
        {"$set": {"subscription_plan_id": SPIN_REWARD_PLAN_ID}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "success": True,
        "data": {
            "current_plan_id": SPIN_REWARD_PLAN_ID,
            "message": "Platinum plan activated (spin reward).",
        },
    }
