"""
Image upload for property listings.
Saves under HUNT_UPLOADS_DIR (default: backend/uploads). Same folder must be served at /uploads/ in production (nginx).
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.upload_urls import get_uploads_directory, upload_response_payload

router = APIRouter()

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_SIZE_MB = 10


def _ensure_uploads_dir():
    get_uploads_directory().mkdir(parents=True, exist_ok=True)


def _allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


@router.post("/image")
async def upload_image(file: UploadFile = File(...)):
    """
    Upload a single image. Returns url (absolute …/uploads/…), path (/uploads/…), filename.
    """
    if not file.filename or not _allowed_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail="Invalid file. Allowed: jpg, jpeg, png, gif, webp",
        )

    _ensure_uploads_dir()
    ext = Path(file.filename).suffix.lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = get_uploads_directory() / unique_name

    try:
        contents = await file.read()
        if len(contents) > MAX_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max {MAX_SIZE_MB}MB",
            )
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        if file_path.exists():
            file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    return upload_response_payload(unique_name)
