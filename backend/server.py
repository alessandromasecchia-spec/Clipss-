import asyncio
import logging
import os
import shutil
import ipaddress
import socket
import subprocess
import sys
import urllib.parse
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Body, Request
from fastapi.responses import Response, FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.middleware.cors import CORSMiddleware

from config import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, THUMB_DIR, WORK_DIR, CACHE_DIR
from media import free_disk_bytes, generate_thumbnail, probe_video, sanitize_filename
from models import ClipInfo, ClipSettings, Job, Project, new_id
from pipeline import extract_audio, make_zip, render_clip, select_auto_clips, uniform_clips
import storage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="ClipForge")
api = APIRouter(prefix="/api")
_JOB_SEM = asyncio.Semaphore(1)  # process one heavy job at a time (batch queue)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("clipforge")


# ------------------------- helpers -------------------------
def _project_summary(p: dict) -> dict:
    return {
        "id": p["id"], "name": p["name"], "duration": p["duration"],
        "width": p["width"], "height": p["height"], "fps": p["fps"],
        "size_bytes": p["size_bytes"], "has_audio": p["has_audio"],
        "created_at": p["created_at"], "clip_count": p.get("clip_count", 0),
        "original_filename": p["original_filename"],
        "thumbnail_url": f"/api/media/thumb/{p['id']}",
        "preview_url": f"/api/media/original/{p['id']}",
    }


async def _get_project(project_id: str) -> dict:
    p = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Progetto non trovato.")
    return p


def _range_response(data: bytes, content_type: str, request: Request, filename: str = None):
    total = len(data)
    rng = request.headers.get("range") or request.headers.get("Range")
    headers = {"Accept-Ranges": "bytes"}
    if filename:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    if rng and rng.startswith("bytes="):
        try:
            part = rng.split("=", 1)[1].split(",")[0]
            s, e = part.split("-")
            start = int(s) if s else 0
            end = int(e) if e else total - 1
            start = max(0, start)
            end = min(end, total - 1)
            if start > end:
                start, end = 0, total - 1
            chunk = data[start:end + 1]
            headers["Content-Range"] = f"bytes {start}-{end}/{total}"
            headers["Content-Length"] = str(len(chunk))
            return Response(chunk, status_code=206, media_type=content_type, headers=headers)
        except Exception:
            pass
    headers["Content-Length"] = str(total)
    return Response(data, media_type=content_type, headers=headers)          
def _validate_source_url(raw: str) -> str:
    url = (raw or "").strip()
    parsed = urllib.parse.urlparse(url)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(
            status_code=400,
            detail="Inserisci un link video http:// o https:// valido."
        )

    host = parsed.hostname or ""

    try:
        infos = socket.getaddrinfo(host, None)

        for info in infos:
            addr = ipaddress.ip_address(info[4][0])

            if (
                addr.is_private
                or addr.is_loopback
                or addr.is_link_local
                or addr.is_reserved
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Indirizzo non consentito."
                )

    except socket.gaierror:
        raise HTTPException(
            status_code=400,
            detail="Dominio non raggiungibile."
        )

    return url


def _download_video_url(url: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    template = str(out_dir / "source.%(ext)s")

    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--no-playlist",
        "--restrict-filenames",
        "--max-filesize",
        str(MAX_UPLOAD_BYTES),
        "--socket-timeout",
        "20",
        "--retries",
        "2",
        "-f",
        "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
        "--merge-output-format",
        "mp4",
        "-o",
        template,
        url,
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=900,
        )

    except FileNotFoundError:
        raise RuntimeError("yt-dlp non è installato nel backend.")

    except subprocess.CalledProcessError as e:
        error = e.stderr or e.stdout or "Download del link fallito."
        raise RuntimeError(error[-1000:])

    candidates = [
        p for p in out_dir.glob("source.*")
        if p.is_file()
    ]

    if not candidates:
        raise RuntimeError(
            "Il link non contiene un video scaricabile."
        )

    path = candidates[0]

    if path.stat().st_size == 0:
        raise RuntimeError("Il video scaricato è vuoto.")

    if path.stat().st_size > MAX_UPLOAD_BYTES:
        raise RuntimeError("Video troppo grande (max 2GB).")

    return path


# ------------------------- routes -------------------------
@api.get("/")
async def root():
    return {"app": "ClipForge", "status": "ok"}


@api.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    original = file.filename or "video.mp4"
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400,
                            detail=f"Formato non supportato ({ext}). Usa MP4, MOV, MKV, WEBM o AVI.")
    ctype = (file.content_type or "").lower()
    if ctype and not (ctype.startswith("video/") or ctype == "application/octet-stream"):
        raise HTTPException(status_code=400, detail=f"Tipo MIME non valido: {ctype}")
    if free_disk_bytes(WORK_DIR) < 500 * 1024 * 1024:
        raise HTTPException(status_code=507, detail="Spazio su disco insufficiente.")

    project_id = new_id()
    safe = sanitize_filename(original)

    # read into memory enforcing the size limit
    buf = bytearray()
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        buf += chunk
        if len(buf) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File troppo grande (max 2GB).")
    if len(buf) == 0:
        raise HTTPException(status_code=400, detail="File vuoto.")

    # persist original to object storage (source of truth)
    try:
        await asyncio.to_thread(storage.put_bytes, storage.orig_path(project_id, ext), bytes(buf), ctype or "video/mp4")
    except Exception as e:
        logger.exception("Upload su object storage fallito")
        raise HTTPException(status_code=502, detail=f"Errore di archiviazione: {e}")

    # ephemeral local copy (downloaded from storage) for probe + thumbnail
    tmp = WORK_DIR / f"probe_{project_id}{ext}"
    try:
        await asyncio.to_thread(storage.download_to, storage.orig_path(project_id, ext), tmp)
        try:
            meta = await probe_video(tmp)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        await generate_thumbnail(tmp, project_id, at_sec=min(1.0, meta["duration"] / 2))
        thumb_local = THUMB_DIR / f"{project_id}.jpg"
        if thumb_local.exists():
            await asyncio.to_thread(storage.put_file, storage.thumb_path(project_id), thumb_local, "image/jpeg")
            thumb_local.unlink(missing_ok=True)
    finally:
        tmp.unlink(missing_ok=True)

    meta["size_bytes"] = len(buf)
    project = Project(id=project_id, name=safe, original_filename=original,
                      stored_filename=f"original{ext}", ext=ext, **meta)
    await db.projects.insert_one(project.model_dump())
    return _project_summary(project.model_dump())
@api.post("/upload-url")
async def upload_video_url(payload: dict = Body(...)):
    url = _validate_source_url(payload.get("url", ""))

    if free_disk_bytes(WORK_DIR) < 500 * 1024 * 1024:
        raise HTTPException(
            status_code=507,
            detail="Spazio su disco insufficiente."
        )

    project_id = new_id()
    temp_dir = WORK_DIR / f"url_{project_id}"

    try:
        video_path = await asyncio.to_thread(
            _download_video_url,
            url,
            temp_dir
        )

        ext = video_path.suffix.lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Formato scaricato non supportato ({ext})."
            )

        try:
            meta = await probe_video(video_path)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )

        original = sanitize_filename(
            video_path.name
        )

        await asyncio.to_thread(
            storage.put_file,
            storage.orig_path(project_id, ext),
            video_path,
            "video/mp4"
        )

        await generate_thumbnail(
            video_path,
            project_id,
            at_sec=min(1.0, meta["duration"] / 2)
        )

        thumb_local = THUMB_DIR / f"{project_id}.jpg"

        if thumb_local.exists():
            await asyncio.to_thread(
                storage.put_file,
                storage.thumb_path(project_id),
                thumb_local,
                "image/jpeg"
            )

            thumb_local.unlink(missing_ok=True)

        meta["size_bytes"] = video_path.stat().st_size

        project = Project(
            id=project_id,
            name=original,
            original_filename=original,
            stored_filename=f"original{ext}",
            ext=ext,
            **meta
        )

        await db.projects.insert_one(
            project.model_dump()
        )

        return _project_summary(
            project.model_dump()
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.exception("Import da URL fallito")

        raise HTTPException(
            status_code=400,
            detail=f"Impossibile importare il link: {str(e)[:500]}"
        )

    finally:
        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )


@api.get("/projects")
async def list_projects():
    docs = await db.projects.find({}, {"_id": 0, "segments": 0}).sort("created_at", -1).to_list(200)
    return [_project_summary(d) for d in docs]


@api.get("/projects/{project_id}")
async def get_project(project_id: str):
    return _project_summary(await _get_project(project_id))


@api.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    await _get_project(project_id)
    await db.projects.delete_one({"id": project_id})
    await db.jobs.delete_many({"project_id": project_id})
    for pat in (f"orig_{project_id}*", f"thumb_{project_id}.jpg", f"clip_{project_id}_*", f"zip_{project_id}.zip"):
        for f in CACHE_DIR.glob(pat):
            f.unlink(missing_ok=True)
    return {"deleted": True}


# --------------------- media serving ---------------------
_cache_locks: dict = {}


def _lock_for(key: str) -> asyncio.Lock:
    lk = _cache_locks.get(key)
    if lk is None:
        lk = asyncio.Lock()
        _cache_locks[key] = lk
    return lk


async def _serve_cached(object_path: str, local_path: Path, media_type: str,
                        request: Request, filename: str = None, not_found: str = "File non disponibile."):
    """Download the object to a local disk cache once (in a worker thread so the
    event loop is never blocked), then serve it with real HTTP Range support
    (206) by reading only the requested slice from local disk."""
    if not (local_path.exists() and local_path.stat().st_size > 0):
        async with _lock_for(str(local_path)):
            if not (local_path.exists() and local_path.stat().st_size > 0):
                tmp = local_path.with_suffix(local_path.suffix + ".part")
                try:
                    await asyncio.to_thread(storage.download_to, object_path, tmp)
                    tmp.replace(local_path)
                except Exception:
                    tmp.unlink(missing_ok=True)
                    raise HTTPException(status_code=404, detail=not_found)

    file_size = local_path.stat().st_size
    headers = {"Accept-Ranges": "bytes", "Cache-Control": "public, max-age=86400"}
    if filename:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    rng = request.headers.get("range") or request.headers.get("Range")
    if rng and rng.startswith("bytes="):
        try:
            part = rng.split("=", 1)[1].split(",")[0]
            s, e = part.split("-")
            start = int(s) if s else 0
            end = int(e) if e else file_size - 1
            start = max(0, start)
            end = min(end, file_size - 1)
            if start > end:
                start, end = 0, file_size - 1
            length = end - start + 1

            def _read():
                with open(local_path, "rb") as f:
                    f.seek(start)
                    return f.read(length)

            data = await asyncio.to_thread(_read)
            headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            headers["Content-Length"] = str(length)
            return Response(data, status_code=206, media_type=media_type, headers=headers)
        except Exception:
            pass
    return FileResponse(local_path, media_type=media_type, filename=filename, headers=headers)


@api.get("/media/thumb/{project_id}")
async def media_thumb(project_id: str, request: Request):
    pid = sanitize_filename(project_id)
    return await _serve_cached(storage.thumb_path(pid), CACHE_DIR / f"thumb_{pid}.jpg",
                               "image/jpeg", request, not_found="Anteprima non disponibile.")


@api.get("/media/original/{project_id}")
async def media_original(project_id: str, request: Request):
    proj = await _get_project(project_id)
    return await _serve_cached(storage.orig_path(project_id, proj["ext"]),
                               CACHE_DIR / f"orig_{project_id}{proj['ext']}", "video/mp4", request,
                               not_found="Video originale non disponibile.")


@api.get("/media/clip/{project_id}/{name}")
async def media_clip(project_id: str, name: str, request: Request, dl: int = 0):
    safe = sanitize_filename(name)
    return await _serve_cached(storage.clip_path(project_id, safe),
                               CACHE_DIR / f"clip_{project_id}_{safe}", "video/mp4", request,
                               filename=safe if dl else None, not_found="Clip non trovata.")


@api.get("/media/zip/{project_id}")
async def media_zip(project_id: str, request: Request):
    pid = sanitize_filename(project_id)
    return await _serve_cached(storage.zip_path(pid), CACHE_DIR / f"zip_{pid}.zip",
                               "application/zip", request, filename=f"clipforge_{pid}.zip",
                               not_found="Archivio ZIP non disponibile.")


# --------------------- processing ---------------------
@api.post("/projects/{project_id}/process")
async def process_project(project_id: str, settings: ClipSettings = Body(...)):
    await _get_project(project_id)
    job = Job(project_id=project_id, settings=settings)
    await db.jobs.insert_one(job.model_dump())
    asyncio.create_task(run_job(job.id))
    return job.model_dump()


@api.post("/projects/{project_id}/render-clip")
async def render_single(project_id: str, payload: dict = Body(...)):
    await _get_project(project_id)
    start = float(payload.get("start", 0))
    end = float(payload.get("end", 0))
    if end <= start:
        raise HTTPException(status_code=400, detail="Intervallo non valido (end deve essere > start).")
    settings = ClipSettings(**payload.get("settings", {}))
    settings.auto_find = False
    job = Job(project_id=project_id, settings=settings,
              clips=[ClipInfo(index=0, start=round(start, 2), end=round(end, 2),
                              title="Clip manuale", reason="Ritaglio manuale dall'editor")])
    await db.jobs.insert_one(job.model_dump())
    asyncio.create_task(run_job(job.id, manual=True))
    return job.model_dump()


AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}


@api.post("/projects/{project_id}/audio")
async def upload_audio(project_id: str, file: UploadFile = File(...)):
    await _get_project(project_id)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in AUDIO_EXT:
        raise HTTPException(status_code=400, detail="Formato audio non supportato (usa MP3, WAV, M4A, AAC).")
    data = await file.read()
    if len(data) > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File audio troppo grande (max 100MB).")
    name = sanitize_filename(file.filename or f"audio{ext}")
    await asyncio.to_thread(storage.put_bytes, storage.asset_path(project_id, name), data, file.content_type or "audio/mpeg")
    return {"name": name}


@api.post("/projects/{project_id}/overlay")
async def upload_overlay(project_id: str, file: UploadFile = File(...)):
    await _get_project(project_id)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in IMAGE_EXT:
        raise HTTPException(status_code=400, detail="Formato immagine non supportato (usa PNG, JPG, WEBP).")
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Immagine troppo grande (max 20MB).")
    name = sanitize_filename(file.filename or f"overlay{ext}")
    await asyncio.to_thread(storage.put_bytes, storage.asset_path(project_id, name), data, file.content_type or "image/png")
    return {"name": name}


def _caption_cues(segments, words_per_line):
    words = []
    for seg in segments:
        sw = seg.get("words") or []
        if sw:
            for w in sw:
                words.append({"start": w["start"], "end": w["end"], "word": (w["word"] or "").strip(), "whole": False})
        else:
            words.append({"start": seg["start"], "end": seg["end"], "word": (seg["text"] or "").strip(), "whole": True})
    words.sort(key=lambda x: x["start"])
    groups, cur = [], []
    for w in words:
        cur.append(w)
        if w["whole"] or len(cur) >= words_per_line or w["word"].endswith((".", "?", "!")):
            groups.append(cur); cur = []
    if cur:
        groups.append(cur)
    return [{"start": g[0]["start"], "end": max(g[-1]["end"], g[0]["start"] + 0.4),
             "text": " ".join(x["word"] for x in g).strip()} for g in groups if any(x["word"] for x in g)]


def _cue_ts(sec, vtt=False):
    sec = max(0.0, sec)
    h = int(sec // 3600); m = int((sec % 3600) // 60); s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    sep = "." if vtt else ","
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


@api.get("/projects/{project_id}/captions")
async def export_captions(project_id: str, fmt: str = "srt", words: int = 5):
    p = await _get_project(project_id)
    segs = p.get("segments")
    if not segs:
        raise HTTPException(status_code=404, detail="Trascrizione non disponibile. Genera prima delle clip con i sottotitoli attivi.")
    cues = _caption_cues(segs, max(1, min(12, words)))
    fmt = fmt.lower()
    if fmt == "txt":
        body = "\n".join(c["text"] for c in cues)
        media = "text/plain"
    elif fmt == "vtt":
        lines = ["WEBVTT", ""]
        for c in cues:
            lines.append(f"{_cue_ts(c['start'], True)} --> {_cue_ts(c['end'], True)}")
            lines.append(c["text"]); lines.append("")
        body = "\n".join(lines); media = "text/vtt"
    else:  # srt
        lines = []
        for i, c in enumerate(cues, 1):
            lines.append(str(i))
            lines.append(f"{_cue_ts(c['start'])} --> {_cue_ts(c['end'])}")
            lines.append(c["text"]); lines.append("")
        body = "\n".join(lines); media = "application/x-subrip"
    return Response(body, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="clipforge_{project_id}.{fmt}"'})


@api.get("/jobs/{job_id}")
async def get_job(job_id: str):
    j = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    if not j:
        raise HTTPException(status_code=404, detail="Job non trovato.")
    return j


# --------------------- job runner ---------------------
async def _save_job(job: Job):
    await db.jobs.update_one({"id": job.id}, {"$set": job.model_dump()})


async def _upload_with_retry(object_path: str, local_path: Path,
                             content_type: str = "video/mp4", attempts: int = 3):
    delay = 1.0
    last = None
    for _i in range(attempts):
        try:
            await asyncio.to_thread(storage.put_file, object_path, local_path, content_type)
            return
        except Exception as e:
            last = e
            await asyncio.sleep(delay)
            delay *= 2
    raise RuntimeError(f"Upload su storage fallito dopo {attempts} tentativi: {last}")


async def run_job(job_id: str, manual: bool = False):
    jdoc = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    if not jdoc:
        return
    job = Job(**jdoc)
    pdoc = await db.projects.find_one({"id": job.project_id}, {"_id": 0})
    if not pdoc:
        job.status = "failed"; job.error = "Progetto non trovato."
        await _save_job(job); return
    project = Project(**pdoc)
    settings = job.settings

    work = WORK_DIR / job.id
    work.mkdir(parents=True, exist_ok=True)
    video_path = work / f"original{project.ext}"

    job.status = "queued"; job.progress = 0; job.stage = "In coda"
    await _save_job(job)
    await _JOB_SEM.acquire()

    music_local = overlay_local = None
    try:
        job.status = "processing"; job.progress = 2; job.stage = "Preparazione"
        await _save_job(job)
        await asyncio.to_thread(storage.download_to, storage.orig_path(project.id, project.ext), video_path)
        if settings.music:
            music_local = work / f"music_{settings.music.name}"
            await asyncio.to_thread(storage.download_to, storage.asset_path(project.id, settings.music.name), music_local)
        if settings.overlay:
            overlay_local = work / f"overlay_{settings.overlay.name}"
            await asyncio.to_thread(storage.download_to, storage.asset_path(project.id, settings.overlay.name), overlay_local)

        segments = project.segments
        need_transcription = settings.subtitles or (settings.auto_find and not manual)
        if need_transcription and not segments and project.has_audio:
            job.stage = "Trascrizione audio (Whisper)"; job.progress = 5
            await _save_job(job)
            try:
                wav = work / "audio.wav"
                if await extract_audio(video_path, wav):
                    from transcription import transcribe
                    segments = await transcribe(wav)
                    wav.unlink(missing_ok=True)
                    await db.projects.update_one({"id": project.id}, {"$set": {"segments": segments}})
                else:
                    segments = []
            except Exception as e:
                logger.warning("Trascrizione fallita, uso split uniforme: %s", e)
                segments = []
        job.progress = 25
        await _save_job(job)

        if manual:
            clips = job.clips
        elif settings.auto_find and segments:
            clips = select_auto_clips(segments, settings.num_clips, float(settings.clip_duration),
                                      total=project.duration)
            if not clips:
                clips = uniform_clips(project.duration, settings.num_clips, float(settings.clip_duration))
        else:
            clips = uniform_clips(project.duration, settings.num_clips, float(settings.clip_duration))

        job.clips = clips
        await _save_job(job)

        total = max(1, len(clips))
        span = 74.0 / total
        completed_files = []

        for i, clip in enumerate(clips):
            clip.status = "processing"; clip.progress = 0
            job.stage = f"Elaborazione clip {i + 1} di {total}"
            await _save_job(job)

            base = 25.0 + span * i
            filename = f"edit_{job.id[:8]}_{i + 1}.mp4" if manual else f"clip_{i + 1}.mp4"
            out_path = work / filename

            async def progress_cb(pct, _clip=clip, _base=base):
                _clip.progress = pct
                job.progress = int(_base + span * (pct / 100.0))
                await _save_job(job)

            try:
                await render_clip(video_path, clip, settings, segments or [], out_path, progress_cb,
                                  music_path=music_local, overlay_path=overlay_local,
                                  has_audio=project.has_audio)
                clip.status = "verifying"
                await _save_job(job)
                if not out_path.exists() or out_path.stat().st_size == 0:
                    raise RuntimeError("File di output vuoto o mancante.")
                meta = await probe_video(out_path)
                if meta.get("duration", 0) <= 0:
                    raise RuntimeError("Clip non riproducibile (durata nulla).")
                clip.status = "uploading"
                await _save_job(job)
                await _upload_with_retry(storage.clip_path(project.id, filename), out_path, "video/mp4")
                clip.status = "completed"; clip.progress = 100; clip.filename = filename
                completed_files.append(filename)
                out_path.with_suffix(".ass").unlink(missing_ok=True)
            except Exception as e:
                logger.exception("Render clip %s fallito", i)
                clip.status = "failed"; clip.error = str(e)[:300]
            await _save_job(job)

        if completed_files and not manual:
            zip_local = work / f"{project.id}.zip"
            await asyncio.to_thread(make_zip, zip_local, work, completed_files)
            await _upload_with_retry(storage.zip_path(project.id), zip_local, "application/zip")
            job.zip_filename = f"{project.id}.zip"
            await db.projects.update_one({"id": project.id},
                                         {"$set": {"clip_count": len(completed_files)}})

        if completed_files:
            job.status = "completed"; job.progress = 100; job.stage = "Completato"
        else:
            job.status = "failed"
            job.error = job.error or "Nessuna clip è stata generata con successo."
            job.stage = "Errore"
        await _save_job(job)

    except Exception as e:
        logger.exception("Job fallito")
        job.status = "failed"; job.error = str(e)[:400]; job.stage = "Errore"
        await _save_job(job)
    finally:
        _JOB_SEM.release()
        shutil.rmtree(work, ignore_errors=True)


@app.on_event("startup")
async def _startup():
    try:
        storage.init_storage()
        logger.info("Object storage inizializzato.")
    except Exception as e:
        logger.error("Init object storage fallito: %s", e)


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
