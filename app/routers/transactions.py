from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from app.schemas import Transaction, TransactionCreate, TransactionUpdate
from app.database import get_database

router = APIRouter()


@router.post("/", response_model=Transaction, status_code=201)
async def create_transaction(transaction: TransactionCreate):
    """Create a new transaction"""
    db = await get_database()
    
    # Validate property exists
    if not ObjectId.is_valid(transaction.property_id):
        raise HTTPException(status_code=400, detail="Invalid property ID")
    property_exists = await db.properties.find_one({"_id": ObjectId(transaction.property_id)})
    if not property_exists:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Validate buyer exists
    if not ObjectId.is_valid(transaction.buyer_id):
        raise HTTPException(status_code=400, detail="Invalid buyer ID")
    buyer_exists = await db.users.find_one({"_id": ObjectId(transaction.buyer_id)})
    if not buyer_exists:
        raise HTTPException(status_code=404, detail="Buyer not found")
    
    # Validate seller exists
    if not ObjectId.is_valid(transaction.seller_id):
        raise HTTPException(status_code=400, detail="Invalid seller ID")
    seller_exists = await db.users.find_one({"_id": ObjectId(transaction.seller_id)})
    if not seller_exists:
        raise HTTPException(status_code=404, detail="Seller not found")
    
    transaction_dict = transaction.dict()
    transaction_dict["property_id"] = ObjectId(transaction_dict["property_id"])
    transaction_dict["buyer_id"] = ObjectId(transaction_dict["buyer_id"])
    transaction_dict["seller_id"] = ObjectId(transaction_dict["seller_id"])
    transaction_dict["created_at"] = datetime.utcnow()
    
    result = await db.transactions.insert_one(transaction_dict)
    created_transaction = await db.transactions.find_one({"_id": result.inserted_id})
    created_transaction["_id"] = str(created_transaction["_id"])
    created_transaction["property_id"] = str(created_transaction["property_id"])
    created_transaction["buyer_id"] = str(created_transaction["buyer_id"])
    created_transaction["seller_id"] = str(created_transaction["seller_id"])
    return created_transaction


@router.get("/", response_model=List[Transaction])
async def get_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    property_id: Optional[str] = None,
    buyer_id: Optional[str] = None,
    seller_id: Optional[str] = None,
    status: Optional[str] = None
):
    """Get all transactions with optional filters"""
    db = await get_database()
    query = {}
    
    if property_id:
        if not ObjectId.is_valid(property_id):
            raise HTTPException(status_code=400, detail="Invalid property ID")
        query["property_id"] = ObjectId(property_id)
    
    if buyer_id:
        if not ObjectId.is_valid(buyer_id):
            raise HTTPException(status_code=400, detail="Invalid buyer ID")
        query["buyer_id"] = ObjectId(buyer_id)
    
    if seller_id:
        if not ObjectId.is_valid(seller_id):
            raise HTTPException(status_code=400, detail="Invalid seller ID")
        query["seller_id"] = ObjectId(seller_id)
    
    if status:
        query["status"] = status
    
    cursor = db.transactions.find(query).skip(skip).limit(limit).sort("created_at", -1)
    transactions = await cursor.to_list(length=limit)
    
    for transaction in transactions:
        transaction["_id"] = str(transaction["_id"])
        transaction["property_id"] = str(transaction["property_id"])
        transaction["buyer_id"] = str(transaction["buyer_id"])
        transaction["seller_id"] = str(transaction["seller_id"])
    
    return transactions


@router.get("/{transaction_id}", response_model=Transaction)
async def get_transaction(transaction_id: str):
    """Get a specific transaction by ID"""
    db = await get_database()
    if not ObjectId.is_valid(transaction_id):
        raise HTTPException(status_code=400, detail="Invalid transaction ID")
    
    transaction = await db.transactions.find_one({"_id": ObjectId(transaction_id)})
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    transaction["_id"] = str(transaction["_id"])
    transaction["property_id"] = str(transaction["property_id"])
    transaction["buyer_id"] = str(transaction["buyer_id"])
    transaction["seller_id"] = str(transaction["seller_id"])
    return transaction


@router.put("/{transaction_id}", response_model=Transaction)
async def update_transaction(transaction_id: str, transaction_update: TransactionUpdate):
    """Update a transaction"""
    db = await get_database()
    if not ObjectId.is_valid(transaction_id):
        raise HTTPException(status_code=400, detail="Invalid transaction ID")
    
    update_data = transaction_update.dict(exclude_unset=True)
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    # If status is being updated to "completed", set completed_at
    if update_data.get("status") == "completed":
        update_data["completed_at"] = datetime.utcnow()
    
    result = await db.transactions.update_one(
        {"_id": ObjectId(transaction_id)},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    updated_transaction = await db.transactions.find_one({"_id": ObjectId(transaction_id)})
    updated_transaction["_id"] = str(updated_transaction["_id"])
    updated_transaction["property_id"] = str(updated_transaction["property_id"])
    updated_transaction["buyer_id"] = str(updated_transaction["buyer_id"])
    updated_transaction["seller_id"] = str(updated_transaction["seller_id"])
    return updated_transaction


@router.delete("/{transaction_id}", status_code=204)
async def delete_transaction(transaction_id: str):
    """Delete a transaction"""
    db = await get_database()
    if not ObjectId.is_valid(transaction_id):
        raise HTTPException(status_code=400, detail="Invalid transaction ID")
    
    result = await db.transactions.delete_one({"_id": ObjectId(transaction_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    return None



