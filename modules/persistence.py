"""Auto-save and auto-load session state to disk.

Saves classified data, MPMs, CF items, transition notes, and entity settings
to a local `.ifrs18_projects/` directory as parquet + JSON.
On app start, automatically restores the last session.
"""

import base64
import json
import os
import shutil
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

# Where projects are saved
PROJECTS_DIR = Path(".ifrs18_projects")

# Session state keys that hold DataFrames
_DF_KEYS = [
    "classified_pnl",
    "classified_bs",
    "classified_cf",
    "all_classified",
    "raw_upload",
]

# Session state keys that hold JSON-serialisable data
_JSON_KEYS = [
    "entity_type",
    "mpms",
    "cf_items",       # DataFrame → serialised separately
    "_transition_notes",
    "expense_presentation",
    "classifications_confirmed",
    "raw_upload_source",
]

# Keys that hold sets (need list conversion for JSON)
_SET_KEYS = [
    "loaded_statements",
]


def _project_dir(name: str) -> Path:
    return PROJECTS_DIR / name


def _ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def save_session(project_name: str = "autosave"):
    """Save current session state to disk. Silently fails on read-only filesystems.

    If the user is signed in and GCS is configured, also push a zipped copy
    to cloud storage so the project survives across sessions and devices.
    """
    try:
        _save_session_inner(project_name)
    except Exception:
        pass  # Read-only filesystem (e.g. Streamlit Cloud) — skip silently

    # Cloud sync (best-effort)
    try:
        from modules.auth import user_email
        from modules.cloud_storage import upload_project
        email = user_email()
        if email:
            upload_project(email, project_name, _project_dir(project_name))
    except Exception:
        pass


def _save_session_inner(project_name: str):
    proj = _project_dir(project_name)
    _ensure_dir(proj)

    # Save DataFrames as parquet
    for key in _DF_KEYS:
        if key in st.session_state and st.session_state[key] is not None:
            df = st.session_state[key]
            if isinstance(df, pd.DataFrame) and not df.empty:
                df.to_parquet(proj / f"{key}.parquet", index=False)

    # cf_items is also a DataFrame
    if "cf_items" in st.session_state:
        cf = st.session_state["cf_items"]
        if isinstance(cf, pd.DataFrame) and not cf.empty:
            cf.to_parquet(proj / "cf_items.parquet", index=False)

    # Save JSON-serialisable state
    json_state = {}
    for key in _JSON_KEYS:
        if key in st.session_state and key != "cf_items":
            val = st.session_state[key]
            if val is not None:
                json_state[key] = val

    for key in _SET_KEYS:
        if key in st.session_state:
            val = st.session_state[key]
            if isinstance(val, set):
                json_state[key] = list(val)

    if json_state:
        with open(proj / "state.json", "w") as f:
            json.dump(json_state, f, indent=2, default=str)

    # Save original uploaded file bytes (if any) under raw_files/
    raw_files = st.session_state.get("raw_upload_files_bytes")
    if isinstance(raw_files, dict) and raw_files:
        raw_dir = proj / "raw_files"
        # Reset directory so removed files don't linger
        if raw_dir.exists():
            shutil.rmtree(raw_dir)
        _ensure_dir(raw_dir)
        for fname, data in raw_files.items():
            try:
                with open(raw_dir / fname, "wb") as f:
                    f.write(data)
            except Exception:
                pass

    # Save metadata
    meta = {
        "saved_at": datetime.now().isoformat(),
        "project_name": project_name,
        "dataframes": [
            key for key in _DF_KEYS
            if key in st.session_state
            and isinstance(st.session_state.get(key), pd.DataFrame)
            and not st.session_state[key].empty
        ],
    }
    with open(proj / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_session(project_name: str = "autosave") -> bool:
    """Load session state from disk. Returns True if data was loaded.

    If signed in, pulls the cloud copy down first so the local directory
    reflects the latest cross-device state before reading.
    """
    proj = _project_dir(project_name)

    # Pull from cloud first when signed in — overwrites local copy so the
    # most recent cross-device save wins.
    try:
        from modules.auth import user_email
        from modules.cloud_storage import download_project
        email = user_email()
        if email:
            download_project(email, project_name, proj)
    except Exception:
        pass

    if not proj.exists():
        return False

    loaded_any = False

    # Load DataFrames
    for key in _DF_KEYS:
        parquet_path = proj / f"{key}.parquet"
        if parquet_path.exists():
            try:
                df = pd.read_parquet(parquet_path)
                st.session_state[key] = df
                loaded_any = True
            except Exception:
                pass

    # Load cf_items DataFrame
    cf_path = proj / "cf_items.parquet"
    if cf_path.exists():
        try:
            st.session_state["cf_items"] = pd.read_parquet(cf_path)
            loaded_any = True
        except Exception:
            pass

    # Load JSON state
    json_path = proj / "state.json"
    if json_path.exists():
        try:
            with open(json_path) as f:
                json_state = json.load(f)

            for key in _JSON_KEYS:
                if key in json_state and key != "cf_items":
                    st.session_state[key] = json_state[key]

            for key in _SET_KEYS:
                if key in json_state:
                    st.session_state[key] = set(json_state[key])
                    loaded_any = True
        except Exception:
            pass

    # Load original uploaded file bytes
    raw_dir = proj / "raw_files"
    if raw_dir.exists():
        files_bytes = {}
        for f in raw_dir.iterdir():
            if f.is_file():
                try:
                    files_bytes[f.name] = f.read_bytes()
                except Exception:
                    pass
        if files_bytes:
            st.session_state["raw_upload_files_bytes"] = files_bytes
            loaded_any = True

    return loaded_any


def get_save_time(project_name: str = "autosave") -> str | None:
    """Get the last save timestamp for a project."""
    meta_path = _project_dir(project_name) / "meta.json"
    if not meta_path.exists():
        return None
    try:
        with open(meta_path) as f:
            meta = json.load(f)
        return meta.get("saved_at")
    except Exception:
        return None


def has_saved_session(project_name: str = "autosave") -> bool:
    return (_project_dir(project_name) / "meta.json").exists()


def delete_session(project_name: str = "autosave"):
    """Delete a saved project, locally and in the cloud."""
    proj = _project_dir(project_name)
    if proj.exists():
        shutil.rmtree(proj)
    try:
        from modules.auth import user_email
        from modules.cloud_storage import delete_project
        email = user_email()
        if email:
            delete_project(email, project_name)
    except Exception:
        pass


def list_projects() -> list[dict]:
    """List saved projects with metadata.

    When signed in, merges local projects with cloud projects. Cloud-only
    projects are downloaded on demand when the user clicks them.
    """
    projects: dict[str, dict] = {}

    if PROJECTS_DIR.exists():
        for d in sorted(PROJECTS_DIR.iterdir()):
            if d.is_dir() and (d / "meta.json").exists():
                try:
                    with open(d / "meta.json") as f:
                        meta = json.load(f)
                    meta["dir_name"] = d.name
                    meta["location"] = "local"
                    projects[d.name] = meta
                except Exception:
                    pass

    try:
        from modules.auth import user_email
        from modules.cloud_storage import list_project_names
        email = user_email()
        if email:
            for name in list_project_names(email):
                if name in projects:
                    projects[name]["location"] = "synced"
                else:
                    projects[name] = {
                        "dir_name": name,
                        "project_name": name,
                        "saved_at": "cloud",
                        "location": "cloud",
                    }
    except Exception:
        pass

    return list(projects.values())


# ---------------------------------------------------------------------------
# Auto-save hook — call after any data change
# ---------------------------------------------------------------------------

def auto_save():
    """Auto-save if there's data worth saving."""
    has_data = any(
        key in st.session_state
        and isinstance(st.session_state.get(key), pd.DataFrame)
        and not st.session_state[key].empty
        for key in _DF_KEYS
    )
    if has_data:
        save_session("autosave")


# ---------------------------------------------------------------------------
# Auto-load on startup — call once at app start
# ---------------------------------------------------------------------------

def auto_load_if_needed():
    """Load autosaved session if no data is currently in session state.

    When signed in, tries to pull the cloud autosave first so returning
    users (including from a different device) see their last project.
    """
    if "_persistence_loaded" in st.session_state:
        return  # already attempted

    st.session_state["_persistence_loaded"] = True

    # Only load if session is empty
    has_data = any(
        key in st.session_state
        and isinstance(st.session_state.get(key), pd.DataFrame)
        for key in _DF_KEYS
    )
    if has_data:
        return

    try:
        from modules.auth import user_email
        from modules.cloud_storage import download_project
        email = user_email()
        if email:
            download_project(email, "autosave", _project_dir("autosave"))
    except Exception:
        pass

    if has_saved_session("autosave"):
        load_session("autosave")
