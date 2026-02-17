"""
Image upload for property listings.
Saves files to uploads/ and returns a URL path that the app can use in property.images.
"""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter()

# Directory to store uploads (relative to project root)
UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_SIZE_MB = 10


def _ensure_uploads_dir():
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


@router.post("/image")
async def upload_image(file: UploadFile = File(...)):
    """
    Upload a single image. Returns { "url": "/uploads/<filename>" }.
    Frontend should prepend base URL when displaying or sending in create property (e.g. baseUrl + url).
    """
    if not file.filename or not _allowed_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail="Invalid file. Allowed: jpg, jpeg, png, gif, webp",
        )

    _ensure_uploads_dir()
    ext = Path(file.filename).suffix.lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOADS_DIR / unique_name

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

    return {"url": f"/uploads/{unique_name}"}
