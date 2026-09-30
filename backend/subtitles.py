from pathlib import Path


def _hex_to_ass(hex_color: str, alpha_hex: str = "00") -> str:
    h = hex_color.lstrip("#")
    if len(h) != 6:
        h = "FFFFFF"
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha_hex}{b}{g}{r}".upper()


def _ts(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs == 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _alignment_code(position: str, alignment: str) -> int:
    base = {"bottom": 1, "center": 4, "top": 7}[position]
    offset = {"left": 0, "center": 1, "right": 2}[alignment]
    return base + offset


PRESET_DEFAULTS = {
    "classico": {"font": "DejaVu Sans", "size": 58, "color": "#FFFFFF", "outline": 3,
                 "shadow": True, "bold": False, "background": False},
    "bold": {"font": "DejaVu Sans", "size": 68, "color": "#FFFFFF", "outline": 4,
             "shadow": True, "bold": True, "background": False},
    "gaming": {"font": "DejaVu Sans", "size": 66, "color": "#00E5FF", "outline": 5,
               "shadow": True, "bold": True, "background": False},
    "minimal": {"font": "DejaVu Sans", "size": 52, "color": "#FFFFFF", "outline": 1,
                "shadow": False, "bold": False, "background": False},
}


def build_ass(segments: list, style, clip_start: float, clip_end: float,
              out_path: Path, video_w: int = 1080, video_h: int = 1920) -> Path:
    """Create an .ass subtitle file for the clip. `segments` are absolute-timed
    transcription segments; timestamps are shifted to be relative to clip_start."""
    primary = _hex_to_ass(style.color)
    outline_col = _hex_to_ass("#000000")
    back_col = _hex_to_ass(style.bg_color, "40")  # semi-transparent box

    border_style = 3 if style.background else 1
    outline = max(0, style.outline)
    shadow = 2 if style.shadow else 0
    bold = -1 if style.bold else 0
    align = _alignment_code(style.position, style.alignment)
    margin_v = int(video_h * 0.10) if style.position != "center" else 0

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_w}
PlayResY: {video_h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style.font},{style.size},{primary},{primary},{outline_col},{back_col},{bold},0,0,0,100,100,0,0,{border_style},{outline},{shadow},{align},60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, MarginL, MarginR, Effect, Text
"""

    lines = []
    for seg in segments:
        s = seg["start"]
        e = seg["end"]
        if e <= clip_start or s >= clip_end:
            continue
        rs = max(0.0, s - clip_start)
        re_ = min(clip_end, e) - clip_start
        text = (seg.get("text") or "").strip().replace("\n", " ")
        if not text:
            continue
        # ASS escape
        text = text.replace("{", "(").replace("}", ")")
        lines.append(f"Dialogue: 0,{_ts(rs)},{_ts(re_)},Default,,0,0,0,,{text}")

    out_path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return out_path
