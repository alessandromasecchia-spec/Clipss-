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


def _clean(t: str) -> str:
    return (t or "").strip().replace("\n", " ").replace("{", "(").replace("}", ")")


def build_ass(lines: list, style, out_path: Path,
              video_w: int = 1080, video_h: int = 1920) -> Path:
    """Render caption `lines` (already in the OUTPUT timeline, 0-based) to an .ass
    file. Each line: {start, end, text, words:[{start,end,word}]}. When
    style.word_highlight is on, the currently spoken word is coloured using the
    real Whisper word timestamps."""
    primary = _hex_to_ass(style.color)
    hl = _hex_to_ass(style.highlight_color)
    outline_col = _hex_to_ass("#000000")
    back_col = _hex_to_ass(style.bg_color, "40")

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

    events = []
    for ln in lines:
        words = ln.get("words") or []
        text = _clean(ln.get("text", ""))
        if not text:
            continue
        if style.word_highlight and words:
            n = len(words)
            for i, w in enumerate(words):
                w_start = w["start"]
                w_end = words[i + 1]["start"] if i + 1 < n else ln["end"]
                if w_end <= w_start:
                    w_end = w_start + 0.15
                parts = []
                for j, wj in enumerate(words):
                    tok = _clean(wj["word"]).strip()
                    if j == i:
                        parts.append(f"{{\\c{hl}}}{tok}{{\\c{primary}}}")
                    else:
                        parts.append(tok)
                line_text = " ".join(parts)
                events.append(f"Dialogue: 0,{_ts(w_start)},{_ts(w_end)},Default,,0,0,0,,{line_text}")
        else:
            events.append(f"Dialogue: 0,{_ts(ln['start'])},{_ts(ln['end'])},Default,,0,0,0,,{text}")

    out_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return out_path
