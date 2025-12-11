import random
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict
from app.database import get_database

# In-memory OTP storage (in production, use Redis or MongoDB)
otp_storage: Dict[str, Dict] = {}


class OTPService:
    @staticmethod
    def generate_otp(length: int = 6) -> str:
        """Generate a random OTP"""
        return str(random.randint(10**(length-1), 10**length - 1))
    
    @staticmethod
    async def send_otp(phone_number: str) -> str:
        """
        Generate and send OTP to phone number
        Returns the OTP (in production, send via SMS service)
        """
        otp = OTPService.generate_otp()
        expires_at = datetime.utcnow() + timedelta(minutes=10)  # OTP valid for 10 minutes
        
        # Store OTP
        otp_storage[phone_number] = {
            "otp": otp,
            "expires_at": expires_at,
            "verified": False,
            "attempts": 0
        }
        
        # In production, integrate with SMS service like Twilio, AWS SNS, etc.
        # For now, we'll just return it (you can print it for testing)
        print(f"OTP for {phone_number}: {otp}")  # Remove in production
        
        # TODO: Integrate with SMS service
        # Example: await send_sms(phone_number, f"Your OTP is: {otp}")
        
        return otp
    
    @staticmethod
    async def verify_otp(phone_number: str, otp: str) -> bool:
        """Verify OTP for phone number"""
        if phone_number not in otp_storage:
            return False
        
        otp_data = otp_storage[phone_number]
        
        # Check if OTP expired
        if datetime.utcnow() > otp_data["expires_at"]:
            del otp_storage[phone_number]
            return False
        
        # Check attempts (max 5 attempts)
        if otp_data["attempts"] >= 5:
            del otp_storage[phone_number]
            return False
        
        # Increment attempts
        otp_data["attempts"] += 1
        
        # Verify OTP
        if otp_data["otp"] == otp:
            otp_data["verified"] = True
            return True
        
        return False
    
    @staticmethod
    async def is_otp_verified(phone_number: str) -> bool:
        """Check if OTP is verified for phone number"""
        if phone_number not in otp_storage:
            return False
        return otp_storage[phone_number].get("verified", False)
    
    @staticmethod
    async def clear_otp(phone_number: str):
        """Clear OTP data after successful signup"""
        if phone_number in otp_storage:
            del otp_storage[phone_number]
    
    @staticmethod
    async def store_otp_in_db(phone_number: str, otp: str):
        """Store OTP in MongoDB for persistence (optional)"""
        db = await get_database()
        expires_at = datetime.utcnow() + timedelta(minutes=10)
        
        await db.otps.update_one(
            {"phone_number": phone_number},
            {
                "$set": {
                    "otp": otp,
                    "expires_at": expires_at,
                    "verified": False,
                    "attempts": 0,
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )
    
    @staticmethod
    async def verify_otp_from_db(phone_number: str, otp: str) -> bool:
        """Verify OTP from MongoDB"""
        db = await get_database()
        otp_data = await db.otps.find_one({"phone_number": phone_number})
        
        if not otp_data:
            return False
        
        # Check if expired
        if datetime.utcnow() > otp_data["expires_at"]:
            await db.otps.delete_one({"phone_number": phone_number})
            return False
        
        # Check attempts
        if otp_data.get("attempts", 0) >= 5:
            await db.otps.delete_one({"phone_number": phone_number})
            return False
        
        # Update attempts
        await db.otps.update_one(
            {"phone_number": phone_number},
            {"$inc": {"attempts": 1}}
        )
        
        # Verify OTP
        if otp_data["otp"] == otp:
            await db.otps.update_one(
                {"phone_number": phone_number},
                {"$set": {"verified": True}}
            )
            return True
        
        return False
    
    @staticmethod
    async def is_otp_verified_from_db(phone_number: str) -> bool:
        """Check if OTP is verified from MongoDB"""
        db = await get_database()
        otp_data = await db.otps.find_one({"phone_number": phone_number})
        if not otp_data:
            return False
        return otp_data.get("verified", False)
    
    @staticmethod
    async def clear_otp_from_db(phone_number: str):
        """Clear OTP from MongoDB"""
        db = await get_database()
        await db.otps.delete_one({"phone_number": phone_number})


