import asyncio
import json
import re
import shutil
from pathlib import Path

from config import THUMB_DIR


def sanitize_filename(name: str) -> str:
    """Keep only a safe base name; strip any path components."""
    name = Path(name).name  # removes directory traversal
    name = name.replace("\x00", "")
    # keep letters, numbers, space, dash, underscore, dot
    base = re.sub(r"[^A-Za-z0-9._\- ]+", "_", name).strip()
    base = re.sub(r"_+", "_", base)
    return base or "video"


async def _run(cmd: list) -> tuple[int, bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    return proc.returncode, out, err


async def probe_video(path: Path) -> dict:
    """Return metadata using ffprobe. Raises ValueError on failure."""
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    code, out, err = await _run(cmd)
    if code != 0:
        raise ValueError(f"ffprobe fallito: {err.decode('utf-8', 'ignore')[:300]}")
    data = json.loads(out.decode("utf-8", "ignore"))

    v_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if v_stream is None:
        raise ValueError("Nessuna traccia video trovata nel file.")

    fmt = data.get("format", {})
    duration = float(fmt.get("duration") or v_stream.get("duration") or 0.0)
    width = int(v_stream.get("width") or 0)
    height = int(v_stream.get("height") or 0)

    # fps
    fps = 0.0
    rate = v_stream.get("avg_frame_rate") or v_stream.get("r_frame_rate") or "0/0"
    try:
        num, den = rate.split("/")
        fps = round(float(num) / float(den), 2) if float(den) else 0.0
    except Exception:
        fps = 0.0

    return {
        "duration": round(duration, 2),
        "width": width,
        "height": height,
        "fps": fps,
        "has_audio": a_stream is not None,
        "size_bytes": path.stat().st_size,
    }


async def generate_thumbnail(video_path: Path, project_id: str, at_sec: float = 1.0) -> str:
    out = THUMB_DIR / f"{project_id}.jpg"
    cmd = [
        "ffmpeg", "-y", "-ss", str(max(0.0, at_sec)), "-i", str(video_path),
        "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "4", str(out),
    ]
    code, _, err = await _run(cmd)
    if code != 0 or not out.exists():
        # fallback at 0
        cmd[3] = "0"
        await _run(cmd)
    return out.name if out.exists() else ""


def free_disk_bytes(path: Path) -> int:
    total, used, free = shutil.disk_usage(path)
    return free
