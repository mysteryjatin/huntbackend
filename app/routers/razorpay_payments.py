"""
Razorpay Checkout for website (e.g. Advertising Packages).
Keys only via environment — never expose RAZORPAY_KEY_SECRET to the client.

Flow:
1) POST /create-order — creates Razorpay order, stores pending checkout in MongoDB
2) POST /verify-payment — verifies signature, marks checkout paid
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict

import razorpay
from fastapi import APIRouter, HTTPException

from app.database import get_database
from app.schemas import RazorpayCreateOrderRequest, RazorpayCreateOrderResponse, RazorpayVerifyRequest, RazorpayVerifyResponse

router = APIRouter()

# Server-side price map (INR → paise). Client cannot override amount.
# ₹35,000 = 3_500_000 paise
_AD_PACKAGES: Dict[str, Dict[str, Any]] = {
    "horizontal_banner_home": {
        "amount_paise": 35000 * 100,
        "label": "Horizontal Banners — Home Page",
    },
    "vertical_banner_home": {
        "amount_paise": 35000 * 100,
        "label": "Vertical Banners — Home Page",
    },
    "horizontal_banner_dashboard": {
        "amount_paise": 25000 * 100,
        "label": "Horizontal Banners — Dashboard",
    },
    "vertical_banner_dashboard": {
        "amount_paise": 25000 * 100,
        "label": "Vertical Banners — Dashboard",
    },
}


def _client() -> razorpay.Client:
    key_id = os.getenv("RAZORPAY_KEY_ID", "").strip()
    secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
    if not key_id or not secret:
        raise HTTPException(
            status_code=503,
            detail="Payment gateway is not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET on the API server.",
        )
    return razorpay.Client(auth=(key_id, secret))


def _key_id_public() -> str:
    kid = os.getenv("RAZORPAY_KEY_ID", "").strip()
    if not kid:
        raise HTTPException(status_code=503, detail="Payment gateway is not configured.")
    return kid


@router.post("/create-order", response_model=RazorpayCreateOrderResponse)
async def create_order(body: RazorpayCreateOrderRequest):
    """Create a Razorpay order and a pending checkout record."""
    pkg = _AD_PACKAGES.get(body.package_id)
    if not pkg:
        raise HTTPException(status_code=400, detail="Invalid advertising package.")

    amount_paise = int(pkg["amount_paise"])
    label = str(pkg["label"])
    client = _client()

    receipt = f"adv_{body.package_id[:16]}_{int(datetime.utcnow().timestamp())}"[:40]
    notes = {
        "package_id": body.package_id,
        "label": label,
        "source": "website_advertising_packages",
    }
    if body.user_id:
        notes["user_id"] = body.user_id

    try:
        order = client.order.create(
            {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": receipt,
                "notes": notes,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not create payment order: {e!s}") from e

    order_id = order.get("id")
    if not order_id:
        raise HTTPException(status_code=502, detail="Invalid response from payment gateway.")

    db = await get_database()
    doc = {
        "razorpay_order_id": order_id,
        "package_id": body.package_id,
        "package_label": label,
        "amount_paise": amount_paise,
        "currency": "INR",
        "status": "pending",
        "user_id": body.user_id.strip() if body.user_id else None,
        "created_at": datetime.utcnow(),
    }
    await db.advertising_checkouts.insert_one(doc)

    return RazorpayCreateOrderResponse(
        key_id=_key_id_public(),
        order_id=order_id,
        amount=amount_paise,
        currency="INR",
        package_id=body.package_id,
        package_label=label,
    )


@router.post("/verify-payment", response_model=RazorpayVerifyResponse)
async def verify_payment(body: RazorpayVerifyRequest):
    """Verify Razorpay signature and complete the checkout."""
    db = await get_database()

    checkout = await db.advertising_checkouts.find_one(
        {"razorpay_order_id": body.razorpay_order_id}
    )
    if not checkout:
        raise HTTPException(
            status_code=400,
            detail="Unknown or expired order. Please start checkout again.",
        )
    if checkout.get("status") == "paid":
        return RazorpayVerifyResponse(
            ok=True,
            message="Payment was already recorded.",
            package_id=checkout.get("package_id", ""),
        )

    client = _client()
    params_dict = {
        "razorpay_order_id": body.razorpay_order_id,
        "razorpay_payment_id": body.razorpay_payment_id,
        "razorpay_signature": body.razorpay_signature,
    }
    try:
        client.utility.verify_payment_signature(params_dict)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail="Payment verification failed. If money was debited, contact support with your payment ID.",
        ) from e

    paid_at = datetime.utcnow()
    await db.advertising_checkouts.update_one(
        {"razorpay_order_id": body.razorpay_order_id},
        {
            "$set": {
                "status": "paid",
                "razorpay_payment_id": body.razorpay_payment_id,
                "paid_at": paid_at,
            }
        },
    )

    # Optional: mirror into advertising_payments for reporting
    await db.advertising_payments.insert_one(
        {
            "checkout_id": checkout.get("_id"),
            "razorpay_order_id": body.razorpay_order_id,
            "razorpay_payment_id": body.razorpay_payment_id,
            "package_id": checkout.get("package_id"),
            "package_label": checkout.get("package_label"),
            "amount_paise": checkout.get("amount_paise"),
            "currency": "INR",
            "user_id": checkout.get("user_id"),
            "created_at": paid_at,
        }
    )

    return RazorpayVerifyResponse(
        ok=True,
        message="Payment successful. Our team will contact you shortly.",
        package_id=str(checkout.get("package_id", "")),
    )
