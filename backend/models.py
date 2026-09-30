import uuid
from datetime import datetime, timezone
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


class SubtitleStyle(BaseModel):
    preset: Literal["classico", "bold", "gaming", "minimal"] = "bold"
    font: str = "DejaVu Sans"
    size: int = 64
    color: str = "#FFFFFF"          # primary text
    background: bool = False
    bg_color: str = "#000000"
    shadow: bool = True
    outline: int = 3
    bold: bool = True
    position: Literal["bottom", "center", "top"] = "bottom"
    alignment: Literal["left", "center", "right"] = "center"


class ClipSettings(BaseModel):
    aspect_ratio: Literal["9:16", "16:9", "1:1"] = "9:16"
    clip_duration: int = 30            # seconds (used when auto_find or uniform split)
    num_clips: int = 3
    subtitles: bool = True
    auto_zoom: bool = False
    auto_crop: bool = True
    face_tracking: bool = True
    audio_normalize: bool = True
    auto_find: bool = True             # find best moments via transcription
    subtitle_style: SubtitleStyle = Field(default_factory=SubtitleStyle)


class ClipInfo(BaseModel):
    index: int
    start: float
    end: float
    title: str = ""
    reason: str = ""
    status: Literal["queued", "processing", "completed", "failed"] = "queued"
    progress: int = 0
    filename: Optional[str] = None
    error: Optional[str] = None


class Project(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str
    original_filename: str
    stored_filename: str
    ext: str
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    size_bytes: int = 0
    has_audio: bool = True
    created_at: str = Field(default_factory=now_iso)
    clip_count: int = 0
    segments: Optional[list] = None    # cached transcription segments


class Job(BaseModel):
    id: str = Field(default_factory=new_id)
    project_id: str
    status: Literal["queued", "processing", "completed", "failed"] = "queued"
    progress: int = 0
    stage: str = "In coda"
    settings: ClipSettings
    clips: List[ClipInfo] = Field(default_factory=list)
    error: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)
    zip_filename: Optional[str] = None
