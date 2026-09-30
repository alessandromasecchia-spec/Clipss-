from pathlib import Path


def _hex_to_ass(hex_color: str, alpha_hex: str = "00") -> str:
    h = (hex_color or "#FFFFFF").lstrip("#")
    if len(h) != 6:
        h = "FFFFFF"
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha_hex}{b}{g}{r}".upper()


def _alpha(op: float) -> str:
    op = max(0.0, min(1.0, op))
    return f"{int((1 - op) * 255):02X}"


def _ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = min(99, int(round((seconds - int(seconds)) * 100)))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _pos_margin(position: str, video_h: int):
    if position == "center":
        return 4, 0
    if position == "top":
        return 7, int(video_h * 0.08)
    if position == "upper":
        return 7, int(video_h * 0.28)
    if position == "lower":
        return 1, int(video_h * 0.18)
    return 1, int(video_h * 0.08)  # bottom


def _align_code(position: str, alignment: str) -> int:
    base, _ = _pos_margin(position, 1000)
    return base + {"left": 0, "center": 1, "right": 2}[alignment]


def _clean(t: str) -> str:
    return (t or "").strip().replace("\n", " ").replace("{", "(").replace("}", ")")


# 12 originali caption presets (functional, not copied from any app)
CAPTION_PRESETS = {
    "classic": {"mode": "static", "animation": "fade", "color": "#FFFFFF", "size": 58, "bold": True, "bg_mode": "none", "outline": 3},
    "bold": {"mode": "highlight", "animation": "fade", "color": "#FFFFFF", "highlight_color": "#FFE600", "size": 70, "bold": True, "outline": 5},
    "minimal": {"mode": "minimal", "animation": "fade", "color": "#FFFFFF", "size": 50, "bold": False, "outline": 1, "shadow": True},
    "gaming": {"mode": "glow", "animation": "word_pop", "color": "#00E5FF", "highlight_color": "#B4FF00", "size": 66, "bold": True, "outline": 4},
    "karaoke": {"mode": "karaoke", "animation": "karaoke", "color": "#FFFFFF", "highlight_color": "#22D3EE", "size": 64, "bold": True, "outline": 4},
    "highlight": {"mode": "highlight", "animation": "pop", "color": "#FFFFFF", "highlight_color": "#FACC15", "size": 66, "bold": True, "outline": 4},
    "pop": {"mode": "pop", "animation": "word_pop", "color": "#FFFFFF", "highlight_color": "#FB7185", "size": 66, "bold": True, "outline": 4},
    "scale": {"mode": "scale", "animation": "scale", "color": "#FFFFFF", "highlight_color": "#34D399", "size": 64, "bold": True, "outline": 4},
    "box": {"mode": "box", "animation": "fade", "color": "#FFFFFF", "size": 56, "bold": True, "bg_mode": "box", "bg_color": "#111111", "bg_opacity": 0.75, "outline": 0},
    "glow": {"mode": "glow", "animation": "fade", "color": "#FFFFFF", "highlight_color": "#A78BFA", "size": 62, "bold": True, "outline": 2},
    "hormozi": {"mode": "hormozi", "animation": "pop", "color": "#FFFFFF", "highlight_color": "#FFE600", "size": 84, "bold": True, "uppercase": True, "outline": 6},
    "clean": {"mode": "word_by_word", "animation": "fade", "color": "#FFFFFF", "size": 60, "bold": True, "outline": 3},
}

_PER_WORD = {"highlight", "pop", "scale", "glow", "hormozi"}
_INTENSITY = {"subtle": (120, 90), "normal": (180, 82), "strong": (260, 72)}


def _line_anim(style):
    fd, s0 = _INTENSITY.get(style.animation_intensity, _INTENSITY["normal"])
    a = style.animation
    if a == "none":
        return ""
    if a in ("pop", "scale", "bounce"):
        return f"\\fscx{s0}\\fscy{s0}\\t(0,{fd},\\fscx100\\fscy100)"
    # fade, slide_up, slide_down, typewriter, word_pop, karaoke -> gentle fade entrance
    return f"\\fad({fd},0)"


def _decorate(tok, active, style, hl):
    if not active:
        return tok
    if style.mode in ("pop", "scale", "word_pop"):
        return f"{{\\c{hl}\\fscx118\\fscy118}}{tok}{{\\r}}"
    if style.mode == "glow" or style.animation == "word_pop":
        return f"{{\\c{hl}\\blur{max(2, style.shadow_blur)}}}{tok}{{\\r}}"
    return f"{{\\c{hl}}}{tok}{{\\r}}"  # highlight / hormozi


def build_ass(lines: list, style, out_path: Path,
              video_w: int = 1080, video_h: int = 1920) -> Path:
    primary = _hex_to_ass(style.color)
    hl = _hex_to_ass(style.highlight_color)
    outline_col = _hex_to_ass(getattr(style, "outline_color", "#000000"))
    boxed = style.bg_mode in ("box", "rounded", "full") or style.background
    back_col = _hex_to_ass(style.bg_color, _alpha(style.bg_opacity)) if boxed else _hex_to_ass("#000000", "80")
    border_style = 3 if boxed else 1
    outline = max(0, style.outline)
    shadow = 2 if style.shadow else 0
    bold = -1 if (style.bold or style.font_weight >= 700) else 0
    _, margin_v = _pos_margin(style.position, video_h)
    align = _align_code(style.position, style.alignment)
    fsp = style.tracking or 0

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_w}
PlayResY: {video_h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style.font},{style.size},{primary},{hl},{outline_col},{back_col},{bold},0,0,0,100,100,{fsp},0,{border_style},{outline},{shadow},{align},70,70,{margin_v},1

[Events]
Format: Layer, Start, End, Style, MarginL, MarginR, Effect, Text
"""

    anim = _line_anim(style)
    glow = f"\\blur{max(2, style.shadow_blur)}" if style.mode == "glow" else ""
    prefix = ("{" + anim + glow + "}") if (anim or glow) else ""
    up = style.uppercase or style.mode == "hormozi"

    def txt(s):
        s = _clean(s)
        return s.upper() if up else s

    events = []
    for ln in lines:
        words = ln.get("words") or []
        full = txt(ln.get("text", ""))
        if not full:
            continue

        if style.mode == "karaoke" and words:
            parts = []
            for w in words:
                dur_cs = max(1, int(round((w["end"] - w["start"]) * 100)))
                parts.append(f"{{\\kf{dur_cs}}}{txt(w['word'])} ")
            body = f"{{\\1c{hl}\\2c{primary}}}" + "".join(parts).strip()
            events.append(f"Dialogue: 0,{_ts(ln['start'])},{_ts(ln['end'])},Default,,0,0,0,,{prefix}{body}")

        elif style.mode == "word_by_word" and words:
            n = len(words)
            for i, w in enumerate(words):
                we = words[i + 1]["start"] if i + 1 < n else ln["end"]
                events.append(f"Dialogue: 0,{_ts(w['start'])},{_ts(max(w['start']+0.12, we))},Default,,0,0,0,,{prefix}{txt(w['word'])}")

        elif style.mode in _PER_WORD and words:
            n = len(words)
            for i, w in enumerate(words):
                we = words[i + 1]["start"] if i + 1 < n else ln["end"]
                toks = [_decorate(txt(wj["word"]), j == i, style, hl) for j, wj in enumerate(words)]
                events.append(f"Dialogue: 0,{_ts(w['start'])},{_ts(max(w['start']+0.12, we))},Default,,0,0,0,,{prefix}{' '.join(toks)}")

        else:  # static / minimal / box
            events.append(f"Dialogue: 0,{_ts(ln['start'])},{_ts(ln['end'])},Default,,0,0,0,,{prefix}{full}")

    out_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return out_path


# kept for backward-compat import in pipeline
PRESET_DEFAULTS = {
    "classico": {"font": "DejaVu Sans"}, "bold": {"font": "DejaVu Sans"},
    "gaming": {"font": "DejaVu Sans"}, "minimal": {"font": "DejaVu Sans"},
}
