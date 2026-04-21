"""Google Drive backend for per-user project persistence.

Each project is stored as a single zip in the user's own Google Drive,
inside a folder named "IFRS 18 Tool". We only see files we create
(the `drive.file` scope keeps us out of the rest of the user's Drive).

Requires the user to be signed in via Streamlit's native `st.login`,
with `expose_tokens = ["access"]` and the Drive scope requested —
see README-style setup notes in the conversation / SETUP.md.

Gracefully no-ops when not configured or unauthenticated so local dev
keeps working.
"""

import io
import shutil
import zipfile
from pathlib import Path

import streamlit as st

FOLDER_NAME = "IFRS 18 Tool"
DRIVE_API = "https://www.googleapis.com/drive/v3"
UPLOAD_API = "https://www.googleapis.com/upload/drive/v3/files"


def drive_available() -> bool:
    """True when a Drive access token is exposed by st.login."""
    try:
        if not st.user.is_logged_in:
            return False
        _ = st.user.tokens["access"]
        return True
    except Exception:
        return False


def _access_token() -> str | None:
    try:
        return st.user.tokens["access"]
    except Exception:
        return None


def _headers():
    return {"Authorization": f"Bearer {_access_token()}"}


def _zip_dir(src: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path in src.rglob("*"):
            if path.is_file():
                z.write(path, arcname=path.relative_to(src))
    return buf.getvalue()


def _unzip_to(data: bytes, dest: Path):
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(dest)


@st.cache_data(ttl=60, show_spinner=False)
def _folder_id_cached(token_hash: str) -> str | None:
    """Cache the folder id per access token so we don't hit Drive every run."""
    return _ensure_folder()


def _folder_id() -> str | None:
    token = _access_token()
    if not token:
        return None
    return _folder_id_cached(str(hash(token)))


def _ensure_folder() -> str | None:
    """Find or create the 'IFRS 18 Tool' folder; return its Drive file id."""
    import requests

    params = {
        "q": (
            f"name = '{FOLDER_NAME}' and "
            "mimeType = 'application/vnd.google-apps.folder' and "
            "trashed = false"
        ),
        "fields": "files(id,name)",
        "spaces": "drive",
    }
    try:
        r = requests.get(f"{DRIVE_API}/files", headers=_headers(), params=params, timeout=15)
        r.raise_for_status()
        files = r.json().get("files", [])
        if files:
            return files[0]["id"]
        # Create folder
        r = requests.post(
            f"{DRIVE_API}/files",
            headers={**_headers(), "Content-Type": "application/json"},
            json={"name": FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()["id"]
    except Exception:
        return None


def _find_zip(folder_id: str, project_name: str) -> str | None:
    import requests
    fname = f"{project_name}.zip"
    params = {
        "q": f"name = '{fname}' and '{folder_id}' in parents and trashed = false",
        "fields": "files(id,name,modifiedTime)",
        "spaces": "drive",
    }
    try:
        r = requests.get(f"{DRIVE_API}/files", headers=_headers(), params=params, timeout=15)
        r.raise_for_status()
        files = r.json().get("files", [])
        return files[0]["id"] if files else None
    except Exception:
        return None


def upload_project(email: str, project_name: str, local_dir: Path) -> bool:
    """Zip local project dir and push to the user's Drive (create or update)."""
    if not drive_available() or not local_dir.exists():
        return False

    import requests

    folder_id = _folder_id()
    if not folder_id:
        return False

    try:
        data = _zip_dir(local_dir)
        existing_id = _find_zip(folder_id, project_name)

        # Multipart upload (metadata + media)
        import json as _json
        metadata = {"name": f"{project_name}.zip"}
        if not existing_id:
            metadata["parents"] = [folder_id]

        boundary = "----ifrs18-boundary-a3k2"
        body = (
            f"--{boundary}\r\n"
            "Content-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{_json.dumps(metadata)}\r\n"
            f"--{boundary}\r\n"
            "Content-Type: application/zip\r\n\r\n"
        ).encode("utf-8") + data + f"\r\n--{boundary}--".encode("utf-8")

        headers = {
            **_headers(),
            "Content-Type": f"multipart/related; boundary={boundary}",
        }

        if existing_id:
            url = f"{UPLOAD_API}/{existing_id}?uploadType=multipart"
            r = requests.patch(url, headers=headers, data=body, timeout=30)
        else:
            url = f"{UPLOAD_API}?uploadType=multipart"
            r = requests.post(url, headers=headers, data=body, timeout=30)
        r.raise_for_status()
        return True
    except Exception:
        return False


def download_project(email: str, project_name: str, local_dir: Path) -> bool:
    """Download the user's project zip from Drive and unzip to local_dir."""
    if not drive_available():
        return False

    import requests

    folder_id = _folder_id()
    if not folder_id:
        return False

    file_id = _find_zip(folder_id, project_name)
    if not file_id:
        return False

    try:
        r = requests.get(
            f"{DRIVE_API}/files/{file_id}?alt=media",
            headers=_headers(),
            timeout=60,
        )
        r.raise_for_status()
        _unzip_to(r.content, local_dir)
        return True
    except Exception:
        return False


def delete_project(email: str, project_name: str) -> bool:
    if not drive_available():
        return False

    import requests

    folder_id = _folder_id()
    if not folder_id:
        return False

    file_id = _find_zip(folder_id, project_name)
    if not file_id:
        return True  # already absent

    try:
        r = requests.delete(
            f"{DRIVE_API}/files/{file_id}", headers=_headers(), timeout=15
        )
        r.raise_for_status()
        return True
    except Exception:
        return False


def list_project_names(email: str) -> list[str]:
    """List zip-backed project names in the user's Drive folder."""
    if not drive_available():
        return []

    import requests

    folder_id = _folder_id()
    if not folder_id:
        return []

    try:
        params = {
            "q": f"'{folder_id}' in parents and trashed = false and mimeType = 'application/zip'",
            "fields": "files(name)",
            "spaces": "drive",
            "pageSize": 200,
        }
        r = requests.get(
            f"{DRIVE_API}/files", headers=_headers(), params=params, timeout=15
        )
        r.raise_for_status()
        names = []
        for f in r.json().get("files", []):
            n = f.get("name", "")
            if n.endswith(".zip"):
                names.append(n[:-4])
        return sorted(names)
    except Exception:
        return []
