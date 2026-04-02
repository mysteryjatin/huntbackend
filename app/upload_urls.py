"""
Single source of truth for uploaded image files and public URLs.

Env:
  HUNT_UPLOADS_DIR     — absolute path where images are stored (default: <backend>/uploads)
  PUBLIC_UPLOAD_BASE_URL — public origin for image URLs, e.g. https://huntindiainfra.com
                          (also accepts API_PUBLIC_ORIGIN). Used in API responses so clients
                          always get https://…/uploads/<uuid>.jpg even if DB has wrong paths.

Production: nginx should serve GET /uploads/ from the same directory as HUNT_UPLOADS_DIR
(or proxy to uvicorn). See docs/PROPERTY_IMAGES_NGINX.md.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

_UPLOAD_FILENAME_RE = re.compile(
    r"^([a-f0-9]{32}\.(?:jpe?g|jpeg|png|gif|webp|heic|heif))$", re.IGNORECASE
)


def get_uploads_directory() -> Path:
    env = (os.getenv("HUNT_UPLOADS_DIR") or "").strip()
    if env:
        return Path(env).resolve()
    root = Path(__file__).resolve().parent.parent
    return root / "uploads"


def get_public_origin() -> str:
    return (
        (os.getenv("PUBLIC_UPLOAD_BASE_URL") or "").strip()
        or (os.getenv("API_PUBLIC_ORIGIN") or "").strip()
        or "https://huntindiainfra.com"
    ).rstrip("/")


def extract_stored_upload_filename(url: Optional[str]) -> Optional[str]:
    """Return uuid.ext if *url* references an upload file, else None."""
    if not url:
        return None
    u = str(url).strip().replace("\\", "/")
    for seg in u.split("/"):
        seg = seg.split("?")[0]
        if _UPLOAD_FILENAME_RE.match(seg):
            return seg
    return None


def canonical_client_image_url(stored: Optional[str]) -> Optional[str]:
    """
    Absolute URL browsers should use: {PUBLIC_ORIGIN}/uploads/{uuid}.jpg
    Fixes DB values like https://host/uuid.jpg or bare uuid.jpg.
    """
    if not stored:
        return None
    origin = get_public_origin()
    fn = extract_stored_upload_filename(stored)
    if fn:
        return f"{origin}/uploads/{fn}"
    s = stored.strip()
    if s.startswith("http://") or s.startswith("https://"):
        return s
    if s.startswith("/uploads/"):
        return f"{origin}{s}"
    if s.startswith("/") and not s.startswith("//"):
        low = s.lower()
        if not low.startswith("/api/") and "uploads" not in low:
            tail = s.strip("/").split("/")[-1]
            if _UPLOAD_FILENAME_RE.match(tail):
                return f"{origin}/uploads/{tail}"
        return f"{origin}{s}"
    return s


def normalize_property_images_inplace(prop: Dict[str, Any]) -> None:
    """Mutate property dict: images[].url and top-level image_url if present."""
    imgs = prop.get("images")
    if isinstance(imgs, list):
        for i, item in enumerate(imgs):
            if isinstance(item, dict) and item.get("url"):
                c = canonical_client_image_url(item["url"])
                if c:
                    item["url"] = c
            elif isinstance(item, str):
                c = canonical_client_image_url(item)
                if c:
                    imgs[i] = c
    for key in ("image_url", "thumbnail_url"):
        if prop.get(key):
            c = canonical_client_image_url(prop[key])
            if c:
                prop[key] = c


def normalize_properties_list(properties: List[Dict[str, Any]]) -> None:
    for p in properties:
        normalize_property_images_inplace(p)


def upload_response_payload(filename: str) -> Dict[str, str]:
    """JSON for POST /api/upload/image."""
    path = f"/uploads/{filename}"
    origin = get_public_origin()
    return {
        "url": f"{origin}{path}",
        "path": path,
        "filename": filename,
    }
