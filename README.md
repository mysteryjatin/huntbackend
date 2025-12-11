# Hunt Property API

A complete FastAPI-based REST API for Hunt Property - Real Estate Management System with MongoDB.

## Features

- **Property Management**: CRUD operations for property listings
- **User Management**: User registration and profile management
- **Reviews System**: Property reviews and ratings
- **Inquiries**: Property inquiry management
- **Favorites**: Save favorite properties
- **Transactions**: Track property transactions
- **Advanced Search**: 
  - Text search (full-text search)
  - Geo-based search (location-based)
  - Filter by price, bedrooms, bathrooms, city, etc.

## Tech Stack

- **FastAPI**: Modern, fast web framework for building APIs
- **MongoDB**: NoSQL database with Motor (async driver)
- **Pydantic**: Data validation using Python type annotations

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. The MongoDB connection string is already configured in `app/database.py`

## Running the Application

Start the server:
```bash
uvicorn main:app --reload
```

The API will be available at:
- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

## API Endpoints

### Properties
- `POST /api/properties` - Create a new property
- `GET /api/properties` - Get all properties (with filters)
- `GET /api/properties/search` - Advanced search (text + geo)
- `GET /api/properties/{property_id}` - Get property by ID
- `PUT /api/properties/{property_id}` - Update property
- `DELETE /api/properties/{property_id}` - Delete property
- `GET /api/properties/owner/{owner_id}` - Get properties by owner

### Users
- `POST /api/users` - Create a new user
- `GET /api/users` - Get all users
- `GET /api/users/{user_id}` - Get user by ID
- `PUT /api/users/{user_id}` - Update user
- `DELETE /api/users/{user_id}` - Delete user

### Reviews
- `POST /api/reviews` - Create a review
- `GET /api/reviews` - Get all reviews (with filters)
- `GET /api/reviews/{review_id}` - Get review by ID
- `PUT /api/reviews/{review_id}` - Update review
- `DELETE /api/reviews/{review_id}` - Delete review
- `GET /api/reviews/property/{property_id}` - Get reviews for a property

### Inquiries
- `POST /api/inquiries` - Create an inquiry
- `GET /api/inquiries` - Get all inquiries (with filters)
- `GET /api/inquiries/{inquiry_id}` - Get inquiry by ID
- `PUT /api/inquiries/{inquiry_id}` - Update inquiry
- `DELETE /api/inquiries/{inquiry_id}` - Delete inquiry

### Favorites
- `POST /api/favorites` - Add to favorites
- `GET /api/favorites/user/{user_id}` - Get user favorites
- `GET /api/favorites/{favorite_id}` - Get favorite by ID
- `DELETE /api/favorites/{favorite_id}` - Remove favorite
- `DELETE /api/favorites/user/{user_id}/property/{property_id}` - Remove specific favorite

### Transactions
- `POST /api/transactions` - Create a transaction
- `GET /api/transactions` - Get all transactions (with filters)
- `GET /api/transactions/{transaction_id}` - Get transaction by ID
- `PUT /api/transactions/{transaction_id}` - Update transaction
- `DELETE /api/transactions/{transaction_id}` - Delete transaction

## Database Schema

The application uses MongoDB with the following collections:
- `users` - User accounts
- `properties` - Property listings
- `reviews` - Property reviews
- `inquiries` - Property inquiries
- `favorites` - User favorites
- `transactions` - Property transactions

### Property Schema Example
```json
{
  "_id": "ObjectId",
  "owner_id": "ObjectId",
  "title": "2 BHK Apartment",
  "description": "Spacious flat near sector 62",
  "transaction_type": "rent",
  "price": 18000,
  "bedrooms": 2,
  "bathrooms": 2,
  "area_sqft": 900,
  "furnishing": "semi-furnished",
  "location": {
    "address": "...",
    "locality": "Raj Nagar",
    "city": "Ghaziabad",
    "geo": {
      "type": "Point",
      "coordinates": [77.412, 28.673]
    }
  },
  "images": [{"url": "...", "is_primary": true}],
  "amenities": ["Lift", "Parking", "Power Backup"],
  "posted_at": "ISODate"
}
```

## Search Features

### Text Search
Search properties by title and description:
```
GET /api/properties/search?text=2 BHK metro
```

### Geo Search
Find properties near a location:
```
GET /api/properties/search?longitude=77.412&latitude=28.673&max_distance=5000
```

### Combined Search
Combine text and geo search with filters:
```
GET /api/properties/search?text=apartment&longitude=77.412&latitude=28.673&transaction_type=rent&min_price=10000&max_price=20000&min_bedrooms=2
```

## Indexes

The application automatically creates the following indexes on startup:
- Geo Search Index on `location.geo`
- Full Text Search Index on `title` and `description`
- Filter indexes on `transaction_type`, `price`, `bedrooms`, `bathrooms`
- Unique indexes on `email` (users) and composite indexes for favorites

## Notes

- Password hashing uses SHA256 (for production, consider using bcrypt)
- All timestamps are in UTC
- ObjectIds are automatically converted to strings in responses
- CORS is enabled for all origins (configure as needed for production)

## License

This project is part of the Hunt Property application.


