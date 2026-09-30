import os
from pathlib import Path

ROOT_DIR = Path(__file__).parent
STORAGE_DIR = ROOT_DIR / "storage"
UPLOAD_DIR = STORAGE_DIR / "uploads"
OUTPUT_DIR = STORAGE_DIR / "outputs"
THUMB_DIR = STORAGE_DIR / "thumbs"
MODEL_DIR = STORAGE_DIR / "models"
ZIP_DIR = STORAGE_DIR / "zips"
WORK_DIR = STORAGE_DIR / "work"

for _d in (UPLOAD_DIR, OUTPUT_DIR, THUMB_DIR, MODEL_DIR, ZIP_DIR, WORK_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Allowed video inputs
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
ALLOWED_MIME_PREFIXES = ("video/", "application/octet-stream")

# Max upload size (bytes) - 2GB for a personal tool
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024

# Whisper
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "base")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")

# Target resolutions per aspect ratio
ASPECT_TARGETS = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
}
