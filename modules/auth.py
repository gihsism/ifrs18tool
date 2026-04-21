"""Google Sign-In wrapper around Streamlit's native st.login().

If `[auth]` is not configured in `st.secrets`, everything degrades gracefully:
`user_email()` returns None and the sidebar controls are hidden. That means
local dev works without any OAuth setup, and signing in is only offered on
deployments that have secrets configured.
"""

import streamlit as st


def auth_configured() -> bool:
    """True when Streamlit secrets contain an [auth] section."""
    try:
        return "auth" in st.secrets
    except Exception:
        return False


def user_email() -> str | None:
    """Return the signed-in user's email, or None if anonymous / unconfigured."""
    if not auth_configured():
        return None
    try:
        if st.user.is_logged_in:
            return st.user.email
    except Exception:
        pass
    return None


def render_auth_sidebar():
    """Sign-in / sign-out controls and the 'save history' banner."""
    if not auth_configured():
        return

    email = user_email()
    if email:
        st.sidebar.success(f"Signed in as {email}")
        if st.sidebar.button("Sign out", key="auth_signout"):
            st.logout()
    else:
        st.sidebar.info(
            "**Want to save your projects across sessions?**\n\n"
            "Sign in with Google — otherwise your work is kept only for "
            "this browser session."
        )
        if st.sidebar.button("Sign in with Google", key="auth_signin", type="primary"):
            st.login("google")
