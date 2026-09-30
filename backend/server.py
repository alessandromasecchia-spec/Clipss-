import asyncio
import logging
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Body
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.middleware.cors import CORSMiddleware

from config import (ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, OUTPUT_DIR, THUMB_DIR,
                    UPLOAD_DIR, ZIP_DIR, MODEL_DIR)
from media import (free_disk_bytes, generate_thumbnail, probe_video, sanitize_filename)
from models import ClipInfo, ClipSettings, Job, Project, new_id
from pipeline import (extract_audio, make_zip, render_clip, select_auto_clips,
                      uniform_clips)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="ClipForge")
api = APIRouter(prefix="/api")

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

    if free_disk_bytes(UPLOAD_DIR) < 500 * 1024 * 1024:
        raise HTTPException(status_code=507, detail="Spazio su disco insufficiente.")

    project_id = new_id()
    pdir = UPLOAD_DIR / project_id
    pdir.mkdir(parents=True, exist_ok=True)
    safe = sanitize_filename(original)
    stored = pdir / f"original{ext}"

    size = 0
    try:
        with open(stored, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="File troppo grande (max 2GB).")
                out.write(chunk)
    except HTTPException:
        shutil.rmtree(pdir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(pdir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Upload interrotto: {e}")

    if size == 0:
        shutil.rmtree(pdir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="File vuoto.")

    try:
        meta = await probe_video(stored)
    except ValueError as e:
        shutil.rmtree(pdir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(e))

    await generate_thumbnail(stored, project_id, at_sec=min(1.0, meta["duration"] / 2))

    project = Project(
        id=project_id, name=safe, original_filename=original,
        stored_filename=stored.name, ext=ext, **meta,
    )
    await db.projects.insert_one(project.model_dump())
    return _project_summary(project.model_dump())


@api.get("/projects")
async def list_projects():
    docs = await db.projects.find({}, {"_id": 0, "segments": 0}).sort("created_at", -1).to_list(200)
    return [_project_summary(d) for d in docs]


@api.get("/projects/{project_id}")
async def get_project(project_id: str):
    p = await _get_project(project_id)
    return _project_summary(p)


@api.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    await _get_project(project_id)
    for d in (UPLOAD_DIR / project_id, OUTPUT_DIR / project_id):
        shutil.rmtree(d, ignore_errors=True)
    (THUMB_DIR / f"{project_id}.jpg").unlink(missing_ok=True)
    (ZIP_DIR / f"{project_id}.zip").unlink(missing_ok=True)
    await db.projects.delete_one({"id": project_id})
    await db.jobs.delete_many({"project_id": project_id})
    return {"deleted": True}


# --------------------- media serving ---------------------
@api.get("/media/thumb/{project_id}")
async def media_thumb(project_id: str):
    p = THUMB_DIR / f"{sanitize_filename(project_id)}.jpg"
    if not p.exists():
        raise HTTPException(status_code=404, detail="Anteprima non disponibile.")
    return FileResponse(p, media_type="image/jpeg")


@api.get("/media/original/{project_id}")
async def media_original(project_id: str):
    proj = await _get_project(project_id)
    p = UPLOAD_DIR / project_id / proj["stored_filename"]
    if not p.exists():
        raise HTTPException(status_code=404, detail="Video originale non disponibile.")
    return FileResponse(p)


@api.get("/media/clip/{project_id}/{name}")
async def media_clip(project_id: str, name: str, dl: int = 0):
    safe = sanitize_filename(name)
    p = OUTPUT_DIR / project_id / safe
    if not p.exists() or p.parent != (OUTPUT_DIR / project_id):
        raise HTTPException(status_code=404, detail="Clip non trovata.")
    if dl:
        return FileResponse(p, media_type="video/mp4", filename=safe)
    return FileResponse(p, media_type="video/mp4")


@api.get("/media/zip/{project_id}")
async def media_zip(project_id: str):
    p = ZIP_DIR / f"{sanitize_filename(project_id)}.zip"
    if not p.exists():
        raise HTTPException(status_code=404, detail="Archivio ZIP non disponibile.")
    return FileResponse(p, media_type="application/zip", filename=f"clipforge_{project_id}.zip")


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
        job.status = "failed"
        job.error = "Progetto non trovato."
        await _save_job(job)
        return
    project = Project(**pdoc)
    video_path = UPLOAD_DIR / project.id / project.stored_filename
    out_dir = OUTPUT_DIR / project.id
    out_dir.mkdir(parents=True, exist_ok=True)
    settings = job.settings

    job.status = "processing"
    job.progress = 2
    job.stage = "Preparazione"
    await _save_job(job)

    try:
        segments = project.segments
        need_transcription = settings.subtitles or (settings.auto_find and not manual)
        if need_transcription and not segments and project.has_audio:
            job.stage = "Trascrizione audio (Whisper)"
            job.progress = 5
            await _save_job(job)
            wav = out_dir / "audio.wav"
            if await extract_audio(video_path, wav):
                from transcription import transcribe
                segments = await transcribe(wav)
                wav.unlink(missing_ok=True)
                await db.projects.update_one({"id": project.id}, {"$set": {"segments": segments}})
            else:
                segments = []
        job.progress = 25
        await _save_job(job)

        # decide clips
        if manual:
            clips = job.clips
        elif settings.auto_find and segments:
            clips = select_auto_clips(segments, settings.num_clips, float(settings.clip_duration))
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
            clip.status = "processing"
            clip.progress = 0
            job.stage = f"Elaborazione clip {i + 1} di {total}"
            await _save_job(job)

            base = 25.0 + span * i
            filename = f"edit_{job.id[:8]}_{i + 1}.mp4" if manual else f"clip_{i + 1}.mp4"
            out_path = out_dir / filename

            async def progress_cb(pct, _clip=clip, _base=base):
                _clip.progress = pct
                job.progress = int(_base + span * (pct / 100.0))
                await _save_job(job)

            try:
                await render_clip(video_path, clip, settings, segments or [], out_path, progress_cb)
                clip.status = "completed"
                clip.progress = 100
                clip.filename = filename
                completed_files.append(filename)
                # cleanup ass file
                out_path.with_suffix(".ass").unlink(missing_ok=True)
            except Exception as e:
                logger.exception("Render clip %s fallito", i)
                clip.status = "failed"
                clip.error = str(e)[:300]
            await _save_job(job)

        if completed_files and not manual:
            job.zip_filename = make_zip(project.id, completed_files)
            await db.projects.update_one({"id": project.id},
                                         {"$set": {"clip_count": len(completed_files)}})

        if completed_files:
            job.status = "completed"
            job.progress = 100
            job.stage = "Completato"
        else:
            job.status = "failed"
            job.error = job.error or "Nessuna clip è stata generata con successo."
            job.stage = "Errore"
        await _save_job(job)

    except Exception as e:
        logger.exception("Job fallito")
        job.status = "failed"
        job.error = str(e)[:400]
        job.stage = "Errore"
        await _save_job(job)


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
