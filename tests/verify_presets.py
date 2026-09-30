"""Render each caption preset onto a real clip via build_ass + FFmpeg and
extract a frame at the moment a word is 'active', proving preset -> config ->
ASS -> FFmpeg -> MP4 produces visibly different output."""
import subprocess, sys
from pathlib import Path

sys.path.insert(0, "/app/backend")
from models import SubtitleStyle
from subtitles import build_ass

OUT = Path("/app/tests/preset_frames")
OUT.mkdir(exist_ok=True)

# Mirror of the frontend PRESETS payload (what the UI sends to the backend).
PRESETS = {
    "classic":  dict(mode="static",    animation="fade", size=58, color="#FFFFFF", bold=True, outline=3, shadow=True, background=False),
    "highlight":dict(mode="highlight", animation="pop",  size=66, color="#FFFFFF", highlight_color="#FACC15", bold=True, outline=4, shadow=True, background=False),
    "glow":     dict(mode="glow",      animation="fade", size=62, color="#FFFFFF", highlight_color="#A78BFA", bold=True, outline=2, shadow=True, background=False),
    "scale":    dict(mode="scale",     animation="scale",size=64, color="#FFFFFF", highlight_color="#34D399", bold=True, outline=4, shadow=True, background=False),
    "box":      dict(mode="box",       animation="fade", size=56, color="#FFFFFF", bold=True, outline=0, shadow=False, background=True, bg_color="#111111", bg_mode="box", bg_opacity=0.75),
    "hormozi":  dict(mode="hormozi",   animation="pop",  size=84, color="#FFFFFF", highlight_color="#FFE600", bold=True, uppercase=True, outline=6, shadow=True, background=False),
}

# One line, three words with real-style timestamps. "GET" active at t=0.5s.
LINES = [{
    "start": 0.0, "end": 2.0, "text": "TO GET STARTED",
    "words": [
        {"start": 0.0,  "end": 0.35, "word": "TO"},
        {"start": 0.35, "end": 0.9,  "word": "GET"},
        {"start": 0.9,  "end": 2.0,  "word": "STARTED"},
    ],
}]

TW, TH = 1080, 1920

def esc(p): return str(p).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

for key, fields in PRESETS.items():
    style = SubtitleStyle(preset=key, position="center", **fields)
    ass = OUT / f"{key}.ass"
    build_ass(LINES, style, ass, TW, TH)
    mp4 = OUT / f"{key}.mp4"
    # 2s solid slate background clip, burn captions
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x1e293b:s={TW}x{TH}:d=2:r=25",
        "-vf", f"subtitles={esc(ass)}",
        "-frames:v", "50", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        str(mp4),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[{key}] FFMPEG FAIL:\n{r.stderr[-800:]}")
        continue
    # extract frame at t=0.6 (GET active)
    frame = OUT / f"{key}.png"
    subprocess.run(["ffmpeg", "-y", "-ss", "0.6", "-i", str(mp4), "-frames:v", "1", str(frame)],
                   capture_output=True)
    print(f"[{key}] OK  ass={ass.stat().st_size}b  mp4={mp4.stat().st_size}b  frame={'yes' if frame.exists() else 'NO'}")

print("done ->", OUT)
