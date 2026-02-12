import random
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Optional, Dict
from urllib.parse import quote
from app.database import get_database

# In-memory OTP storage (in production, use Redis or MongoDB)
otp_storage: Dict[str, Dict] = {}


class OTPService:
    # SMS API Configuration (NimbusIT)
    SMS_BASE_URL = "http://nimbusit.biz/api/SmsApi/SendSingleApi"
    SMS_USER_ID = "catalystepages"
    SMS_PASSWORD = "!pnLqoC7"
    SMS_SENDER_ID = "HNTPRP"
    SMS_ENTITY_ID = "1701176925982555502"
    SMS_TEMPLATE_ID_LOGIN = "1707177070006589173"
    SMS_TEMPLATE_ID_SIGNUP = "1707177070067885672"
    
    @staticmethod
    def generate_otp(length: int = 6) -> str:
        """Generate a random OTP"""
        return str(random.randint(10**(length-1), 10**length - 1))
    
    @staticmethod
    async def send_sms_via_nimbus(phone_number: str, otp: str, is_login: bool = False) -> bool:
        """
        Send OTP via NimbusIT SMS API.
        Returns True if SMS sent successfully, False otherwise.
        """
        try:
            # Remove + from phone number for SMS API (or keep it, depending on API requirements)
            phone_clean = phone_number.replace("+", "")
            
            # Select template based on login or signup
            template_id = OTPService.SMS_TEMPLATE_ID_LOGIN if is_login else OTPService.SMS_TEMPLATE_ID_SIGNUP
            
            # Build SMS message based on login or signup
            if is_login:
                msg = f"Use OTP {otp} to log in to your Hunt property account. This OTP is valid for 5 minutes. Do not share it with anyone."
            else:
                msg = f"Use OTP {otp} to complete your Hunt property signup. OTP is valid for 5 minutes. Do not share it with anyone."
            
            # Build SMS API URL (URL encode the message)
            url = (
                f"{OTPService.SMS_BASE_URL}?"
                f"UserID={OTPService.SMS_USER_ID}&"
                f"Password={OTPService.SMS_PASSWORD}&"
                f"SenderID={OTPService.SMS_SENDER_ID}&"
                f"Phno={phone_clean}&"
                f"Msg={quote(msg)}&"
                f"EntityID={OTPService.SMS_ENTITY_ID}&"
                f"TemplateID={template_id}"
            )
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        result = await response.text()
                        print(f"✅ SMS sent to {phone_number} via NimbusIT. Response: {result}")
                        return True
                    else:
                        print(f"❌ SMS API error for {phone_number}: Status {response.status}")
                        return False
        except Exception as e:
            print(f"❌ Error sending SMS to {phone_number}: {e}")
            return False
    
    @staticmethod
    async def send_otp(phone_number: str, is_login: bool = False) -> str:
        """
        Generate and send OTP to phone number via SMS.
        Returns the OTP (for internal storage/verification).
        """
        otp = OTPService.generate_otp()
        expires_at = datetime.utcnow() + timedelta(minutes=5)  # OTP valid for 5 minutes (matching SMS message)
        
        # Store OTP
        otp_storage[phone_number] = {
            "otp": otp,
            "expires_at": expires_at,
            "verified": False,
            "attempts": 0
        }
        
        # Send OTP via SMS (NimbusIT)
        sms_sent = await OTPService.send_sms_via_nimbus(phone_number, otp, is_login)
        if not sms_sent:
            print(f"⚠️ Warning: SMS sending failed for {phone_number}, but OTP generated: {otp}")
            # Still store OTP so verification can work if SMS is delayed
        
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
        expires_at = datetime.utcnow() + timedelta(minutes=5)  # Match SMS validity
        
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



