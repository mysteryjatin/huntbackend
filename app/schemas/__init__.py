from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_serializer
from pydantic_core import core_schema
from typing import Optional, List, Annotated, Union
from datetime import datetime
from bson import ObjectId


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type, handler
    ) -> core_schema.CoreSchema:
        return core_schema.union_schema([
            core_schema.is_instance_schema(ObjectId),
            core_schema.no_info_after_validator_function(
                cls._validate_str,
                core_schema.str_schema(),
            ),
        ])
    
    @classmethod
    def _validate_str(cls, v: str) -> ObjectId:
        if ObjectId.is_valid(v):
            return ObjectId(v)
        raise ValueError("Invalid ObjectId string")
    
    def __str__(self):
        return str(ObjectId(self))


# Location Schema
class Location(BaseModel):
    address: str
    locality: str
    city: str
    geo: dict = Field(..., description="GeoJSON Point: {type: 'Point', coordinates: [longitude, latitude]}")


# Image Schema
class Image(BaseModel):
    url: str
    is_primary: bool = False


# Property Schemas
class PropertyBase(BaseModel):
    title: str
    description: str
    transaction_type: str = Field(..., description="rent or sale")
    price: float
    bedrooms: int
    bathrooms: int
    area_sqft: float
    furnishing: str = Field(..., description="furnished, semi-furnished, or unfurnished")
    location: Location
    images: List[Image] = []
    amenities: List[str] = []


class PropertyCreate(PropertyBase):
    owner_id: str


class PropertyUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    transaction_type: Optional[str] = None
    price: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    area_sqft: Optional[float] = None
    furnishing: Optional[str] = None
    location: Optional[Location] = None
    images: Optional[List[Image]] = None
    amenities: Optional[List[str]] = None


class Property(PropertyBase):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    id: Optional[PyObjectId] = Field(None, alias="_id")
    owner_id: PyObjectId
    posted_at: datetime


# User Schemas
class UserBase(BaseModel):
    name: str
    email: EmailStr
    phone: str
    user_type: str = Field(..., description="owner, buyer, or agent")


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    user_type: Optional[str] = None


class User(UserBase):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    id: Optional[PyObjectId] = Field(None, alias="_id")
    created_at: datetime


# Review Schemas
class ReviewBase(BaseModel):
    property_id: str
    user_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: str


class ReviewCreate(ReviewBase):
    pass


class ReviewUpdate(BaseModel):
    rating: Optional[int] = Field(None, ge=1, le=5)
    comment: Optional[str] = None


class Review(ReviewBase):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    id: Optional[PyObjectId] = Field(None, alias="_id")
    created_at: datetime


# Inquiry Schemas
class InquiryBase(BaseModel):
    property_id: str
    user_id: str
    message: str
    contact_preference: str = Field(..., description="phone or email")


class InquiryCreate(InquiryBase):
    pass


class InquiryUpdate(BaseModel):
    message: Optional[str] = None
    contact_preference: Optional[str] = None
    status: Optional[str] = Field(None, description="pending, responded, closed")


class Inquiry(InquiryBase):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    id: Optional[PyObjectId] = Field(None, alias="_id")
    status: str = "pending"
    created_at: datetime


# Favorite Schemas
class FavoriteBase(BaseModel):
    user_id: str
    property_id: str


class FavoriteCreate(FavoriteBase):
    pass


class Favorite(FavoriteBase):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    id: Optional[PyObjectId] = Field(None, alias="_id")
    created_at: datetime


# Transaction Schemas
class TransactionBase(BaseModel):
    property_id: str
    buyer_id: str
    seller_id: str
    transaction_type: str = Field(..., description="rent or sale")
    amount: float
    status: str = Field(default="pending", description="pending, completed, cancelled")


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    status: Optional[str] = None
    amount: Optional[float] = None


class Transaction(TransactionBase):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    id: Optional[PyObjectId] = Field(None, alias="_id")
    created_at: datetime
    completed_at: Optional[datetime] = None


# Search Schemas
class GeoSearchParams(BaseModel):
    longitude: float
    latitude: float
    max_distance: int = Field(default=5000, description="Maximum distance in meters")


class PropertySearchParams(BaseModel):
    transaction_type: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_bedrooms: Optional[int] = None
    min_bathrooms: Optional[int] = None
    city: Optional[str] = None
    locality: Optional[str] = None
    furnishing: Optional[str] = None
    text_search: Optional[str] = None
    geo_search: Optional[GeoSearchParams] = None

