import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routers import (
    properties,
    users,
    reviews,
    inquiries,
    favorites,
    transactions,
    auth,
    filter_screen,
    subscription_plans,
    notifications,
    orders,
    financial_calculators,
    home_loan,
    property_cost,
    nri_queries,
    requirements,
    upload,
    vaastu,
    home as home_router,
    agent_contact_leads,
    channel_partner_applications,
    career_applications,
    success_stories,
)
from app.database import connect_to_mongo, close_mongo_connection
from app.upload_urls import get_uploads_directory

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Hunt Property API",
    description="Complete API for Hunt Property - Real Estate Management System",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(properties.router, prefix="/api/properties", tags=["Properties"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(reviews.router, prefix="/api/reviews", tags=["Reviews"])
app.include_router(inquiries.router, prefix="/api/inquiries", tags=["Inquiries"])
app.include_router(favorites.router, prefix="/api/favorites", tags=["Favorites"])
app.include_router(transactions.router, prefix="/api/transactions", tags=["Transactions"])
app.include_router(filter_screen.router, prefix="/api/filter-screen", tags=["Filter Screen"])
app.include_router(subscription_plans.router, prefix="/api/subscription-plans", tags=["Subscription Plans"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])
app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])
app.include_router(financial_calculators.router, prefix="/api/financial-calculators", tags=["Financial Calculators"])
app.include_router(home_loan.router, prefix="/api/home-loan-applications", tags=["Home Loan"])
app.include_router(property_cost.router, prefix="/api/property-cost-calculations", tags=["Property Cost"])
app.include_router(nri_queries.router, prefix="/api/nri-queries", tags=["NRI Center"])
app.include_router(requirements.router, prefix="/api/requirements", tags=["Requirements"])
app.include_router(upload.router, prefix="/api/upload", tags=["Upload"])
app.include_router(vaastu.router, prefix="/api/vaastu", tags=["Vaastu"])
app.include_router(home_router.router, prefix="/api/home", tags=["Home"])
app.include_router(
    agent_contact_leads.router,
    prefix="/api/agent-contact-leads",
    tags=["Agent Contact Leads"],
)
app.include_router(
    channel_partner_applications.router,
    prefix="/api/channel-partner-applications",
    tags=["Channel Partner Applications"],
)
app.include_router(
    career_applications.router,
    prefix="/api/career-applications",
    tags=["Career Applications"],
)
app.include_router(
    success_stories.router,
    prefix="/api/success-stories",
    tags=["Success Stories"],
)

# Serve uploaded images at /uploads/ (same dir as upload router; override with HUNT_UPLOADS_DIR)
uploads_dir = get_uploads_directory()
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")
logger.info("Serving /uploads/ from %s", uploads_dir)


@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()


@app.on_event("shutdown")
async def shutdown_event():
    await close_mongo_connection()


@app.get("/")
async def root():
    return {
        "message": "Welcome to Hunt Property API",
        "version": "1.0.0",
        "docs": "/docs"
    }

