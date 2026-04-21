"""CSS polish for the Streamlit app — non-functional theming only.

Injected once at the top of main(). Touches nothing except visual appearance
so it can be reverted by deleting this module's single import.
"""

import streamlit as st


_CSS = """
<style>
/* ---- Typography: Inter with system fallback ---- */
html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"],
.stMarkdown, .stText, .stDataFrame, .stTable,
button, input, select, textarea {
  font-family: "Inter", -apple-system, BlinkMacSystemFont, "SF Pro Text",
               "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* Tighter, sharper headers */
h1, h2, h3, h4, h5, h6, [data-testid="stHeader"] h1,
[data-testid="stHeader"] h2, [data-testid="stHeader"] h3 {
  font-feature-settings: "ss01";
  letter-spacing: -0.015em !important;
  font-weight: 600 !important;
}
h1 { font-size: 1.9rem !important; line-height: 1.2 !important; }
h2 { font-size: 1.4rem !important; line-height: 1.25 !important; }
h3 { font-size: 1.1rem !important; line-height: 1.3 !important; }

/* Shrink the giant default title so the page feels less top-heavy */
[data-testid="stMainBlockContainer"] > div:first-child h1 {
  font-size: 1.7rem !important;
  margin-bottom: 0.25rem !important;
}

/* ---- Section cards: subtle borders around the main content blocks ---- */
[data-testid="stExpander"] {
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 10px;
  background: #ffffff;
  margin-bottom: 0.5rem;
}
[data-testid="stExpander"] summary {
  font-weight: 500;
}

[data-testid="stContainer"] > div:has(> [data-testid="stMarkdownContainer"]) {
  /* defensive — don't blanket-style unbordered containers */
}

/* ---- Buttons: sharper corners, clearer hover, primary emphasis ---- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
  border-radius: 8px !important;
  font-weight: 500 !important;
  border: 1px solid rgba(15, 23, 42, 0.12) !important;
  transition: all 0.12s ease-in-out !important;
  box-shadow: 0 1px 0 rgba(15, 23, 42, 0.03) !important;
}
.stButton > button:hover, .stDownloadButton > button:hover,
.stFormSubmitButton > button:hover {
  border-color: rgba(79, 70, 229, 0.45) !important;
  box-shadow: 0 2px 6px rgba(79, 70, 229, 0.1) !important;
  transform: translateY(-1px);
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
  background: linear-gradient(180deg, #6366F1 0%, #4F46E5 100%) !important;
  color: #fff !important;
  border: 0 !important;
  box-shadow: 0 2px 6px rgba(79, 70, 229, 0.28) !important;
}
.stButton > button[kind="primary"]:hover,
.stFormSubmitButton > button[kind="primary"]:hover {
  background: linear-gradient(180deg, #4F46E5 0%, #4338CA 100%) !important;
  box-shadow: 0 4px 10px rgba(79, 70, 229, 0.35) !important;
}

/* ---- Sidebar: tighter spacing, slightly muted ---- */
[data-testid="stSidebar"] {
  background: #F8FAFC !important;
  border-right: 1px solid rgba(15, 23, 42, 0.06);
}
[data-testid="stSidebar"] h2 {
  font-size: 0.78rem !important;
  font-weight: 600 !important;
  letter-spacing: 0.06em !important;
  text-transform: uppercase !important;
  color: rgba(15, 23, 42, 0.55) !important;
  margin-top: 0.6rem !important;
  margin-bottom: 0.4rem !important;
}
[data-testid="stSidebar"] hr {
  margin: 0.8rem 0 !important;
  opacity: 0.6;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label {
  font-weight: 500;
}

/* ---- Captions and muted text ---- */
.stCaption, [data-testid="stCaptionContainer"] {
  color: rgba(15, 23, 42, 0.55) !important;
  font-size: 0.82rem !important;
}

/* ---- Alerts (info / success / warning) — softer ---- */
[data-testid="stAlert"] {
  border-radius: 10px !important;
  border: 1px solid rgba(15, 23, 42, 0.05) !important;
  padding: 0.75rem 1rem !important;
}

/* ---- Tables / data editor: flatter borders ---- */
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {
  border-radius: 10px;
  overflow: hidden;
}

/* ---- Uploader: a bit less cramped ---- */
[data-testid="stFileUploader"] > section {
  border-radius: 10px !important;
  border-style: dashed !important;
  padding: 1.25rem !important;
}

/* ---- Tabs: clearer active state ---- */
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
  color: #4F46E5 !important;
  font-weight: 600 !important;
}

/* ---- Hide the "Made with Streamlit" footer and deploy menu for polish ---- */
footer, [data-testid="stStatusWidget"] { display: none !important; }

/* ---- Top padding: less empty space above the title ---- */
[data-testid="stMainBlockContainer"] { padding-top: 2rem !important; }
</style>
"""


def inject_theme():
    """Call once at the top of main() to apply the CSS."""
    st.markdown(_CSS, unsafe_allow_html=True)
