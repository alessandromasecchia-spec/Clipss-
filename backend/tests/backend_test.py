"""ClipForge backend API tests."""
import os
import time
import pytest
import requests
from pathlib import Path

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback: read from frontend/.env
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"
LAND = "/tmp/test_land.mp4"
SPEECH = "/tmp/test_speech.mp4"


def _wait_job(job_id, timeout=180):
    start = time.time()
    last = None
    while time.time() - start < timeout:
        r = requests.get(f"{API}/jobs/{job_id}", timeout=15)
        assert r.status_code == 200
        last = r.json()
        if last["status"] in ("completed", "failed"):
            return last
        time.sleep(2)
    raise AssertionError(f"Timeout job={job_id} last={last}")


@pytest.fixture(scope="session")
def uploaded_land():
    assert Path(LAND).exists()
    with open(LAND, "rb") as fh:
        r = requests.post(f"{API}/upload",
                          files={"file": ("test_land.mp4", fh, "video/mp4")},
                          timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


def test_root():
    r = requests.get(f"{API}/", timeout=10)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_upload_rejects_txt():
    r = requests.post(f"{API}/upload",
                      files={"file": ("test.txt", b"hello", "text/plain")},
                      timeout=15)
    assert r.status_code == 400


def test_upload_land(uploaded_land):
    p = uploaded_land
    for k in ("id", "duration", "width", "height", "fps", "size_bytes", "has_audio"):
        assert k in p, f"missing {k}"
    assert p["width"] == 1280
    assert p["height"] == 720
    assert p["has_audio"] is True
    assert p["duration"] > 10


def test_list_and_get_project(uploaded_land):
    pid = uploaded_land["id"]
    r = requests.get(f"{API}/projects", timeout=10)
    assert r.status_code == 200
    assert any(x["id"] == pid for x in r.json())
    r2 = requests.get(f"{API}/projects/{pid}", timeout=10)
    assert r2.status_code == 200 and r2.json()["id"] == pid


def test_media_endpoints(uploaded_land):
    pid = uploaded_land["id"]
    r = requests.get(f"{API}/media/thumb/{pid}", timeout=10)
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/")
    r = requests.get(f"{API}/media/original/{pid}", timeout=20)
    assert r.status_code == 200


def test_process_uniform_2clips(uploaded_land):
    pid = uploaded_land["id"]
    settings = {
        "aspect_ratio": "9:16", "clip_duration": 6, "num_clips": 2,
        "subtitles": False, "auto_find": False,
        "face_tracking": True, "auto_crop": True, "audio_normalize": True,
    }
    r = requests.post(f"{API}/projects/{pid}/process", json=settings, timeout=15)
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["status"] == "queued"
    final = _wait_job(job["id"], timeout=180)
    assert final["status"] == "completed", final
    assert final["progress"] == 100
    assert final.get("zip_filename")
    assert len(final["clips"]) == 2
    for c in final["clips"]:
        assert c["status"] == "completed"
        assert c["filename"].startswith("clip_")
        # verify file served
        rc = requests.get(f"{API}/media/clip/{pid}/{c['filename']}", timeout=20)
        assert rc.status_code == 200
        assert rc.headers["content-type"] == "video/mp4"
    # verify dimensions via ffprobe
    import subprocess, json as _json
    clip_path = f"/app/backend/storage/outputs/{pid}/{final['clips'][0]['filename']}"
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,codec_name",
        "-of", "json", clip_path])
    info = _json.loads(out)["streams"][0]
    assert info["width"] == 1080 and info["height"] == 1920
    assert info["codec_name"] == "h264"
    # zip endpoint
    rz = requests.get(f"{API}/media/zip/{pid}", timeout=15)
    assert rz.status_code == 200


def test_render_single_clip(uploaded_land):
    pid = uploaded_land["id"]
    payload = {
        "start": 1.0, "end": 5.0,
        "settings": {
            "aspect_ratio": "9:16", "clip_duration": 4, "num_clips": 1,
            "subtitles": False, "auto_find": False,
            "face_tracking": True, "auto_crop": True, "audio_normalize": True,
        }
    }
    r = requests.post(f"{API}/projects/{pid}/render-clip", json=payload, timeout=15)
    assert r.status_code == 200, r.text
    job = r.json()
    final = _wait_job(job["id"], timeout=120)
    assert final["status"] == "completed"
    fname = final["clips"][0]["filename"]
    assert fname.startswith("edit_"), fname
    # ensure clip_1.mp4 still exists (not overwritten)
    assert Path(f"/app/backend/storage/outputs/{pid}/clip_1.mp4").exists()


def test_process_with_whisper_subtitles():
    assert Path(SPEECH).exists()
    with open(SPEECH, "rb") as fh:
        r = requests.post(f"{API}/upload",
                          files={"file": ("test_speech.mp4", fh, "video/mp4")},
                          timeout=60)
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    settings = {
        "aspect_ratio": "9:16", "clip_duration": 6, "num_clips": 1,
        "subtitles": True, "auto_find": True,
        "face_tracking": False, "auto_crop": True, "audio_normalize": True,
    }
    r = requests.post(f"{API}/projects/{pid}/process", json=settings, timeout=15)
    assert r.status_code == 200
    job = r.json()
    # poll to observe transcription stage
    saw_whisper = False
    t0 = time.time()
    while time.time() - t0 < 240:
        jr = requests.get(f"{API}/jobs/{job['id']}", timeout=10).json()
        if "Whisper" in (jr.get("stage") or ""):
            saw_whisper = True
        if jr["status"] in ("completed", "failed"):
            final = jr
            break
        time.sleep(2)
    else:
        pytest.fail("timeout")
    assert final["status"] == "completed", final
    assert saw_whisper, "Expected to observe 'Whisper' stage"
    # reason should be non-empty for auto-clip
    assert final["clips"][0].get("reason")
    # cleanup - delete project
    requests.delete(f"{API}/projects/{pid}", timeout=15)


def test_delete_project(uploaded_land):
    # create fresh throwaway upload
    with open(LAND, "rb") as fh:
        r = requests.post(f"{API}/upload",
                          files={"file": ("t.mp4", fh, "video/mp4")},
                          timeout=60)
    pid = r.json()["id"]
    d = requests.delete(f"{API}/projects/{pid}", timeout=15)
    assert d.status_code == 200
    g = requests.get(f"{API}/projects/{pid}", timeout=10)
    assert g.status_code == 404
