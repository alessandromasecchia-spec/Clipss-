import asyncio
import logging
import re

logger = logging.getLogger(__name__)

# level -> (threshold_db, min_silence_seconds, padding_seconds)
LEVELS = {
    "low": (-30, 0.80, 0.15),
    "medium": (-30, 0.50, 0.10),
    "high": (-35, 0.35, 0.06),
}

_RE_START = re.compile(r"silence_start:\s*(-?[\d.]+)")
_RE_END = re.compile(r"silence_end:\s*(-?[\d.]+)")


async def detect_silences(video_path, start: float, dur: float, level: str):
    """Run ffmpeg silencedetect on the clip region [start, start+dur].
    Returns list of (s, e) silence intervals RELATIVE to the clip (0-based)."""
    thr, min_sil, _pad = LEVELS[level]
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats",
        "-ss", f"{start}", "-t", f"{dur}", "-i", str(video_path),
        "-af", f"silencedetect=noise={thr}dB:d={min_sil}",
        "-f", "null", "-",
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _o, err = await proc.communicate()
    text = err.decode("utf-8", "ignore")

    silences = []
    cur = None
    for line in text.splitlines():
        ms = _RE_START.search(line)
        if ms:
            cur = max(0.0, float(ms.group(1)))
            continue
        me = _RE_END.search(line)
        if me and cur is not None:
            e = min(dur, float(me.group(1)))
            if e > cur:
                silences.append((cur, e))
            cur = None
    if cur is not None:
        silences.append((cur, dur))
    return silences


def compute_keep_intervals(dur: float, silences: list, level: str):
    """Return keep intervals (voiced parts) with small padding preserved around cuts."""
    if not silences:
        return [(0.0, dur)]
    _thr, _min, pad = LEVELS[level]
    # shrink each silence by padding on both sides so we keep a natural margin
    trimmed = []
    for s, e in silences:
        s2 = s + pad
        e2 = e - pad
        if e2 - s2 > 0.05:
            trimmed.append((s2, e2))
    if not trimmed:
        return [(0.0, dur)]

    keeps = []
    prev = 0.0
    for s, e in trimmed:
        if s > prev + 0.05:
            keeps.append((round(prev, 3), round(s, 3)))
        prev = e
    if dur > prev + 0.05:
        keeps.append((round(prev, 3), round(dur, 3)))
    return keeps or [(0.0, dur)]


def build_remap(keep_intervals: list):
    """Return (remap_fn, total_dur). remap_fn(t) maps a clip-relative input time
    to the output (post-cut) timeline, or None if t falls in a removed region."""
    spans = []
    offset = 0.0
    for a, b in keep_intervals:
        spans.append((a, b, offset))
        offset += (b - a)
    total = offset

    def remap(t):
        for a, b, off in spans:
            if a - 1e-6 <= t <= b + 1e-6:
                return off + (min(max(t, a), b) - a)
        return None

    return remap, total
