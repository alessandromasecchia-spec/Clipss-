import asyncio
import logging
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Body, Request
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.middleware.cors import CORSMiddleware

from config import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, THUMB_DIR, WORK_DIR
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
        storage.put_bytes(storage.orig_path(project_id, ext), bytes(buf), ctype or "video/mp4")
    except Exception as e:
        logger.exception("Upload su object storage fallito")
        raise HTTPException(status_code=502, detail=f"Errore di archiviazione: {e}")

    # ephemeral local copy (downloaded from storage) for probe + thumbnail
    tmp = WORK_DIR / f"probe_{project_id}{ext}"
    try:
        storage.download_to(storage.orig_path(project_id, ext), tmp)
        try:
            meta = await probe_video(tmp)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        await generate_thumbnail(tmp, project_id, at_sec=min(1.0, meta["duration"] / 2))
        thumb_local = THUMB_DIR / f"{project_id}.jpg"
        if thumb_local.exists():
            storage.put_file(storage.thumb_path(project_id), thumb_local, "image/jpeg")
            thumb_local.unlink(missing_ok=True)
    finally:
        tmp.unlink(missing_ok=True)

    meta["size_bytes"] = len(buf)
    project = Project(id=project_id, name=safe, original_filename=original,
                      stored_filename=f"original{ext}", ext=ext, **meta)
    await db.projects.insert_one(project.model_dump())
    return _project_summary(project.model_dump())


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
    return {"deleted": True}


# --------------------- media serving ---------------------
@api.get("/media/thumb/{project_id}")
async def media_thumb(project_id: str, request: Request):
    try:
        data, ct = storage.get_bytes(storage.thumb_path(sanitize_filename(project_id)))
    except Exception:
        raise HTTPException(status_code=404, detail="Anteprima non disponibile.")
    return _range_response(data, "image/jpeg", request)


@api.get("/media/original/{project_id}")
async def media_original(project_id: str, request: Request):
    proj = await _get_project(project_id)
    try:
        data, ct = storage.get_bytes(storage.orig_path(project_id, proj["ext"]))
    except Exception:
        raise HTTPException(status_code=404, detail="Video originale non disponibile.")
    return _range_response(data, ct or "video/mp4", request)


@api.get("/media/clip/{project_id}/{name}")
async def media_clip(project_id: str, name: str, request: Request, dl: int = 0):
    safe = sanitize_filename(name)
    try:
        data, ct = storage.get_bytes(storage.clip_path(project_id, safe))
    except Exception:
        raise HTTPException(status_code=404, detail="Clip non trovata.")
    return _range_response(data, "video/mp4", request, filename=safe if dl else None)


@api.get("/media/zip/{project_id}")
async def media_zip(project_id: str, request: Request):
    try:
        data, ct = storage.get_bytes(storage.zip_path(sanitize_filename(project_id)))
    except Exception:
        raise HTTPException(status_code=404, detail="Archivio ZIP non disponibile.")
    return _range_response(data, "application/zip", request, filename=f"clipforge_{project_id}.zip")


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
    storage.put_bytes(storage.asset_path(project_id, name), data, file.content_type or "audio/mpeg")
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
    storage.put_bytes(storage.asset_path(project_id, name), data, file.content_type or "image/png")
    return {"name": name}


@api.get("/jobs/{job_id}")
async def get_job(job_id: str):
    j = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    if not j:
        raise HTTPException(status_code=404, detail="Job non trovato.")
    return j


# --------------------- job runner ---------------------
async def _save_job(job: Job):
    await db.jobs.update_one({"id": job.id}, {"$set": job.model_dump()})


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
        storage.download_to(storage.orig_path(project.id, project.ext), video_path)
        if settings.music:
            music_local = work / f"music_{settings.music.name}"
            storage.download_to(storage.asset_path(project.id, settings.music.name), music_local)
        if settings.overlay:
            overlay_local = work / f"overlay_{settings.overlay.name}"
            storage.download_to(storage.asset_path(project.id, settings.overlay.name), overlay_local)

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
                storage.put_file(storage.clip_path(project.id, filename), out_path, "video/mp4")
                clip.status = "completed"; clip.progress = 100; clip.filename = filename
                completed_files.append(filename)
                out_path.with_suffix(".ass").unlink(missing_ok=True)
            except Exception as e:
                logger.exception("Render clip %s fallito", i)
                clip.status = "failed"; clip.error = str(e)[:300]
            await _save_job(job)

        if completed_files and not manual:
            zip_local = work / f"{project.id}.zip"
            make_zip(zip_local, work, completed_files)
            storage.put_file(storage.zip_path(project.id), zip_local, "application/zip")
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
