"""
Vaastu Analysis API - backs the Vaastu UI flow.

Endpoints:
- POST /api/vaastu/manual-analyze  -> analyze manual room/direction mapping
- POST /api/vaastu/scan-analyze    -> analyze uploaded floorplan (stub, no real vision yet)

For now, the API returns a structured analysis payload that matches the UI needs
on `vaastu-result.php`. The actual Vaastu logic can be improved later without
changing the response shape.
"""

from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional, Dict, Any


router = APIRouter()


class VaastuRoomInput(BaseModel):
    room_name: str
    direction: str


class VaastuManualRequest(BaseModel):
    rooms: List[VaastuRoomInput]


def _base_sample_analysis(method: str) -> Dict[str, Any]:
    """Static sample payload used for both scan/manual flows."""
    return {
        "method": method,
        "score": 62,
        "directional_analysis": [
            {
                "direction": "NORTH",
                "icon": "mountain-sun",
                "text": "Abundance of open space and balconies in the North promotes prosperity.",
            },
            {
                "direction": "NORTH-EAST",
                "icon": "toilet",
                "text": (
                    "A toilet in the North-East is a major Vaastu defect, impacting health and mental peace."
                ),
            },
            {
                "direction": "SOUTH",
                "icon": "bed",
                "text": "Solid walls and a bedroom on the South side provide stability.",
            },
            {
                "direction": "SOUTH-WEST",
                "icon": "bed",
                "text": "Bedroom placement in the South-West corner is excellent for the head of the family.",
            },
            {
                "direction": "WEST",
                "icon": "fire-burner",
                "text": "The kitchen in the West is manageable, though it’s not the primary Agni (fire) zone.",
            },
            {
                "direction": "NORTH-WEST",
                "icon": "toilet-paper",
                "text": "Toilet and sit‑out in the North‑West are acceptable per Vayu corner principles.",
            },
        ],
        "room_scores": [
            {
                "name": "Master Bedroom (SW)",
                "score": 9,
                "max_score": 10,
                "tag": "good",
                "summary": "Perfectly placed in the South‑West with solid support.",
                "percent": 90,
            },
            {
                "name": "Kitchen (West)",
                "score": 5,
                "max_score": 10,
                "tag": "medium",
                "summary": "West placement is neutral; ideally kitchen sits in South‑East.",
                "percent": 50,
            },
            {
                "name": "Puja Room (NE)",
                "score": 8,
                "max_score": 10,
                "tag": "good",
                "summary": "Located towards North‑East, supporting spiritual harmony.",
                "percent": 80,
            },
            {
                "name": "Dining Area (Center)",
                "score": 7,
                "max_score": 10,
                "tag": "good",
                "summary": "Central placement is convenient and energetically balanced.",
                "percent": 70,
            },
        ],
        "defects": [
            {
                "title": "Ishanya Toilet Dosh",
                "text": (
                    "The presence of a toilet in the North‑East (Ishanya) corner is a severe violation, "
                    "believed to drain positive energy and cause health issues."
                ),
            },
            {
                "title": "Improper Puja Placement",
                "text": (
                    "The Puja/Store is located towards the South, which is the zone of Yama; "
                    "it should be moved to the Ishanya corner for spiritual growth."
                ),
            },
        ],
        "positives": [
            {
                "title": "Nairutya Stability",
                "text": (
                    "The heaviest room (Master Bedroom) is in the South‑West, ensuring financial and "
                    "emotional stability."
                ),
            },
            {
                "title": "Northern Ventilation",
                "text": (
                    "Large balconies in the North and West allow for good airflow and light, keeping "
                    "the home energetically active."
                ),
            },
        ],
        "recommendations": [
            {
                "title": "RELOCATE PUJA ROOM",
                "text": "Shift the Puja room to the North‑East corner of the house for better spiritual alignment.",
            },
            {
                "title": "NE TOILET REMEDY",
                "text": (
                    "If the toilet in the NE cannot be moved, keep it closed and use sea salt/Vaastu pyramids "
                    "to neutralize energy."
                ),
            },
            {
                "title": "KITCHEN COLOR PALETTE",
                "text": "Since the kitchen is in the West, use white or yellow tones to balance the elements.",
            },
        ],
    }


def _with_room_overrides(base: Dict[str, Any], rooms: Optional[List[VaastuRoomInput]]) -> Dict[str, Any]:
    """
    Light‑weight personalization: echo back the user's room/direction mapping so
    the frontend can show it or debug. Scoring stays sample‑based for now.
    """
    if rooms:
        base["rooms_input"] = [r.model_dump() for r in rooms]
    else:
        base["rooms_input"] = []
    return base


@router.post("/manual-analyze")
async def manual_analyze(payload: VaastuManualRequest) -> Dict[str, Any]:
    """
    Analyze Vaastu based on manual room/direction mapping.

    For now returns a structured sample analysis plus an echo of the input
    mapping under `rooms_input`. This keeps the frontend flow dynamic while
    allowing future improvement of the scoring logic without breaking clients.
    """
    analysis = _base_sample_analysis(method="manual")
    analysis = _with_room_overrides(analysis, payload.rooms)
    return {"success": True, "data": analysis}


@router.post("/scan-analyze")
async def scan_analyze(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Analyze an uploaded floor plan. The image is currently accepted and ignored;
    future versions can plug in real vision-based analysis.
    """
    # Read the first bytes to validate upload; ignore actual content for now.
    await file.read(1024)
    analysis = _base_sample_analysis(method="scan")
    return {"success": True, "data": analysis}

