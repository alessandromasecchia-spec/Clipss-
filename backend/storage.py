import logging
import os
from pathlib import Path

import requests

logger = logging.getLogger("clipforge.storage")

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
APP_NAME = "clipforge"

_storage_key = None


def _get_url():
    base = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
    return base.rstrip("/") + "/objstore/api/v1/storage"


def init_storage(force: bool = False):
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    emergent_key = os.environ.get("EMERGENT_LLM_KEY")
    resp = requests.post(f"{_get_url()}/init", json={"emergent_key": emergent_key}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def put_bytes(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = requests.put(
        f"{_get_url()}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=600,
    )
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.put(
            f"{_get_url()}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data, timeout=600,
        )
    resp.raise_for_status()
    return resp.json()


def get_bytes(path: str) -> tuple[bytes, str]:
    key = init_storage()
    resp = requests.get(f"{_get_url()}/objects/{path}", headers={"X-Storage-Key": key}, timeout=600)
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.get(f"{_get_url()}/objects/{path}", headers={"X-Storage-Key": key}, timeout=600)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


def put_file(path: str, local_path: Path, content_type: str) -> dict:
    return put_bytes(path, local_path.read_bytes(), content_type)


def download_to(path: str, local_path: Path) -> Path:
    data, _ = get_bytes(path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(data)
    return local_path


# object storage path builders
def orig_path(pid: str, ext: str) -> str:
    return f"{APP_NAME}/uploads/{pid}/original{ext}"


def thumb_path(pid: str) -> str:
    return f"{APP_NAME}/thumbs/{pid}.jpg"


def clip_path(pid: str, filename: str) -> str:
    return f"{APP_NAME}/outputs/{pid}/{filename}"


def zip_path(pid: str) -> str:
    return f"{APP_NAME}/zips/{pid}.zip"


def asset_path(pid: str, name: str) -> str:
    return f"{APP_NAME}/uploads/{pid}/assets/{name}"
