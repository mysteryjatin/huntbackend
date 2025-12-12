from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional
import os

# MongoDB connection string
MONGODB_URL = "mongodb+srv://dbbackend6_db_user:Huntproperty@maindb.xcdfyp2.mongodb.net/"
DATABASE_NAME = "hunt_property"

# Global client instance
client: Optional[AsyncIOMotorClient] = None
database = None


async def connect_to_mongo():
    """Create database connection"""
    global client, database
    try:
        # Connection options to handle SSL/TLS issues on servers
        # tlsAllowInvalidCertificates=True is a temporary workaround for SSL handshake issues
        # TODO: Fix root cause by updating OpenSSL and CA certificates on server
        client = AsyncIOMotorClient(
            MONGODB_URL,
            tls=True,
            tlsAllowInvalidCertificates=True,  # Temporary workaround for SSL handshake errors
            serverSelectionTimeoutMS=30000,  # 30 seconds
            connectTimeoutMS=30000,
            socketTimeoutMS=30000,
            retryWrites=True,
            retryReads=True
        )
        database = client[DATABASE_NAME]
        # Test connection
        await client.admin.command('ping')
        print("✅ Connected to MongoDB successfully")
        
        # Create indexes
        await create_indexes()
    except Exception as e:
        print(f"❌ Error connecting to MongoDB: {e}")
        raise


async def close_mongo_connection():
    """Close database connection"""
    global client
    if client:
        client.close()
        print("✅ MongoDB connection closed")


async def get_database():
    """Get database instance"""
    return database


async def create_indexes():
    """Create all necessary indexes for optimal performance"""
    db = await get_database()
    
    # Properties collection indexes
    properties_collection = db.properties
    
    # Geo Search Index
    await properties_collection.create_index([("location.geo", "2dsphere")])
    
    # Full Text Search Index
    await properties_collection.create_index([("title", "text"), ("description", "text")])
    
    # Filter indexes
    await properties_collection.create_index([("transaction_type", 1), ("price", 1)])
    await properties_collection.create_index([("bedrooms", 1), ("bathrooms", 1)])
    await properties_collection.create_index([("owner_id", 1)])
    await properties_collection.create_index([("posted_at", -1)])
    
    # Users collection indexes
    users_collection = db.users
    
    # Handle email index - drop existing if it conflicts
    try:
        await users_collection.create_index([("email", 1)], unique=True)
    except Exception as e:
        if "IndexKeySpecsConflict" in str(e) or "already exists" in str(e).lower():
            # Drop existing index and recreate
            try:
                await users_collection.drop_index("email_1")
            except:
                pass
            await users_collection.create_index([("email", 1)], unique=True)
        else:
            raise
    
    # Handle phone index - drop existing if it conflicts (this is the problematic one)
    try:
        await users_collection.create_index([("phone", 1)], unique=True)  # Phone must be unique for OTP signup
    except Exception as e:
        if "IndexKeySpecsConflict" in str(e) or "already exists" in str(e).lower():
            # Drop existing index and recreate
            try:
                await users_collection.drop_index("phone_1")
            except:
                pass
            await users_collection.create_index([("phone", 1)], unique=True)
        else:
            raise
    
    # Reviews collection indexes
    reviews_collection = db.reviews
    await reviews_collection.create_index([("property_id", 1)])
    await reviews_collection.create_index([("user_id", 1)])
    
    # Inquiries collection indexes
    inquiries_collection = db.inquiries
    await inquiries_collection.create_index([("property_id", 1)])
    await inquiries_collection.create_index([("user_id", 1)])
    await inquiries_collection.create_index([("created_at", -1)])
    
    # Favorites collection indexes
    favorites_collection = db.favorites
    # Handle unique composite index - drop existing if it conflicts
    try:
        await favorites_collection.create_index([("user_id", 1), ("property_id", 1)], unique=True)
    except Exception as e:
        if "IndexKeySpecsConflict" in str(e) or "already exists" in str(e).lower():
            # Drop existing index and recreate
            try:
                await favorites_collection.drop_index("user_id_1_property_id_1")
            except:
                pass
            await favorites_collection.create_index([("user_id", 1), ("property_id", 1)], unique=True)
        else:
            raise
    await favorites_collection.create_index([("user_id", 1)])
    
    # Transactions collection indexes
    transactions_collection = db.transactions
    await transactions_collection.create_index([("property_id", 1)])
    await transactions_collection.create_index([("buyer_id", 1)])
    await transactions_collection.create_index([("seller_id", 1)])
    await transactions_collection.create_index([("created_at", -1)])
    
    # OTPs collection indexes
    otps_collection = db.otps
    await otps_collection.create_index([("phone_number", 1)])
    await otps_collection.create_index([("expires_at", 1)], expireAfterSeconds=0)  # TTL index to auto-delete expired OTPs
    
    print("✅ All indexes created successfully")

