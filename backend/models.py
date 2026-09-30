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
    color: str = "#FFFFFF"
    highlight_color: str = "#FFE600"
    background: bool = False
    bg_color: str = "#000000"
    shadow: bool = True
    outline: int = 3
    bold: bool = True
    position: Literal["bottom", "center", "top"] = "bottom"
    alignment: Literal["left", "center", "right"] = "center"
    max_words_per_line: int = 4
    word_highlight: bool = False


class MusicSettings(BaseModel):
    name: str
    volume: float = 0.3
    start_offset: float = 0.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    loop: bool = True


class OverlaySettings(BaseModel):
    name: str
    x: float = 0.5      # fraction of free horizontal space (0=left,1=right)
    y: float = 0.08     # fraction of free vertical space (0=top,1=bottom)
    scale: float = 0.3  # width fraction of the video
    opacity: float = 1.0
    start: float = 0.0
    end: float = 0.0    # 0 = whole clip


class ClipSettings(BaseModel):
    aspect_ratio: Literal["9:16", "16:9", "1:1"] = "9:16"
    clip_duration: int = 30
    num_clips: int = 3
    subtitles: bool = True
    auto_zoom: bool = False
    auto_crop: bool = True
    face_tracking: bool = True
    audio_normalize: bool = True
    auto_find: bool = True
    subtitle_style: SubtitleStyle = Field(default_factory=SubtitleStyle)

    # --- Phase 6: Auto Edit Pro ---
    template: Optional[str] = None                     # podcast|talking_head|gaming|minimal
    silence_removal: Literal["off", "low", "medium", "high"] = "off"
    smart_zoom: Literal["off", "low", "medium", "high"] = "off"
    zoom_mode: Literal["normal", "punch_in", "punch_out"] = "normal"
    export_preset: Literal["social_hq", "social_small", "custom"] = "social_hq"
    export_crf: int = 20
    video_volume: float = 1.0
    fade_in: float = 0.0
    fade_out: float = 0.0
    music: Optional[MusicSettings] = None
    overlay: Optional[OverlaySettings] = None


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
    segments: Optional[list] = None


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
