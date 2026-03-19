"""
Public lead form: Contact Agent from Search Agent page.
Stores inquiries with agent reference, contact details, and consent.
"""
from fastapi import APIRouter, HTTPException
from bson import ObjectId
from datetime import datetime
from app.schemas import AgentContactLead, AgentContactLeadCreate
from app.database import get_database

router = APIRouter()


@router.post("/", response_model=AgentContactLead, status_code=201)
async def create_agent_contact_lead(data: AgentContactLeadCreate):
    """
    Submit contact request for an agent (guests allowed; no login required).
    """
    if not data.consent_accepted:
        raise HTTPException(status_code=400, detail="Consent is required to submit")

    db = await get_database()
    agent_oid = None
    if data.agent_id and str(data.agent_id).strip():
        aid = str(data.agent_id).strip()
        if not ObjectId.is_valid(aid):
            raise HTTPException(status_code=400, detail="Invalid agent ID")
        agent_doc = await db.users.find_one({"_id": ObjectId(aid)})
        if not agent_doc:
            raise HTTPException(status_code=404, detail="Agent not found")
        is_agent = agent_doc.get("user_type") == "agent" or agent_doc.get(
            "is_real_estate_agent"
        ) is True
        if not is_agent:
            raise HTTPException(status_code=400, detail="User is not a registered agent")
        agent_oid = ObjectId(aid)

    doc = {
        "agent_id": agent_oid,
        "agent_name": data.agent_name.strip(),
        "full_name": data.full_name.strip(),
        "email": str(data.email).strip().lower(),
        "phone_number": data.phone_number.strip(),
        "interest_type": (data.interest_type or "").strip() or None,
        "user_role": data.user_role,
        "consent_accepted": True,
        "created_at": datetime.utcnow(),
    }

    result = await db.agent_contact_leads.insert_one(doc)
    created = await db.agent_contact_leads.find_one({"_id": result.inserted_id})
    created["_id"] = str(created["_id"])
    if created.get("agent_id"):
        created["agent_id"] = str(created["agent_id"])
    else:
        created["agent_id"] = None
    return created
