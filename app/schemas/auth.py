from pydantic import BaseModel, Field, EmailStr
from typing import Optional


class RequestOTPRequest(BaseModel):
    phone_number: str = Field(..., description="Phone number with country code (e.g., +918881675561)")


class RequestOTPResponse(BaseModel):
    message: str
    phone_number: str


class VerifyOTPRequest(BaseModel):
    phone_number: str = Field(..., description="Phone number with country code")
    otp: str = Field(..., min_length=4, max_length=6, description="OTP code")


class VerifyOTPResponse(BaseModel):
    verified: bool
    message: str
    token: Optional[str] = None  # For future JWT implementation


class SignupRequest(BaseModel):
    phone_number: str = Field(..., description="Phone number (must be OTP verified)")
    full_name: str = Field(..., min_length=2, description="Full name of the user")
    email: Optional[EmailStr] = Field(None, description="Email address of the user")
    is_real_estate_agent: bool = Field(default=False, description="Whether user is a real estate agent")
    user_type: Optional[str] = Field(None, description="User type: owner, buyer, agent, or user")
    terms_accepted: bool = Field(..., description="Must be true to accept terms and conditions")


class SignupResponse(BaseModel):
    message: str
    user_id: str
    phone_number: str
    full_name: str
    email: Optional[str] = None


# Login Schemas
class LoginRequestOTPRequest(BaseModel):
    phone_number: str = Field(..., description="Phone number with country code (e.g., +918881675561)")


class LoginRequestOTPResponse(BaseModel):
    message: str
    phone_number: str


class LoginVerifyOTPRequest(BaseModel):
    phone_number: str = Field(..., description="Phone number with country code")
    otp: str = Field(..., min_length=4, max_length=6, description="OTP code")


class LoginVerifyOTPResponse(BaseModel):
    message: str
    user_id: str
    phone_number: str
    name: str
    email: Optional[str] = None
    user_type: str
    token: Optional[str] = None  # For future JWT implementation



