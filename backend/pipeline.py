import asyncio
import logging
import zipfile
from pathlib import Path

from config import ASPECT_TARGETS
from face_crop import compute_crop, detect_face_center_x, detect_face_track
from models import ClipInfo
from silence import build_remap, compute_keep_intervals, detect_silences
from subtitles import PRESET_DEFAULTS, build_ass

logger = logging.getLogger(__name__)

KEYWORDS = [
    "perché", "perche", "come", "segreto", "importante", "mai", "sempre",
    "gratis", "errore", "migliore", "peggiore", "incredibile", "attenzione",
    "problema", "soluzione", "trucco", "consiglio", "risultato", "soldi",
    "tempo", "vita", "successo", "primo", "ultimo", "nessuno", "tutti",
]


async def _run_ffmpeg(cmd: list) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
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


# ----------------------- auto-clip selection -----------------------
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
    score -= abs(dur - target) / target * 1.5
    if text.rstrip().endswith((".", "?", "!")):
        score += 0.5
    if not reasons:
        reasons.append("segmento con parlato continuo")
    return score, ", ".join(reasons[:2]).capitalize()


def select_auto_clips(segments: list, num_clips: int, target: float, total: float = 0.0) -> list:
    target = min(60.0, max(15.0, target))
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
            if dur >= max(12.0, target * 0.6):
                score, reason = _score_window(" ".join(texts), dur, target)
                candidates.append({"start": start, "end": end, "score": score,
                                   "reason": reason, "text": " ".join(texts)})
            j += 1

    candidates.sort(key=lambda c: c["score"], reverse=True)
    chosen = []
    for c in candidates:
        if any(not (c["end"] <= x["start"] or c["start"] >= x["end"]) for x in chosen):
            continue
        chosen.append(c)
        if len(chosen) >= num_clips:
            break

    chosen.sort(key=lambda c: c["start"])
    clips = []
    for idx, c in enumerate(chosen):
        # small padding around sentence boundaries, kept natural
        s = max(0.0, c["start"] - 0.3)
        e = c["end"] + 0.3
        if total:
            e = min(total, e)
        title = c["text"].strip()
        title = (title[:47] + "...") if len(title) > 50 else title
        clips.append(ClipInfo(index=idx, start=round(s, 2), end=round(e, 2),
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


# ----------------------- filter helpers -----------------------
def _escape_filter_path(p: str) -> str:
    return p.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _apply_preset(style) -> None:
    d = PRESET_DEFAULTS.get(style.preset)
    if d and not style.font:
        style.font = d["font"]


def _crop_x_expr(points, src_w, crop_w):
    """Piecewise-linear crop x expression over 't' from smoothed face points."""
    lo = crop_w / 2.0
    hi = src_w - crop_w / 2.0
    pts = [(t, min(max(c, lo), hi)) for t, c in points]
    if len(pts) == 1:
        cx = pts[0][1] - crop_w / 2.0
        return str(int(round(min(max(cx, 0), src_w - crop_w))))
    expr = f"({pts[-1][1]}-{crop_w}/2)"
    for i in range(len(pts) - 2, -1, -1):
        t0, x0 = pts[i]
        t1, x1 = pts[i + 1]
        lerp = f"(({x0})+(({x1})-({x0}))*(t-{t0})/{max(0.001, t1 - t0)}-{crop_w}/2)"
        expr = f"if(lt(t,{t1}),{lerp},{expr})"
    return f"clip({expr},0,{src_w - crop_w})"


def _zoom_filter(emph, level, mode, eff, tw, th):
    if level == "off":
        return None
    amp = {"low": 0.05, "medium": 0.09, "high": 0.14}[level]
    cap = {"low": 3, "medium": 5, "high": 8}[level]
    w = 0.6
    emph = emph[:cap]
    bumps = "+".join(f"{amp}*exp(-((it-{round(t,2)})/{w})^2)" for t in emph)
    if mode == "punch_in":
        base = "1.0+min(0.10,0.012*it)"
    elif mode == "punch_out":
        base = "1.12-min(0.12,0.02*it)"
    else:
        base = "1.0"
    inner = base + (f"+{bumps}" if bumps else "")
    if mode == "normal" and not bumps:
        return None
    z = f"min(1.35,max(1.0,({inner})))"
    return (f"zoompan=z='{z}':d=1:x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':s={tw}x{th}:fps=30")


def _export_args(settings):
    if settings.export_preset == "social_small":
        crf = "28"
    elif settings.export_preset == "custom":
        crf = str(int(max(14, min(40, settings.export_crf or 20))))
    else:
        crf = "20"
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", crf,
            "-pix_fmt", "yuv420p", "-profile:v", "high"]


def _prepare_captions(segments, clip_start, clip_end, remap, max_words):
    words = []
    for seg in segments:
        if seg["end"] <= clip_start or seg["start"] >= clip_end:
            continue
        sw = seg.get("words") or []
        if sw:
            for wd in sw:
                if wd["end"] <= clip_start or wd["start"] >= clip_end:
                    continue
                o0 = remap(wd["start"] - clip_start)
                if o0 is None:
                    continue
                o1 = remap(wd["end"] - clip_start) or (o0 + 0.15)
                tok = (wd["word"] or "").strip()
                words.append({"start": o0, "end": o1, "word": tok,
                              "eos": tok.endswith((".", "?", "!")), "whole": False})
        else:
            o0 = remap(max(0.0, seg["start"] - clip_start))
            if o0 is None:
                continue
            o1 = remap(min(clip_end, seg["end"]) - clip_start) or (o0 + 1.0)
            words.append({"start": o0, "end": o1, "word": seg["text"], "eos": True, "whole": True})

    words.sort(key=lambda x: x["start"])
    groups, cur = [], []
    for wd in words:
        cur.append(wd)
        if wd["whole"] or len(cur) >= max_words or wd["eos"]:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)

    lines = []
    for g in groups:
        text = " ".join(x["word"] for x in g).strip()
        lines.append({"start": g[0]["start"], "end": max(g[-1]["end"], g[0]["start"] + 0.4),
                      "text": text, "words": g})
    return lines


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


# ----------------------- main render -----------------------
async def render_clip(video_path: Path, clip: ClipInfo, settings, segments, out_path: Path,
                      progress_cb, music_path=None, overlay_path=None, has_audio=True) -> None:
    tw, th = ASPECT_TARGETS[settings.aspect_ratio]
    dur = max(0.2, clip.end - clip.start)
    src_w, src_h = await _probe_dims(video_path)
    landscape = src_w / max(1, src_h) > (tw / th)

    # --- silence removal ---
    keep = [(0.0, dur)]
    if settings.silence_removal != "off" and has_audio:
        try:
            sil = await detect_silences(video_path, clip.start, dur, settings.silence_removal)
            keep = compute_keep_intervals(dur, sil, settings.silence_removal)
        except Exception as e:
            logger.warning("Silence detect fallito: %s", e)
            keep = [(0.0, dur)]
    silence_on = len(keep) > 1
    remap, eff = build_remap(keep)
    eff = max(0.2, eff)

    # --- face crop ---
    crop_needed = settings.auto_crop or settings.aspect_ratio != "16:9"
    cw = ch = cx = cy = None
    crop_x_expr = None
    pts = []
    if crop_needed:
        face_x = None
        if settings.aspect_ratio == "9:16" and settings.face_tracking and landscape:
            if silence_on:
                try:
                    face_x = await asyncio.to_thread(detect_face_center_x, video_path, clip.start, clip.end)
                except Exception:
                    face_x = None
            else:
                try:
                    pts, med = await asyncio.to_thread(detect_face_track, video_path, clip.start, dur)
                except Exception:
                    pts, med = [], None
                face_x = med
        cw, ch, cx, cy = compute_crop(src_w, src_h, settings.aspect_ratio, face_x)
        if (settings.aspect_ratio == "9:16" and settings.face_tracking and landscape
                and not silence_on and pts and len(pts) >= 2):
            crop_x_expr = _crop_x_expr(pts, src_w, cw)

    # --- zoom emphasis (output timeline) ---
    zoom_level = settings.smart_zoom
    if zoom_level == "off" and settings.auto_zoom:
        zoom_level = "low"
    emph = []
    if zoom_level != "off":
        for seg in segments or []:
            if seg["end"] <= clip.start or seg["start"] >= clip.end:
                continue
            o = remap(max(0.0, seg["start"] - clip.start))
            if o is not None:
                emph.append(o)
        emph = sorted(set(round(t, 2) for t in emph))

    # --- build filter graph ---
    graph = []
    if silence_on:
        vsegs, asegs = [], []
        for i, (a, b) in enumerate(keep):
            graph.append(f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS[sv{i}]")
            vsegs.append(f"[sv{i}]")
            if has_audio:
                graph.append(f"[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS[sa{i}]")
                asegs.append(f"[sa{i}]")
        graph.append(f"{''.join(vsegs)}concat=n={len(vsegs)}:v=1:a=0[vbase]")
        if has_audio:
            graph.append(f"{''.join(asegs)}concat=n={len(asegs)}:v=0:a=1[abase]")
        vbase, abase = "[vbase]", ("[abase]" if has_audio else None)
    else:
        vbase, abase = "[0:v]", ("[0:a]" if has_audio else None)

    vf = []
    if crop_needed:
        if crop_x_expr:
            vf.append(f"crop={cw}:{ch}:'{crop_x_expr}':{cy}")
        else:
            vf.append(f"crop={cw}:{ch}:{cx}:{cy}")
    vf.append(f"scale={tw}:{th}:force_original_aspect_ratio=decrease")
    vf.append(f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:color=black")
    vf.append("setsar=1")
    zf = _zoom_filter(emph, zoom_level, settings.zoom_mode, eff, tw, th)
    if zf:
        vf.append(zf)

    lines = []
    if settings.subtitles and segments:
        _apply_preset(settings.subtitle_style)
        lines = _prepare_captions(segments, clip.start, clip.end, remap,
                                  max(1, settings.subtitle_style.max_words_per_line))
    if lines:
        ass_path = out_path.with_suffix(".ass")
        build_ass(lines, settings.subtitle_style, ass_path, tw, th)
        vf.append(f"subtitles={_escape_filter_path(str(ass_path))}")

    graph.append(f"{vbase}{','.join(vf)}[vp]")

    # inputs & overlay index bookkeeping
    idx = 1
    music_idx = overlay_idx = None
    extra_inputs = []
    if music_path:
        music_idx = idx
        if settings.music and settings.music.loop:
            extra_inputs += ["-stream_loop", "-1"]
        extra_inputs += ["-i", str(music_path)]
        idx += 1
    if overlay_path:
        overlay_idx = idx
        extra_inputs += ["-i", str(overlay_path)]
        idx += 1

    final_v = "[vp]"
    if overlay_path and settings.overlay:
        ov = settings.overlay
        oend = ov.end if ov.end and ov.end > ov.start else eff
        graph.append(f"[{overlay_idx}:v]scale=iw*{ov.scale}:-1,format=rgba,"
                     f"colorchannelmixer=aa={ov.opacity}[ovl]")
        graph.append(f"[vp][ovl]overlay=x=(W-w)*{ov.x}:y=(H-h)*{ov.y}:"
                     f"enable='between(t,{ov.start},{oend})'[vout]")
        final_v = "[vout]"

    # audio
    final_a = None
    if abase:
        af = []
        if settings.audio_normalize:
            af.append("loudnorm=I=-16:TP=-1.5:LRA=11")
        if abs(settings.video_volume - 1.0) > 1e-3:
            af.append(f"volume={settings.video_volume}")
        if settings.fade_in > 0:
            af.append(f"afade=t=in:st=0:d={settings.fade_in}")
        if settings.fade_out > 0:
            af.append(f"afade=t=out:st={max(0.0, eff - settings.fade_out)}:d={settings.fade_out}")
        if not af:
            af.append("anull")
        graph.append(f"{abase}{','.join(af)}[asrc]")
    if music_path and settings.music:
        m = settings.music
        mf = [f"atrim=start={m.start_offset}", "asetpts=PTS-STARTPTS", f"volume={m.volume}"]
        if m.fade_in > 0:
            mf.append(f"afade=t=in:st=0:d={m.fade_in}")
        if m.fade_out > 0:
            mf.append(f"afade=t=out:st={max(0.0, eff - m.fade_out)}:d={m.fade_out}")
        mf.append(f"atrim=0:{eff}")
        graph.append(f"[{music_idx}:a]{','.join(mf)}[amus]")

    if abase and music_path:
        graph.append("[asrc][amus]amix=inputs=2:duration=first:normalize=0[aout]")
        final_a = "[aout]"
    elif abase:
        final_a = "[asrc]"
    elif music_path:
        final_a = "[amus]"

    filter_complex = ";".join(graph)

    cmd = ["ffmpeg", "-y", "-ss", f"{clip.start}", "-t", f"{dur}", "-i", str(video_path)]
    cmd += extra_inputs
    cmd += ["-filter_complex", filter_complex, "-map", final_v]
    if final_a:
        cmd += ["-map", final_a]
    else:
        cmd += ["-an"]
    cmd += _export_args(settings)
    if final_a:
        cmd += ["-c:a", "aac", "-b:a", "128k", "-ar", "48000"]
    cmd += ["-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(out_path)]

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    assert proc.stdout is not None
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        s = line.decode("utf-8", "ignore").strip()
        if s.startswith("out_time_ms="):
            try:
                ms = int(s.split("=", 1)[1])
                pct = int(min(99, (ms / 1_000_000) / eff * 100))
                await progress_cb(pct)
            except Exception:
                pass
    _out, err = await proc.communicate()
    err_tail = err.decode("utf-8", "ignore")[-600:] if err else ""
    if proc.returncode != 0 or not out_path.exists():
        raise RuntimeError(f"FFmpeg export fallito: {err_tail}")
    await progress_cb(100)


def make_zip(zip_local: Path, work_dir: Path, files: list) -> Path:
    with zipfile.ZipFile(zip_local, "w", zipfile.ZIP_STORED) as zf:
        for f in files:
            p = work_dir / f
            if p.exists():
                zf.write(p, arcname=f)
    return zip_local
