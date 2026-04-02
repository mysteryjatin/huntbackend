"""
Vaastu Analysis API - backs the Vaastu UI flow.

Endpoints:
- POST /api/vaastu/manual-analyze  -> analyze manual room/direction mapping
- POST /api/vaastu/scan-analyze    -> validate + store uploaded floorplan session
- POST /api/vaastu/analyze-floorplan -> analyze stored floorplan with North direction
- POST /api/vaastu/chat           -> follow-up chat for remedies & guidance

The scan/analyze endpoints are implemented with OpenAI when `OPENAI_API_KEY` is set.
If OpenAI fails/missing, the API falls back to sample payloads so the UI flow keeps working.
"""

import aiohttp
import base64
import json
import os
import re
import uuid
from typing import List, Optional, Dict, Any, Union

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from fastapi import Body


router = APIRouter()

_VASTU_IMAGE_SESSIONS: Dict[str, Dict[str, Any]] = {}


def _get_openai_api_key() -> str:
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return key


def _has_openai_api_key() -> bool:
    return bool((os.getenv("OPENAI_API_KEY") or "").strip())


def _extract_first_json_object(text: str) -> Optional[Dict[str, Any]]:
    """
    Best-effort extraction of a JSON object from a model response.
    """
    if not text:
        return None
    try:
        # Sometimes the model returns JSON directly.
        loaded = json.loads(text)
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        loaded = json.loads(match.group(0))
        return loaded if isinstance(loaded, dict) else None
    except Exception:
        return None


async def _openai_chat_completion(
    *,
    api_key: str,
    model: str,
    messages: List[Dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 1000,
) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            body = await resp.json()
            if resp.status != 200:
                detail = body.get("error", {}).get("message") or body.get("detail") or str(body)
                raise HTTPException(status_code=resp.status, detail=detail)
            return body["choices"][0]["message"]["content"] or ""


def _vastu_chat_system_prompt(context: Optional[str]) -> str:
    """
    Same intent as the Flutter `VastuService.getVastuAnalysis()` system prompt.
    Keeps responses plain text and Vastu-only.
    """
    context_block = f"\n\nContext about the property: {context}" if context else ""
    return f"""You are an expert Vastu Shastra consultant with deep knowledge of traditional Indian architecture and design principles.
Your role is to provide accurate, helpful, and practical Vastu advice for homes and properties.

About You:
- You were created by Hunt Property Team, a leading real estate and property consulting company
- Hunt Property Team developed you to help people achieve harmony in their homes through Vastu Shastra
- If someone asks who made you or who created you, respond: "I was created by Hunt Property Team, a company dedicated to helping people find and harmonize their perfect homes through Vastu principles."

IMPORTANT - Scope of Expertise:
- You are specifically designed to answer questions related to Vastu Shastra, home design, property analysis, and architectural principles
- If someone asks questions that are NOT related to Vastu Shastra, home design, property analysis, or architecture, politely decline and redirect them
- When declining non-Vastu questions, respond in a warm and friendly manner like this: "I'm specifically designed to help with Vastu Shastra analysis for homes and properties. I'd love to assist you with any questions about Vastu principles, home design, floor plan analysis, or property-related Vastu guidance. For other topics, I may not be able to provide accurate information. How can I help you with your Vastu-related questions today?"

Guidelines:
- Provide specific, actionable Vastu recommendations
- Explain the reasoning behind each suggestion
- Consider directional placements (North, South, East, West, and their combinations)
- Address room placements, entrances, and structural elements
- Suggest remedies when there are Vastu doshas (defects)
- Be clear, concise, and culturally sensitive
- If asked about a floor plan, analyze it based on Vastu principles

IMPORTANT FORMATTING REQUIREMENTS:
- Use plain text only - NO markdown formatting (no #, *, **, _, etc.)
- NO emojis or special symbols
- Use simple line breaks and clear structure
- Use numbered lists with "1." format, not markdown lists
- Keep the response professional and clean{context_block}"""


def _vastu_vision_system_prompt() -> str:
    return """You are an expert Vastu Shastra consultant analyzing a floor plan image.

About You:
- You were created by Hunt Property Team, a leading real estate and property consulting company
- If asked who made you, respond: "I was created by Hunt Property Team."

IMPORTANT - Scope of Expertise:
- You are specifically designed to answer questions related to Vastu Shastra, home design, property analysis, and architectural principles
- If someone asks questions that are NOT related to Vastu Shastra, home design, property analysis, or architecture, politely decline and redirect them
- Be polite, understanding, and make the user feel valued even when redirecting

Analyze the image according to traditional Vastu principles considering:
- North direction is at: (provided by the user)
- Room placements and their Vastu compliance
- Directional alignments
- Entrance positioning
- Key Vastu elements

Provide a comprehensive analysis with scores and recommendations.

IMPORTANT:
- Use plain text only - NO markdown formatting (no #, *, **, _, etc.)
- NO emojis or special symbols
"""


def _expected_vastu_analysis_json_schema() -> str:
    return """Return ONLY a valid JSON object matching this schema (no extra keys, no markdown):
{
  "score": 0-100 number,
  "directional_analysis": [
    {"direction":"NORTH|NORTH-EAST|EAST|SOUTHEAST|SOUTH|SOUTH-WEST|WEST|NORTH-WEST",
     "icon":"mountain-sun|toilet|bed|fire-burner|toilet-paper",
     "text":"string"}
  ],
  "room_scores": [
    {"name":"string","score":0-10 number,"max_score":10,"tag":"good|medium|bad",
     "summary":"string","percent":0-100 number}
  ],
  "defects":[{"title":"string","text":"string"}],
  "positives":[{"title":"string","text":"string"}],
  "recommendations":[{"title":"string","text":"string"}]
}"""


async def _validate_floorplan_image_with_openai(*, api_key: str, image_base64: str) -> Dict[str, Any]:
    system_prompt = """You are an expert at identifying architectural floor plans and building layouts.
Your task is to determine if an uploaded image is a valid floor plan suitable for Vastu Shastra analysis.

A valid floor plan should contain:
- Room layouts and boundaries
- Walls, doors, windows
- Room labels or clear room divisions
- Architectural drawings or blueprints
- Clear structure that shows spatial relationships

Invalid images include:
- Photos of actual rooms or buildings (not floor plans)
- Random images, landscapes, or unrelated photos
- Blurry or unclear images
- Images without clear room divisions

Respond with:
- "valid": true if it's a clear floor plan
- "valid": false if it's not a floor plan
- "message": Brief explanation of your assessment"""

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Please analyze this image and determine if it is a valid floor plan suitable for Vastu Shastra analysis. Respond with JSON format: {\"valid\": true/false, \"message\": \"explanation\"}",
                },
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
            ],
        },
    ]

    content = await _openai_chat_completion(
        api_key=api_key,
        model="gpt-4o",
        messages=messages,
        temperature=0.3,
        max_tokens=200,
    )
    parsed = _extract_first_json_object(content) or {}
    return {
        "success": isinstance(parsed, dict),
        "isValid": bool(parsed.get("valid", False)),
        "message": str(parsed.get("message") or "Image validation completed"),
    }


async def _analyze_floorplan_with_openai_vision(
    *, api_key: str, image_base64: str, north_direction: str
) -> Dict[str, Any]:
    system_prompt = _vastu_vision_system_prompt()

    user_text = f"""Please analyze this floor plan image according to Vastu Shastra principles (North is at {north_direction}).

Provide:
1. Overall Vastu Score (X/100)
2. Directional Analysis for all 8 directions
3. Room Analysis with individual scores
4. Critical Issues to address
5. Positive Aspects that are correct
6. Recommendations for improvements

IMPORTANT: { _expected_vastu_analysis_json_schema() }"""

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
            ],
        },
    ]

    content = await _openai_chat_completion(
        api_key=api_key,
        model="gpt-4o",
        messages=messages,
        temperature=0.7,
        max_tokens=2000,
    )

    parsed = _extract_first_json_object(content)
    if not parsed:
        raise RuntimeError("Failed to parse structured Vaastu JSON from OpenAI response.")
    return parsed


def _analysis_to_chat_context(analysis: Optional[Dict[str, Any]]) -> str:
    if not analysis:
        return ""
    # Convert structured analysis to a compact string for prompts.
    return json.dumps(analysis, ensure_ascii=False)


class VaastuRoomInput(BaseModel):
    room_name: str
    direction: str


class VaastuManualRequest(BaseModel):
    rooms: List[VaastuRoomInput]


class VaastuAnalyzeFloorplanRequest(BaseModel):
    session_id: str
    north_direction: str
    north_image_side: Optional[str] = None


class VaastuChatRequest(BaseModel):
    message: str
    context: Optional[Union[str, Dict[str, Any]]] = None


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
                "direction": "EAST",
                "icon": "fire-burner",
                "text": "A well-planned East zone supports clarity, energy flow, and daily progress.",
            },
            {
                "direction": "SOUTH-EAST",
                "icon": "fire-burner",
                "text": "The South-East zone (Agni) is best supported with an appropriate kitchen/utility placement.",
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

    When `OPENAI_API_KEY` is set, calls OpenAI to generate a structured analysis
    matching the schema used by `vaastu-result.php`.
    """
    analysis: Dict[str, Any] = _base_sample_analysis(method="manual")
    has_key = _has_openai_api_key()

    try:
        api_key = _get_openai_api_key()

        rooms_lines = []
        for r in payload.rooms:
            room = (r.room_name or "").strip()
            direction = (r.direction or "").strip()
            if room and direction:
                rooms_lines.append(f"- {room}: Located in {direction} direction")

        rooms_text = "\n".join(rooms_lines) if rooms_lines else "(no room selections provided)"

        system_prompt = (
            "You are an expert Vastu Shastra consultant. "
            "Generate a complete Vaastu analysis using the provided room placements. "
            "IMPORTANT: Respond ONLY with a valid JSON object that matches the required schema. "
            "No markdown. No extra keys. No surrounding text."
        )

        user_text = (
            f"Room Placements and Directions:\n{rooms_text}\n\n"
            f"{_expected_vastu_analysis_json_schema()}"
        )

        content = await _openai_chat_completion(
            api_key=api_key,
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            temperature=0.5,
            max_tokens=1800,
        )

        parsed = _extract_first_json_object(content)
        if isinstance(parsed, dict):
            analysis = parsed
        else:
            raise RuntimeError("OpenAI manual analysis returned non-JSON response.")
    except Exception as e:
        # If OpenAI is configured, do not silently fallback to static data.
        if has_key:
            raise HTTPException(status_code=502, detail=f"Vaastu AI manual analysis failed: {e}")
        # No key: keep fallback sample mode so basic flow still works.

    analysis = _with_room_overrides(analysis, payload.rooms)
    return {"success": True, "data": analysis}


@router.post("/scan-analyze")
async def scan_analyze(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Validate and store an uploaded floor plan as an in-memory session.

    The follow-up endpoint `/api/vaastu/analyze-floorplan` uses the stored image
    to generate results after the user selects the North direction.
    """
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Convert to base64 once so downstream endpoints don't need the file stream.
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    # Validate with OpenAI when configured; otherwise assume valid to keep UI working.
    has_key = _has_openai_api_key()
    try:
        api_key = _get_openai_api_key()
        validation = await _validate_floorplan_image_with_openai(
            api_key=api_key,
            image_base64=image_base64,
        )
        if not validation.get("isValid", False):
            return {
                "success": False,
                "error": validation.get("message") or "Invalid floor plan image.",
                "data": {"isValid": False},
            }
    except Exception as e:
        # If key exists and validation fails, stop the flow (no static fallback).
        if has_key:
            raise HTTPException(status_code=502, detail=f"Vaastu image validation failed: {e}")
        # No key: fallback mode for basic flow.

    session_id = str(uuid.uuid4())
    _VASTU_IMAGE_SESSIONS[session_id] = {
        "image_base64": image_base64,
        "analysis": None,
    }

    return {"success": True, "data": {"session_id": session_id}}


@router.post("/analyze-floorplan")
async def analyze_floorplan(payload: VaastuAnalyzeFloorplanRequest) -> Dict[str, Any]:
    """
    Analyze a stored floorplan session with North direction.
    Returns a structured JSON payload that matches `vaastu-result.php` hydration.
    """
    session = _VASTU_IMAGE_SESSIONS.get(payload.session_id)
    if not session or not session.get("image_base64"):
        raise HTTPException(status_code=404, detail="Invalid or expired vaastu session_id.")

    image_base64 = session["image_base64"]
    north_direction = (payload.north_direction or "").strip()
    if not north_direction:
        raise HTTPException(status_code=400, detail="north_direction is required.")

    analysis: Dict[str, Any] = _base_sample_analysis(method="scan")
    has_key = _has_openai_api_key()
    try:
        api_key = _get_openai_api_key()
        analysis = await _analyze_floorplan_with_openai_vision(
            api_key=api_key,
            image_base64=image_base64,
            north_direction=north_direction if not payload.north_image_side else f"{north_direction} (facing {payload.north_image_side})",
        )
    except Exception as e:
        # If OpenAI is configured, surface the failure instead of returning static sample.
        if has_key:
            raise HTTPException(status_code=502, detail=f"Vaastu floorplan analysis failed: {e}")
        # No key: fallback sample for basic flow.

    # Store last analysis for chat context convenience.
    session["analysis"] = analysis
    _VASTU_IMAGE_SESSIONS[payload.session_id] = session
    return {"success": True, "data": analysis}


@router.post("/chat")
async def chat(payload: VaastuChatRequest = Body(...)) -> Dict[str, Any]:
    """
    Follow-up chat for remedies/guidance. Returns plain text.
    """
    message = (payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required.")

    # Context can be passed from frontend as structured analysis JSON.
    context_obj = payload.context
    context_text = ""
    if isinstance(context_obj, dict):
        context_text = json.dumps(context_obj, ensure_ascii=False)
    elif isinstance(context_obj, str):
        context_text = context_obj

    has_key = _has_openai_api_key()
    assistant_response = "Thanks for your question. I can help with Vastu Shastra and home design guidance."
    try:
        api_key = _get_openai_api_key()

        system_prompt = _vastu_chat_system_prompt(context_text if context_text else None)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ]

        assistant_response = await _openai_chat_completion(
            api_key=api_key,
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
        )
    except Exception as e:
        # If key exists, return error so frontend doesn't show non-dynamic canned chat.
        if has_key:
            raise HTTPException(status_code=502, detail=f"Vaastu chat failed: {e}")
        # No key: keep a minimal fallback response.
        assistant_response = f"{assistant_response}\n\n(Note: AI backend is using fallback mode.)"

    return {"success": True, "message": assistant_response}

