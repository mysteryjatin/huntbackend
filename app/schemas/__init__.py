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
    # Basic info (maps to Step 1 - User & Property Info from UI)
    title: str  # Property Name in UI
    description: str  # Building Description in UI
    transaction_type: str = Field(
        ...,
        description="rent or sale - corresponds to 'Property For' in UI",
    )
    price: float

    # Core configuration / type
    property_category: Optional[str] = Field(
        default=None,
        description="Property Type group in UI: residential, commercial, agricultural",
    )
    property_subtype: Optional[str] = Field(
        default=None,
        description=(
            "Specific property option from UI: House or Kothi, Builder Floor, Villa, "
            "Service Apartment, Penthouse, Studio Apartment, Flats, Duplex, Plot/Land, etc."
        ),
    )

    # Features (maps to 'Property Features' UI screen)
    bedrooms: int
    bathrooms: int
    balconies: Optional[int] = None
    area_sqft: float
    furnishing: str = Field(
        ...,
        description="furnished, semi-furnished, or unfurnished",
    )
    floor_number: Optional[int] = Field(
        default=None,
        description="Current floor number of the property",
    )
    total_floors: Optional[int] = Field(
        default=None,
        description="Total number of floors in the building",
    )
    floors_allowed: Optional[int] = Field(
        default=None,
        description="Maximum floors allowed (useful for plots)",
    )
    open_sides: Optional[int] = Field(
        default=None,
        description="Number of open sides: 1, 2, 3, or 4",
    )
    facing: Optional[str] = Field(
        default=None,
        description=(
            "Facing of property: North, East, West, South, "
            "North-East, South-East, North-West, South-West"
        ),
    )
    store_room: Optional[bool] = Field(
        default=None,
        description="Whether the property has a store room (Yes/No in UI)",
    )
    servant_room: Optional[bool] = Field(
        default=None,
        description="Whether the property has a servant room (Yes/No in UI)",
    )

    # Possession & availability (Filter screen)
    possession_status: Optional[str] = Field(
        default=None,
        description="Possession status: 'under_construction' or 'ready_to_move'",
    )
    availability_month: Optional[int] = Field(
        default=None,
        ge=1,
        le=12,
        description="Availability month (1-12) for filter",
    )
    availability_year: Optional[int] = Field(
        default=None,
        ge=2000,
        le=2100,
        description="Availability year (e.g. 2025) for filter",
    )
    age_of_construction: Optional[str] = Field(
        default=None,
        description=(
            "Age of construction: 'new_construction', 'less_than_5_years', "
            "'5_to_10_years', '10_to_15_years', '15_to_20_years', '15_to_20_plus_years'"
        ),
    )

    # Location & media
    location: Location
    images: List[Image] = []
    amenities: List[str] = []

    # My Listing screen: listing status and view count (optional for backward compatibility)
    listing_status: Optional[str] = Field(
        default="active",
        description="Listing status: 'active', 'pending', or 'rejected'",
    )
    view_count: Optional[int] = Field(default=0, description="Number of views (for My Listing)")


class PropertyCreate(PropertyBase):
    owner_id: str


class PropertyUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    transaction_type: Optional[str] = None
    price: Optional[float] = None
    property_category: Optional[str] = None
    property_subtype: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    balconies: Optional[int] = None
    area_sqft: Optional[float] = None
    furnishing: Optional[str] = None
    floor_number: Optional[int] = None
    total_floors: Optional[int] = None
    floors_allowed: Optional[int] = None
    open_sides: Optional[int] = None
    facing: Optional[str] = None
    store_room: Optional[bool] = None
    servant_room: Optional[bool] = None
    possession_status: Optional[str] = None
    availability_month: Optional[int] = Field(None, ge=1, le=12)
    availability_year: Optional[int] = Field(None, ge=2000, le=2100)
    age_of_construction: Optional[str] = None
    location: Optional[Location] = None
    images: Optional[List[Image]] = None
    amenities: Optional[List[str]] = None
    listing_status: Optional[str] = Field(None, description="active, pending, or rejected")
    view_count: Optional[int] = None


class Property(PropertyBase):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    id: Optional[PyObjectId] = Field(None, alias="_id")
    owner_id: PyObjectId
    posted_at: datetime
    # My Listing response: saves = count of users who favorited this property (computed, not stored)
    saves: Optional[int] = Field(default=None, description="Favorite/save count (computed for My Listing)")


# User Schemas
class UserBase(BaseModel):
    name: str
    email: EmailStr
    phone: str
    user_type: str = Field(..., description="owner, buyer, or agent")
    subscription_plan_id: Optional[str] = Field(
        default="metal",
        description="Subscription plan: metal, bronze, silver, gold, platinum",
    )


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    user_type: Optional[str] = None
    subscription_plan_id: Optional[str] = Field(
        None,
        description="Subscription plan: metal, bronze, silver, gold, platinum",
    )


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


# Notification Schemas (Notification Screen)
# UI tabs: All | Property Alerts | Plan. Types map to tabs for filtering.
class NotificationBase(BaseModel):
    user_id: str = Field(..., description="User who receives this notification")
    type: str = Field(
        ...,
        description=(
            "Notification type for filtering: "
            "property_alerts tab: price_drop, new_listing, plot_available, price_alert, favorite, inquiry, listing_approved; "
            "plan tab: subscription, plan; "
            "others: system, etc."
        ),
    )
    title: str = Field(..., description="Notification title (e.g. 'Price dropped by $20k!')")
    body: str = Field(..., description="Notification message/description shown below title")
    read: bool = Field(default=False, description="Whether user has read it (unread = show green dot)")
    action_text: Optional[str] = Field(
        default=None,
        description="Button label (e.g. 'View Details >', 'Book Visit >', 'Renew Now >')",
    )
    action_url: Optional[str] = Field(
        default=None,
        description="Deep link or route when user taps the action button",
    )
    data: Optional[dict] = Field(
        default=None,
        description="Optional: property_id, inquiry_id, etc. for deep linking",
    )


class NotificationCreate(NotificationBase):
    pass


class NotificationUpdate(BaseModel):
    read: Optional[bool] = None
    action_text: Optional[str] = None
    action_url: Optional[str] = None


class Notification(NotificationBase):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    id: Optional[PyObjectId] = Field(None, alias="_id")
    created_at: datetime


class NotificationListResponse(BaseModel):
    notifications: List[Notification]
    total: int
    page: int
    limit: int
    total_pages: int
    has_next: bool
    has_prev: bool
    unread_count: int = Field(..., description="Total unread count for badge")


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


# Paginated Response Schema for Property Listing
class PropertyListResponse(BaseModel):
    properties: List[Property]
    total: int
    page: int
    limit: int
    total_pages: int
    has_next: bool
    has_prev: bool


# Order Schemas (Order History Screen)
class OrderBase(BaseModel):
    user_id: str
    plan_id: str = Field(..., description="metal, bronze, silver, gold, platinum")
    plan_name: str = Field(..., description="Metal, Bronze, Silver, Gold, Platinum")
    amount: float = Field(..., ge=0, description="Order amount in INR")
    currency: str = Field(default="INR")
    status: str = Field(
        default="pending",
        description="pending, success, invalid, cancelled, refunded",
    )


class OrderCreate(OrderBase):
    order_number: Optional[str] = Field(None, description="Display order ref e.g. 114107135936")


class OrderUpdate(BaseModel):
    status: Optional[str] = None


class Order(OrderBase):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    id: Optional[PyObjectId] = Field(None, alias="_id")
    order_number: Optional[str] = None
    created_at: datetime
    title: Optional[str] = Field(None, description="Display title for Order History card e.g. Owner-Gold -3500 / 114107135936")


class OrderListResponse(BaseModel):
    orders: List[Order]
    total: int
    page: int
    limit: int
    total_pages: int
    has_next: bool
    has_prev: bool


# Home Loan Application Schemas (Home Loan Screen)
class HomeLoanApplicationBase(BaseModel):
    loan_type: str = Field(
        ...,
        description="Home Loan, Commercial Loan, or Residential Loan",
    )
    name: str = Field(..., min_length=1)
    email: EmailStr
    phone: str = Field(..., min_length=1)
    address: str = Field(..., min_length=1)


class HomeLoanApplicationCreate(HomeLoanApplicationBase):
    user_id: Optional[str] = Field(None, description="Logged-in user ID if available")


class HomeLoanApplication(HomeLoanApplicationBase):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    id: Optional[PyObjectId] = Field(None, alias="_id")
    user_id: Optional[str] = None
    status: str = Field(default="submitted", description="submitted, contacted, in_progress, approved, rejected")
    created_at: datetime


# Property Cost Calculator (Property Cost Screen)
class AnnexureRowSchema(BaseModel):
    name: str
    price: float = Field(0, ge=0)
    units: float = Field(0, ge=0)


class PropertyCostCalculationBase(BaseModel):
    developer_name: Optional[str] = None
    project_name: Optional[str] = None
    property_type: str = Field(
        default="Residential",
        description="Residential, Commercial, or Others",
    )
    payment_plan: Optional[str] = Field(
        None,
        description="Construction Link Plan, Down Payment Plan, Flexi Plan, etc.",
    )
    location: Optional[str] = None
    size: Optional[str] = None
    unit_type: str = Field(
        default="Sqft",
        description="Sqft, Sqyrds, or Sqmtrs",
    )
    annexure_i: List[AnnexureRowSchema] = Field(default_factory=list)
    annexure_ii: List[AnnexureRowSchema] = Field(default_factory=list)
    annexure_iii: List[AnnexureRowSchema] = Field(default_factory=list)


class PropertyCostCalculationCreate(PropertyCostCalculationBase):
    user_id: Optional[str] = None


class PropertyCostCalculation(PropertyCostCalculationBase):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    id: Optional[PyObjectId] = Field(None, alias="_id")
    user_id: Optional[str] = None
    grand_total: float = Field(0, ge=0)
    created_at: datetime


# NRI Center - NRI Query Schemas
class NRIQueryBase(BaseModel):
    first_name: str = Field(..., min_length=1)
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: str = Field(..., min_length=1, description="Phone number (required)")
    state: str = Field(..., min_length=1)
    country: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class NRIQueryCreate(NRIQueryBase):
    user_id: Optional[str] = Field(None, description="Logged-in user ID if available")


class NRIQuery(NRIQueryBase):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    id: Optional[PyObjectId] = Field(None, alias="_id")
    user_id: Optional[str] = None
    created_at: datetime


# Post Your Requirement - Requirement Schemas
class RequirementBase(BaseModel):
    # Personal details
    iam: str = Field(..., description="Individual or Corporate")
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    mobile: Optional[str] = None
    country: Optional[str] = None
    state: Optional[str] = None
    resident_type: str = Field(
        default="Resident",
        description="Resident or Non Resident",
    )

    # Requirement intent
    want: str = Field(
        ...,
        description="To Buy, To Rent, or Other Services",
    )

    # Property info
    property_type: Optional[str] = Field(
        default=None,
        description="Residential, Commercial, or Agricultural",
    )
    option: Optional[str] = Field(
        default=None,
        description="House or Kothi, Builder Floor, Villa, Service Apartment, Penthouse, Studio Apartment, Flats, Duplex, Plot/Land",
    )
    property_state: Optional[str] = None
    property_city: Optional[str] = None
    locality: Optional[str] = None
    bhk: Optional[str] = Field(
        default=None,
        description="1 BHK, 2 BHK, 3 BHK, 4 BHK",
    )
    finishing: Optional[str] = Field(
        default=None,
        description="Bare Shell, Semi Furnished, Fully Furnished",
    )
    possession: Optional[str] = Field(
        default=None,
        description="Ready To Move or Under Construction",
    )
    min_area: Optional[float] = Field(default=None, ge=0)
    max_area: Optional[float] = Field(default=None, ge=0)
    min_price: Optional[float] = Field(default=None, ge=0)
    max_price: Optional[float] = Field(default=None, ge=0)
    payment_plan: Optional[str] = Field(
        default=None,
        description="CLP, SPP, FLEXI",
    )


class RequirementCreate(RequirementBase):
    user_id: Optional[str] = Field(None, description="Logged-in user ID if available")


class Requirement(RequirementBase):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    id: Optional[PyObjectId] = Field(None, alias="_id")
    user_id: Optional[str] = None
    status: str = Field(
        default="submitted",
        description="submitted, in_progress, matched, closed",
    )
    created_at: datetime
