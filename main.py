from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import properties, users, reviews, inquiries, favorites, transactions, auth, filter_screen, subscription_plans, notifications, orders, financial_calculators
from app.database import connect_to_mongo, close_mongo_connection

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

