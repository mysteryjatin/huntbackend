"""
Subscription Plans API - Returns all subscription plan tiers for the Subscription Plan Screen.
Plans: Metal (Free), Bronze, Silver, Gold, Platinum.
Optionally pass user_id to get current_plan_id and is_current on each plan.
After spin: Platinum = Active Plan, rest = Downgrade. Use POST /activate-spin-reward to set user's plan to Platinum.
iOS: POST /apple/verify-receipt with App Store receipt to unlock plan (Guideline 3.1.1).
"""
import os
from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional, Any, Dict
from bson import ObjectId
from pydantic import BaseModel
import aiohttp
from app.database import get_database

router = APIRouter()

# Must match App Store Connect product IDs and frontend iap_product_ids.dart
APPLE_PRODUCT_TO_PLAN = {
    "com.hunt.property.subscription.bronze": "bronze",
    "com.hunt.property.subscription.silver": "silver",
    "com.hunt.property.subscription.gold": "gold",
    "com.hunt.property.subscription.platinum": "platinum",
}

APP_STORE_VERIFY_PRODUCTION = "https://buy.itunes.apple.com/verifyReceipt"
APP_STORE_VERIFY_SANDBOX = "https://sandbox.itunes.apple.com/verifyReceipt"


class AppleVerifyReceiptBody(BaseModel):
    user_id: str
    receipt_data: str

# Plan definitions matching frontend subscription_plans_screen.dart (Metal, Bronze, Silver, Gold, Platinum)
SUBSCRIPTION_PLANS = [
    {
        "id": "metal",
        "name": "Metal",
        "duration_days": 30,
        "duration_label": "1 month",
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
        "apple_product_id": None,
    },
    {
        "id": "bronze",
        "name": "Bronze",
        "duration_days": 60,
        "duration_label": "2 months",
        "price_amount": 729,
        "price_display": "₹ 729",
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
        "apple_product_id": "com.hunt.property.subscription.bronze",
    },
    {
        "id": "silver",
        "name": "Silver",
        "duration_days": 90,
        "duration_label": "3 months",
        "price_amount": 1399,
        "price_display": "₹ 1399",
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
        "apple_product_id": "com.hunt.property.subscription.silver",
    },
    {
        "id": "gold",
        "name": "Gold",
        "duration_days": 90,
        "duration_label": "3 months",
        "price_amount": 3499,
        "price_display": "₹ 3499",
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
        "apple_product_id": "com.hunt.property.subscription.gold",
    },
    {
        "id": "platinum",
        "name": "Platinum",
        "duration_days": 180,
        "duration_label": "6 months",
        "price_amount": 4999,
        "price_display": "₹ 4999",
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
        "apple_product_id": "com.hunt.property.subscription.platinum",
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


def _pick_latest_product_id(latest_receipt_info: Any) -> Optional[str]:
    if not latest_receipt_info:
        return None
    rows = latest_receipt_info if isinstance(latest_receipt_info, list) else [latest_receipt_info]
    best_pid: Optional[str] = None
    best_exp = -1
    for item in rows:
        if not isinstance(item, dict):
            continue
        pid = item.get("product_id")
        exp_ms = item.get("expires_date_ms")
        if exp_ms is None or pid is None:
            continue
        try:
            exp = int(exp_ms)
        except (TypeError, ValueError):
            continue
        if exp > best_exp:
            best_exp = exp
            best_pid = pid
    return best_pid


async def _post_apple_verify(url: str, payload: dict) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            return await resp.json()


async def _verify_apple_receipt(receipt_data: str) -> dict:
    secret = os.getenv("APP_STORE_SHARED_SECRET", "").strip()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="Server is not configured for App Store verification (APP_STORE_SHARED_SECRET).",
        )
    payload = {
        "receipt-data": receipt_data,
        "password": secret,
        "exclude-old-transactions": True,
    }
    data = await _post_apple_verify(APP_STORE_VERIFY_PRODUCTION, payload)
    status = data.get("status")
    if status == 21007:
        data = await _post_apple_verify(APP_STORE_VERIFY_SANDBOX, payload)
    if data.get("status") != 0:
        raise HTTPException(
            status_code=400,
            detail=f"Apple receipt verification failed (status={data.get('status')})",
        )
    return data


def _plan_id_from_apple_body(data: dict) -> Optional[str]:
    pid = _pick_latest_product_id(data.get("latest_receipt_info"))
    if pid and pid in APPLE_PRODUCT_TO_PLAN:
        return APPLE_PRODUCT_TO_PLAN[pid]
    receipt = data.get("receipt") or {}
    in_app = receipt.get("in_app") or []
    best_pid: Optional[str] = None
    best_exp = -1
    for item in in_app:
        if not isinstance(item, dict):
            continue
        p = item.get("product_id")
        exp_ms = item.get("expires_date_ms") or item.get("purchase_date_ms")
        if exp_ms is None or p is None:
            continue
        try:
            exp = int(exp_ms)
        except (TypeError, ValueError):
            continue
        if exp > best_exp:
            best_exp = exp
            best_pid = p
    if best_pid and best_pid in APPLE_PRODUCT_TO_PLAN:
        return APPLE_PRODUCT_TO_PLAN[best_pid]
    return None


@router.post("/apple/verify-receipt")
async def apple_verify_receipt(body: AppleVerifyReceiptBody):
    """
    Verify an iOS App Store receipt and set the user's subscription_plan_id.
    Required for Guideline 3.1.1 (digital subscriptions must use In-App Purchase).
    """
    if not body.user_id or not body.user_id.strip():
        raise HTTPException(status_code=400, detail="user_id is required")
    if not ObjectId.is_valid(body.user_id.strip()):
        raise HTTPException(status_code=400, detail="Invalid user ID")
    if not body.receipt_data or not body.receipt_data.strip():
        raise HTTPException(status_code=400, detail="receipt_data is required")

    data = await _verify_apple_receipt(body.receipt_data.strip())
    plan_id = _plan_id_from_apple_body(data)
    if not plan_id:
        raise HTTPException(
            status_code=400,
            detail="Could not identify a known subscription product in the App Store receipt",
        )

    db = await get_database()
    uid = ObjectId(body.user_id.strip())
    result = await db.users.update_one(
        {"_id": uid},
        {"$set": {"subscription_plan_id": plan_id}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "success": True,
        "data": {
            "current_plan_id": plan_id,
            "message": "Subscription updated from App Store purchase.",
        },
    }
