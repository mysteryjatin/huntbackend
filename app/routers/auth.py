from fastapi import APIRouter, HTTPException, status
from bson import ObjectId
from datetime import datetime
from app.schemas.auth import (
    RequestOTPRequest, RequestOTPResponse,
    VerifyOTPRequest, VerifyOTPResponse,
    SignupRequest, SignupResponse,
    LoginRequestOTPRequest, LoginRequestOTPResponse,
    LoginVerifyOTPRequest, LoginVerifyOTPResponse
)
from app.schemas import User
from app.services.otp_service import OTPService
from app.database import get_database
import hashlib

router = APIRouter()


def hash_password(password: str) -> str:
    """Simple password hashing (in production, use bcrypt)"""
    return hashlib.sha256(password.encode()).hexdigest()


@router.post("/request-otp", response_model=RequestOTPResponse, status_code=status.HTTP_200_OK)
async def request_otp(request: RequestOTPRequest):
    """
    Request OTP for phone number verification
    This is the first step in the signup process
    """
    phone_number = request.phone_number.strip()
    
    # Validate phone number format (basic validation)
    if not phone_number.startswith("+") or len(phone_number) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number format. Please include country code (e.g., +918881675561)"
        )
    
    # Check if user already exists
    db = await get_database()
    existing_user = await db.users.find_one({"phone": phone_number})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this phone number already exists"
        )
    
    # Generate and send OTP via SMS (signup flow)
    otp = await OTPService.send_otp(phone_number, is_login=False)
    
    # Store in database (optional, for persistence across server restarts)
    await OTPService.store_otp_in_db(phone_number, otp)
    
    return RequestOTPResponse(
        message="OTP sent successfully to your phone number",
        phone_number=phone_number
    )


@router.post("/verify-otp", response_model=VerifyOTPResponse, status_code=status.HTTP_200_OK)
async def verify_otp(request: VerifyOTPRequest):
    """
    Verify OTP for phone number
    This is the second step - after OTP verification, user can proceed to signup
    """
    phone_number = request.phone_number.strip()
    otp = request.otp.strip()
    
    # Verify OTP (try database first, fallback to memory)
    verified = await OTPService.verify_otp_from_db(phone_number, otp)
    if not verified:
        verified = await OTPService.verify_otp(phone_number, otp)
    
    if not verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP. Please request a new OTP."
        )
    
    return VerifyOTPResponse(
        verified=True,
        message="OTP verified successfully. You can now complete your signup.",
        token=None  # For future JWT implementation
    )


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(request: SignupRequest):
    """
    Complete user signup after OTP verification
    This is the final step - saves user data to database
    """
    phone_number = request.phone_number.strip()
    
    # Check if OTP is verified
    is_verified = await OTPService.is_otp_verified_from_db(phone_number)
    if not is_verified:
        is_verified = await OTPService.is_otp_verified(phone_number)
    
    if not is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number not verified. Please verify OTP first."
        )
    
    # Check if user already exists
    db = await get_database()
    existing_user = await db.users.find_one({"phone": phone_number})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this phone number already exists"
        )
    
    # Validate terms acceptance
    if not request.terms_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must accept the Terms & Conditions and Privacy Policy to continue"
        )
    
    # Determine user type - prioritize request.user_type, then is_real_estate_agent, default to "buyer"
    if request.user_type:
        user_type = request.user_type.lower()
        # Map "user" to "buyer" for backward compatibility
        if user_type == "user":
            user_type = "buyer"
    elif request.is_real_estate_agent:
        user_type = "agent"
    else:
        user_type = "buyer"
    
    # Validate user_type
    if user_type not in ["owner", "buyer", "agent"]:
        user_type = "buyer"  # Default to buyer if invalid
    
    # Use email from request if provided, otherwise generate temporary email
    if request.email:
        email = str(request.email).strip()
        # Basic email validation (EmailStr already validates format, but double-check)
        if "@" not in email or len(email) < 5:
            email = f"{phone_number}@temp.huntproperty.com"  # Invalid email, use fallback
    else:
        email = f"{phone_number}@temp.huntproperty.com"  # Temporary email fallback
    
    # Check if email already exists (if not temporary)
    if not email.endswith("@temp.huntproperty.com"):
        existing_email_user = await db.users.find_one({"email": email})
        if existing_email_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
    
    # Create user
    user_dict = {
        "name": request.full_name,
        "phone": phone_number,
        "email": email,
        "user_type": user_type,
        "created_at": datetime.utcnow(),
        "password": hash_password(phone_number)  # Default password (user can change later)
    }
    
    result = await db.users.insert_one(user_dict)
    user_id = str(result.inserted_id)
    
    # Clear OTP after successful signup
    await OTPService.clear_otp_from_db(phone_number)
    await OTPService.clear_otp(phone_number)
    
    return SignupResponse(
        message="Account created successfully",
        user_id=user_id,
        phone_number=phone_number,
        full_name=request.full_name,
        email=email
    )


@router.get("/check-phone/{phone_number}", status_code=status.HTTP_200_OK)
async def check_phone_exists(phone_number: str):
    """
    Check if phone number is already registered
    Useful for login/signup flow
    """
    db = await get_database()
    user = await db.users.find_one({"phone": phone_number})
    
    return {
        "exists": user is not None,
        "phone_number": phone_number
    }


@router.post("/login/request-otp", response_model=LoginRequestOTPResponse, status_code=status.HTTP_200_OK)
async def login_request_otp(request: LoginRequestOTPRequest):
    """
    Request OTP for login
    Checks if phone number exists in database, then sends OTP
    """
    phone_number = request.phone_number.strip()
    
    # Validate phone number format (basic validation)
    if not phone_number.startswith("+") or len(phone_number) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number format. Please include country code (e.g., +918881675561)"
        )
    
    # Check if user exists in database
    db = await get_database()
    existing_user = await db.users.find_one({"phone": phone_number})
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this phone number not found. Please sign up first."
        )
    
    # Generate and send OTP via SMS (login flow)
    otp = await OTPService.send_otp(phone_number, is_login=True)
    
    # Store in database (optional, for persistence across server restarts)
    await OTPService.store_otp_in_db(phone_number, otp)
    
    return LoginRequestOTPResponse(
        message="OTP sent successfully to your phone number",
        phone_number=phone_number
    )


@router.post("/login/verify-otp", response_model=LoginVerifyOTPResponse, status_code=status.HTTP_200_OK)
async def login_verify_otp(request: LoginVerifyOTPRequest):
    """
    Verify OTP and login user
    After OTP verification, returns user data
    """
    phone_number = request.phone_number.strip()
    otp = request.otp.strip()
    
    # Verify OTP (try database first, fallback to memory)
    verified = await OTPService.verify_otp_from_db(phone_number, otp)
    if not verified:
        verified = await OTPService.verify_otp(phone_number, otp)
    
    if not verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP. Please request a new OTP."
        )
    
    # Get user from database
    db = await get_database()
    user = await db.users.find_one({"phone": phone_number})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Clear OTP after successful login
    await OTPService.clear_otp_from_db(phone_number)
    await OTPService.clear_otp(phone_number)
    
    return LoginVerifyOTPResponse(
        message="Login successful",
        user_id=str(user["_id"]),
        phone_number=user.get("phone", phone_number),
        name=user.get("name", ""),
        email=user.get("email"),
        user_type=user.get("user_type", "buyer"),
        token=None  # For future JWT implementation
    )



