"""
Airplane background for the Travel app
"""
import streamlit as st

def apply_airplane_background():
    """Inject CSS to set the airplane background on the right side of the Streamlit app"""
    css = get_airplane_background()
    if css: 
        st.markdown(
            f"""
            <style>
            .airplane-bg {{
                position: fixed;
                top: 0;
                right: 0;
                width: 40vw;
                height: 100vh;
                {css}
                background-size: cover;
                background-repeat: no-repeat;
                z-index: -1;
            }}
            </style>
            <div class="airplane-bg"></div>
            """,
            unsafe_allow_html=True
        )
from pathlib import Path

def get_airplane_background() -> str:
    """
    Return a *data URI* (NOT a full CSS declaration).
    Either read the raw base64, or the full data URI.
    """
    p = Path(__file__).with_name("airplane_image_base64.txt")
    s = p.read_text(encoding="utf-8").strip()

    # If the file already contains a data URI, return it as-is
    if s.startswith("data:image"):
        return s

    # Otherwise assume it's raw base64 for a PNG
    return f"data:image/png;base64,{s}"