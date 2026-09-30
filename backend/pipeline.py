import asyncio
import logging
import re
import zipfile
from pathlib import Path

from config import ASPECT_TARGETS, OUTPUT_DIR, ZIP_DIR
from face_crop import compute_crop, detect_face_center_x
from models import ClipInfo
from subtitles import PRESET_DEFAULTS, build_ass
from transcription import transcribe

logger = logging.getLogger(__name__)

KEYWORDS = [
    "perché", "perche", "come", "segreto", "importante", "mai", "sempre",
    "gratis", "errore", "migliore", "peggiore", "incredibile", "attenzione",
    "problema", "soluzione", "trucco", "consiglio", "risultato", "soldi",
    "tempo", "vita", "successo", "primo", "ultimo", "nessuno", "tutti",
]


async def _run_ffmpeg(cmd: list) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _out, err = await proc.communicate()
    return proc.returncode, err.decode("utf-8", "ignore")


async def extract_audio(video_path: Path, out_wav: Path) -> bool:
    cmd = ["ffmpeg", "-y", "-i", str(video_path), "-vn", "-ac", "1",
           "-ar", "16000", "-f", "wav", str(out_wav)]
    code, err = await _run_ffmpeg(cmd)
    if code != 0:
        logger.error("Estrazione audio fallita: %s", err[:300])
        return False
    return out_wav.exists()


def _score_window(text: str, dur: float, target: float) -> tuple[float, str]:
    t = text.lower()
    words = t.split()
    wc = len(words)
    reasons = []
    score = 0.0

    q = text.count("?")
    if q:
        score += 2.0 * q
        reasons.append("contiene una domanda")
    ex = text.count("!")
    if ex:
        score += 1.2 * ex
        reasons.append("affermazione forte")

    kw = sum(1 for w in words if w.strip(".,!?;:") in KEYWORDS)
    if kw:
        score += 1.0 * kw
        reasons.append("parole chiave rilevanti")

    density = wc / dur if dur > 0 else 0
    score += min(density, 4.0) * 0.6
    if density > 2.2:
        reasons.append("ritmo di parlato elevato")

    # closeness to target duration
    score -= abs(dur - target) / target * 1.5

    # prefer complete sentences (ends with . ? !)
    if text.rstrip().endswith((".", "?", "!")):
        score += 0.5

    if not reasons:
        reasons.append("segmento con parlato continuo")
    return score, ", ".join(reasons[:2]).capitalize()


def select_auto_clips(segments: list, num_clips: int, target: float) -> list:
    """Build candidate windows snapped to sentence/segment boundaries and pick best."""
    candidates = []
    n = len(segments)
    for i in range(n):
        start = segments[i]["start"]
        j = i
        texts = []
        while j < n and (segments[j]["end"] - start) < target * 1.25:
            texts.append(segments[j]["text"])
            end = segments[j]["end"]
            dur = end - start
            if dur >= target * 0.7:
                score, reason = _score_window(" ".join(texts), dur, target)
                candidates.append({"start": start, "end": end, "score": score,
                                   "reason": reason, "text": " ".join(texts)})
            j += 1

    candidates.sort(key=lambda c: c["score"], reverse=True)
    chosen = []
    for c in candidates:
        overlap = any(not (c["end"] <= x["start"] or c["start"] >= x["end"]) for x in chosen)
        if overlap:
            continue
        chosen.append(c)
        if len(chosen) >= num_clips:
            break

    chosen.sort(key=lambda c: c["start"])
    clips = []
    for idx, c in enumerate(chosen):
        title = c["text"].strip()
        title = (title[:47] + "...") if len(title) > 50 else title
        clips.append(ClipInfo(index=idx, start=round(c["start"], 2), end=round(c["end"], 2),
                              title=title or f"Clip {idx+1}", reason=c["reason"]))
    return clips


def uniform_clips(duration: float, num_clips: int, clip_len: float) -> list:
    clips = []
    if num_clips <= 0:
        return clips
    clip_len = min(clip_len, duration)
    if num_clips == 1:
        starts = [max(0.0, (duration - clip_len) / 2)]
    else:
        usable = max(0.0, duration - clip_len)
        starts = [usable * i / (num_clips - 1) for i in range(num_clips)]
    for idx, s in enumerate(starts):
        clips.append(ClipInfo(index=idx, start=round(s, 2), end=round(min(duration, s + clip_len), 2),
                              title=f"Clip {idx+1}", reason="Suddivisione uniforme del video"))
    return clips


def _escape_filter_path(p: str) -> str:
    return p.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


async def render_clip(video_path: Path, clip: ClipInfo, settings, segments,
                      out_path: Path, progress_cb) -> None:
    """Render a single clip with crop/scale/zoom/subtitles/audio-normalize."""
    tw, th = ASPECT_TARGETS[settings.aspect_ratio]
    duration = max(0.1, clip.end - clip.start)

    # probe source dims from stored project via ffprobe-less: use cv2? we pass via settings? -> reprobe quickly
    src_w, src_h = await _probe_dims(video_path)

    face_x = None
    if settings.aspect_ratio == "9:16" and settings.face_tracking and src_w / max(1, src_h) > (tw / th):
        try:
            face_x = await asyncio.to_thread(detect_face_center_x, video_path, clip.start, clip.end)
        except Exception as e:
            logger.warning("Face detection fallita: %s", e)
            face_x = None

    vf = []
    if settings.auto_crop or settings.aspect_ratio != "16:9":
        cw, ch, cx, cy = compute_crop(src_w, src_h, settings.aspect_ratio, face_x)
        vf.append(f"crop={cw}:{ch}:{cx}:{cy}")
    vf.append(f"scale={tw}:{th}:force_original_aspect_ratio=decrease")
    vf.append(f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:color=black")
    vf.append("setsar=1")

    if settings.auto_zoom:
        vf.append(
            f"zoompan=z='min(1.0+0.0009*on,1.12)':d=1:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={tw}x{th}:fps=30"
        )

    if settings.subtitles and segments:
        ass_path = out_path.with_suffix(".ass")
        # merge preset defaults into style for rendering
        _apply_preset(settings.subtitle_style)
        build_ass(segments, settings.subtitle_style, clip.start, clip.end, ass_path, tw, th)
        vf.append(f"subtitles={_escape_filter_path(str(ass_path))}")

    vf_str = ",".join(vf)

    cmd = [
        "ffmpeg", "-y", "-ss", f"{clip.start}", "-i", str(video_path),
        "-t", f"{duration}",
        "-vf", vf_str,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-profile:v", "high",
    ]
    if settings.audio_normalize:
        cmd += ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"]
    cmd += ["-c:a", "aac", "-b:a", "128k", "-ar", "48000",
            "-movflags", "+faststart",
            "-progress", "pipe:1", "-nostats", str(out_path)]

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    err_tail = []
    assert proc.stdout is not None
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        s = line.decode("utf-8", "ignore").strip()
        if s.startswith("out_time_ms="):
            try:
                ms = int(s.split("=", 1)[1])
                pct = int(min(99, (ms / 1_000_000) / duration * 100))
                await progress_cb(pct)
            except Exception:
                pass
    _out, err = await proc.communicate()
    if err:
        err_tail = err.decode("utf-8", "ignore")[-500:]
    if proc.returncode != 0 or not out_path.exists():
        raise RuntimeError(f"FFmpeg export fallito: {err_tail}")
    await progress_cb(100)


async def _probe_dims(video_path: Path) -> tuple[int, int]:
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", str(video_path)]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, _ = await proc.communicate()
    try:
        w, h = out.decode().strip().split("x")
        return int(w), int(h)
    except Exception:
        return 1920, 1080


def _apply_preset(style) -> None:
    d = PRESET_DEFAULTS.get(style.preset)
    if not d:
        return
    # preset drives look; explicit user changes already in fields, but ensure font fallback
    if not style.font:
        style.font = d["font"]


def make_zip(zip_local: Path, work_dir: Path, files: list) -> Path:
    with zipfile.ZipFile(zip_local, "w", zipfile.ZIP_STORED) as zf:
        for f in files:
            p = work_dir / f
            if p.exists():
                zf.write(p, arcname=f)
    return zip_local
