"""ClipForge Phase 6 backend tests: silence removal, smart zoom, subtitles word highlight,
export presets, music+overlay, batch semaphore serialization, tone-only fallback."""
import os
import subprocess
import time
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"

SPEECH = "/tmp/test_speech.mp4"
LAND = "/tmp/test_land.mp4"
GAP = "/tmp/test_gap.mp4"
MUSIC = "/tmp/music.wav"
LOGO = "/tmp/logo.png"


def _wait(job_id, timeout=200):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        r = requests.get(f"{API}/jobs/{job_id}", timeout=15)
        assert r.status_code == 200
        last = r.json()
        if last["status"] in ("completed", "failed"):
            return last
        time.sleep(2)
    raise AssertionError(f"Timeout job={job_id} last stage={last and last.get('stage')}")


def _upload(path):
    with open(path, "rb") as fh:
        r = requests.post(f"{API}/upload",
                          files={"file": (Path(path).name, fh, "video/mp4")},
                          timeout=90)
    assert r.status_code == 200, r.text
    return r.json()


def _probe(url_or_path, streams=False):
    args = ["ffprobe", "-v", "error", "-show_format"]
    if streams:
        args += ["-show_streams"]
    args += ["-of", "json", str(url_or_path)]
    return subprocess.check_output(args).decode()


def _download_clip(pid, fname, out):
    r = requests.get(f"{API}/media/clip/{pid}/{fname}", timeout=60)
    assert r.status_code == 200
    Path(out).write_bytes(r.content)


# ---------- Regression: full flow still works ----------
def test_regression_full_flow_9x16():
    p = _upload(LAND)
    pid = p["id"]
    settings = {
        "aspect_ratio": "9:16", "clip_duration": 5, "num_clips": 1,
        "subtitles": False, "auto_find": False,
        "face_tracking": True, "auto_crop": True, "audio_normalize": True,
    }
    r = requests.post(f"{API}/projects/{pid}/process", json=settings, timeout=15)
    assert r.status_code == 200
    final = _wait(r.json()["id"], timeout=180)
    assert final["status"] == "completed"
    assert final["clips"][0]["status"] == "completed"
    fname = final["clips"][0]["filename"]
    # media serving + range
    rc = requests.get(f"{API}/media/clip/{pid}/{fname}", timeout=30)
    assert rc.status_code == 200 and rc.headers["content-type"] == "video/mp4"
    rng = requests.get(f"{API}/media/clip/{pid}/{fname}", headers={"Range": "bytes=0-99"}, timeout=30)
    assert rng.status_code == 206
    assert rng.headers.get("Content-Range", "").startswith("bytes 0-99/")
    # zip
    rz = requests.get(f"{API}/media/zip/{pid}", timeout=30)
    assert rz.status_code == 200
    # 1080x1920
    out = "/tmp/_reg.mp4"; _download_clip(pid, fname, out)
    info = _probe(out, streams=True)
    assert '"width": 1080' in info and '"height": 1920' in info


# ---------- Silence removal actually shortens output ----------
def test_silence_removal_high_shortens():
    p = _upload(GAP)
    pid = p["id"]
    orig_dur = float(p["duration"])
    settings = {
        "aspect_ratio": "9:16", "clip_duration": int(orig_dur) + 2, "num_clips": 1,
        "subtitles": False, "auto_find": False, "face_tracking": False,
        "auto_crop": True, "audio_normalize": False,
        "silence_removal": "high",
    }
    r = requests.post(f"{API}/projects/{pid}/process", json=settings, timeout=15)
    assert r.status_code == 200
    final = _wait(r.json()["id"], timeout=200)
    assert final["status"] == "completed", final
    fname = final["clips"][0]["filename"]
    out = "/tmp/_sil.mp4"; _download_clip(pid, fname, out)
    dur = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", out]).strip())
    # gap file has ~2.5s of silence; expect meaningful cut
    assert dur < orig_dur - 1.0, f"Expected shortening, orig={orig_dur} out={dur}"


# ---------- Smart zoom + punch_in renders ----------
def test_smart_zoom_punch_in():
    p = _upload(LAND)
    pid = p["id"]
    settings = {
        "aspect_ratio": "9:16", "clip_duration": 5, "num_clips": 1,
        "subtitles": False, "auto_find": False, "face_tracking": False,
        "auto_crop": True, "audio_normalize": False,
        "smart_zoom": "medium", "zoom_mode": "punch_in",
    }
    r = requests.post(f"{API}/projects/{pid}/process", json=settings, timeout=15)
    final = _wait(r.json()["id"], timeout=180)
    assert final["status"] == "completed", final


# ---------- Word highlight subtitles ----------
def test_word_highlight_subtitles():
    p = _upload(SPEECH)
    pid = p["id"]
    settings = {
        "aspect_ratio": "9:16", "clip_duration": 6, "num_clips": 1,
        "subtitles": True, "auto_find": False,
        "face_tracking": False, "auto_crop": True, "audio_normalize": True,
        "subtitle_style": {
            "preset": "bold", "font": "DejaVu Sans", "size": 66,
            "color": "#FFFFFF", "highlight_color": "#FFE600",
            "background": False, "bg_color": "#000000", "shadow": True,
            "outline": 4, "bold": True, "position": "bottom", "alignment": "center",
            "max_words_per_line": 3, "word_highlight": True,
        },
    }
    r = requests.post(f"{API}/projects/{pid}/process", json=settings, timeout=15)
    final = _wait(r.json()["id"], timeout=240)
    assert final["status"] == "completed", final
    fname = final["clips"][0]["filename"]
    rc = requests.get(f"{API}/media/clip/{pid}/{fname}", timeout=30)
    assert rc.status_code == 200


# ---------- Export preset social_small (smaller/higher CRF) ----------
def test_export_preset_social_small():
    p = _upload(LAND)
    pid = p["id"]
    settings = {
        "aspect_ratio": "9:16", "clip_duration": 5, "num_clips": 1,
        "subtitles": False, "auto_find": False, "face_tracking": False,
        "auto_crop": True, "audio_normalize": False,
        "export_preset": "social_small",
    }
    r = requests.post(f"{API}/projects/{pid}/process", json=settings, timeout=15)
    final = _wait(r.json()["id"], timeout=180)
    assert final["status"] == "completed"
    fname = final["clips"][0]["filename"]
    out = "/tmp/_small.mp4"; _download_clip(pid, fname, out)
    info = _probe(out, streams=True)
    assert '"codec_name": "h264"' in info


# ---------- Music + overlay upload and render ----------
def test_music_and_overlay():
    p = _upload(SPEECH)
    pid = p["id"]
    with open(MUSIC, "rb") as fh:
        r = requests.post(f"{API}/projects/{pid}/audio",
                          files={"file": ("music.wav", fh, "audio/wav")}, timeout=30)
    assert r.status_code == 200, r.text
    music_name = r.json()["name"]
    with open(LOGO, "rb") as fh:
        r = requests.post(f"{API}/projects/{pid}/overlay",
                          files={"file": ("logo.png", fh, "image/png")}, timeout=30)
    assert r.status_code == 200
    overlay_name = r.json()["name"]

    settings = {
        "aspect_ratio": "9:16", "clip_duration": 6, "num_clips": 1,
        "subtitles": False, "auto_find": False, "face_tracking": False,
        "auto_crop": True, "audio_normalize": False,
        "music": {"name": music_name, "volume": 0.3, "start_offset": 0,
                  "fade_in": 0.5, "fade_out": 0.5, "loop": True},
        "overlay": {"name": overlay_name, "x": 0.5, "y": 0.06,
                    "scale": 0.28, "opacity": 1.0, "start": 0, "end": 0},
    }
    r = requests.post(f"{API}/projects/{pid}/process", json=settings, timeout=15)
    final = _wait(r.json()["id"], timeout=240)
    assert final["status"] == "completed", final
    fname = final["clips"][0]["filename"]
    out = "/tmp/_mo.mp4"; _download_clip(pid, fname, out)
    info = _probe(out, streams=True)
    # video + audio stream present
    assert '"codec_type": "video"' in info
    assert '"codec_type": "audio"' in info


# ---------- Batch serialization (semaphore) ----------
def test_batch_serialization_semaphore():
    p1 = _upload(LAND); p2 = _upload(LAND)
    settings = {
        "aspect_ratio": "9:16", "clip_duration": 5, "num_clips": 1,
        "subtitles": False, "auto_find": False, "face_tracking": False,
        "auto_crop": True, "audio_normalize": False,
    }
    j1 = requests.post(f"{API}/projects/{p1['id']}/process", json=settings, timeout=15).json()
    j2 = requests.post(f"{API}/projects/{p2['id']}/process", json=settings, timeout=15).json()
    # observe that at some point only one is processing while the other is queued
    saw_serial = False
    t0 = time.time()
    while time.time() - t0 < 60:
        d1 = requests.get(f"{API}/jobs/{j1['id']}").json()
        d2 = requests.get(f"{API}/jobs/{j2['id']}").json()
        st = {d1["status"], d2["status"]}
        if "processing" in st and "queued" in st:
            saw_serial = True
        if d1["status"] in ("completed", "failed") and d2["status"] in ("completed", "failed"):
            break
        time.sleep(1)
    f1 = _wait(j1["id"], timeout=200)
    f2 = _wait(j2["id"], timeout=200)
    assert f1["status"] == "completed" and f2["status"] == "completed"
    assert saw_serial, "Never observed serialization (both processing simultaneously)"


# ---------- Tone-only video: auto_find + subtitles should NOT crash, falls back to uniform ----------
def test_tone_only_autofind_fallback():
    p = _upload(LAND)  # testsrc + tone (no speech)
    pid = p["id"]
    settings = {
        "aspect_ratio": "9:16", "clip_duration": 5, "num_clips": 1,
        "subtitles": True, "auto_find": True,
        "face_tracking": False, "auto_crop": True, "audio_normalize": True,
    }
    r = requests.post(f"{API}/projects/{pid}/process", json=settings, timeout=15)
    final = _wait(r.json()["id"], timeout=240)
    assert final["status"] == "completed", f"Should degrade gracefully, got {final}"
    assert len(final["clips"]) == 1
    assert final["clips"][0]["status"] == "completed"
