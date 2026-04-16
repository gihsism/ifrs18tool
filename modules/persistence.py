"""Auto-save and auto-load session state to disk.

Saves classified data, MPMs, CF items, transition notes, and entity settings
to a local `.ifrs18_projects/` directory as parquet + JSON.
On app start, automatically restores the last session.
"""

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
]

# Session state keys that hold JSON-serialisable data
_JSON_KEYS = [
    "entity_type",
    "mpms",
    "cf_items",       # DataFrame → serialised separately
    "_transition_notes",
    "expense_presentation",
    "classifications_confirmed",
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
    """Save current session state to disk."""
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
    """Load session state from disk. Returns True if data was loaded."""
    proj = _project_dir(project_name)
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
    """Delete a saved project."""
    proj = _project_dir(project_name)
    if proj.exists():
        shutil.rmtree(proj)


def list_projects() -> list[dict]:
    """List all saved projects with metadata."""
    if not PROJECTS_DIR.exists():
        return []
    projects = []
    for d in sorted(PROJECTS_DIR.iterdir()):
        if d.is_dir() and (d / "meta.json").exists():
            try:
                with open(d / "meta.json") as f:
                    meta = json.load(f)
                meta["dir_name"] = d.name
                projects.append(meta)
            except Exception:
                pass
    return projects


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
    """Load autosaved session if no data is currently in session state."""
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

    if has_saved_session("autosave"):
        load_session("autosave")
