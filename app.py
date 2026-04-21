"""IFRS 18 Conversion Tool — Main Streamlit Application."""

import streamlit as st

st.set_page_config(
    page_title="IFRS 18 Conversion Tool",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

from modules.data_input import render_data_input
from modules.classification import render_classification
from modules.pnl_analysis import render_pnl_analysis
from modules.bs_analysis import render_bs_analysis
from modules.cf_analysis_full import render_cf_analysis_full
from modules.transition import render_transition
from modules.persistence import (
    auto_load_if_needed,
    auto_save,
    get_save_time,
    has_saved_session,
    delete_session,
    save_session,
    list_projects,
    load_session,
)
from modules.auth import render_auth_sidebar, auth_configured, user_email


def main():
    # Auto-load previous session on startup
    auto_load_if_needed()

    st.title("IFRS 18 Conversion Tool")
    st.caption("Presentation and Disclosure in Financial Statements")

    # Sidebar navigation
    st.sidebar.header("Navigation")
    page = st.sidebar.radio(
        "Select Step",
        [
            "1. Data Input",
            "2. Classification",
            "3. Income Statement (P&L)",
            "4. Balance Sheet",
            "5. Cash Flow Statement",
            "6. Transition & Export",
        ],
    )

    st.sidebar.markdown("---")
    st.sidebar.header("Entity Settings")
    entity_type = st.sidebar.selectbox(
        "Main Business Activity",
        [
            "General (non-financial)",
            "Banking / Lending",
            "Insurance",
            "Investment Entity",
        ],
        help="Entities whose main business is investing or financing "
        "classify related income/expenses as operating.",
    )
    st.session_state["entity_type"] = entity_type

    # Auth controls in sidebar
    st.sidebar.markdown("---")
    st.sidebar.header("Account")
    render_auth_sidebar()

    # Save/Load controls in sidebar
    st.sidebar.markdown("---")
    st.sidebar.header("Project")
    _render_project_controls()

    # Route to page
    if page.startswith("1"):
        render_data_input()
    elif page.startswith("2"):
        render_classification()
    elif page.startswith("3"):
        render_pnl_analysis()
    elif page.startswith("4"):
        render_bs_analysis()
    elif page.startswith("5"):
        render_cf_analysis_full()
    elif page.startswith("6"):
        render_transition()

    # Auto-save after every interaction
    auto_save()


def _render_project_controls():
    """Save/load/clear controls in the sidebar."""
    save_time = get_save_time("autosave")
    if save_time:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(save_time)
            st.sidebar.caption(f"Auto-saved: {dt:%Y-%m-%d %H:%M}")
        except Exception:
            st.sidebar.caption(f"Auto-saved: {save_time}")

    # Save As
    with st.sidebar.expander("Save / Load Project"):
        # Save with name
        proj_name = st.text_input("Project name", value="my_project", key="proj_name")
        if st.button("Save Project"):
            save_session(proj_name)
            st.success(f"Saved as '{proj_name}'")

        # Nudge anonymous users when auth is available but they're not signed in
        if auth_configured() and not user_email():
            st.info(
                "Sign in (top of sidebar) to keep your projects across "
                "sessions and devices.",
                icon="☁️",
            )

        # List saved projects
        projects = list_projects()
        if projects:
            st.markdown("**Saved projects:**")
            for p in projects:
                name = p.get("dir_name", "?")
                saved = p.get("saved_at", "?")
                location = p.get("location", "local")
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(saved)
                    saved = f"{dt:%Y-%m-%d %H:%M}"
                except Exception:
                    pass
                badge = {"local": "", "synced": " · ☁️", "cloud": " · ☁️"}.get(location, "")
                col1, col2 = st.columns([3, 1])
                with col1:
                    if st.button(f"{name}", key=f"load_{name}"):
                        load_session(name)
                        st.rerun()
                with col2:
                    st.caption(f"{saved}{badge}")

    # Download / upload zip — universal fallback for users who don't sign in
    _render_zip_transfer()

    # Clear
    if st.sidebar.button("Clear All Data"):
        for key in list(st.session_state.keys()):
            if key not in ("_persistence_loaded",):
                del st.session_state[key]
        delete_session("autosave")
        st.rerun()


def _render_zip_transfer():
    """Download current session as zip / upload a previously saved zip.

    Works for every user regardless of sign-in state. A safety net so nobody
    is locked out of saving their work.
    """
    from modules.persistence import PROJECTS_DIR, _project_dir, auto_save
    from pathlib import Path
    import io
    import zipfile

    with st.sidebar.expander("Download / Upload as file"):
        st.caption(
            "Export your project as a `.zip` to save anywhere (Box, SharePoint, "
            "email). Upload it later to restore."
        )

        # Download: zip the autosave project dir in memory
        autosave_dir = _project_dir("autosave")
        if autosave_dir.exists():
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for p in autosave_dir.rglob("*"):
                    if p.is_file():
                        z.write(p, arcname=p.relative_to(autosave_dir))
            st.download_button(
                "Download current project",
                data=buf.getvalue(),
                file_name="ifrs18_project.zip",
                mime="application/zip",
                key="dl_proj_zip",
            )
        else:
            st.caption("Nothing to download yet — load data first.")

        # Upload: accept a zip, extract into autosave dir, rerun
        uploaded = st.file_uploader(
            "Restore from file", type=["zip"], key="upload_proj_zip",
            label_visibility="collapsed",
        )
        if uploaded is not None and st.button("Restore this file", key="restore_btn"):
            try:
                if autosave_dir.exists():
                    import shutil
                    shutil.rmtree(autosave_dir)
                autosave_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(io.BytesIO(uploaded.read())) as z:
                    z.extractall(autosave_dir)
                # Clear in-memory state so load_session repopulates cleanly
                for k in list(st.session_state.keys()):
                    if k != "_persistence_loaded":
                        del st.session_state[k]
                load_session("autosave")
                st.rerun()
            except Exception as e:
                st.error(f"Could not restore: {e}")


if __name__ == "__main__":
    main()
