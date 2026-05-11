"""
This Streamlit version of the Lead Finder has been retired.
The replacement lives at https://lead-finder-next.vercel.app
"""
import streamlit as st

NEW_URL = "https://lead-finder-next.vercel.app"

st.set_page_config(
    page_title="Lead Finder — Moved",
    page_icon="🦛",
    layout="centered",
)

# Auto-redirect after 5s (works in most browsers via meta refresh).
st.markdown(
    f'<meta http-equiv="refresh" content="5; url={NEW_URL}">',
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div style="text-align:center; padding: 4rem 1rem;">
        <img src="https://fasthippomedia.com/wp-content/uploads/2024/12/SVG-File.png"
             alt="Fast Hippo Media" style="height:64px; margin-bottom:1rem;">
        <h1 style="color:#03045E; margin:0;">Lead Finder has moved</h1>
        <p style="font-size:1rem; color:#444; max-width:540px; margin:1rem auto;">
            The Streamlit version of this tool has been retired. All the same
            features — plus admin usage tracking and improved performance —
            live at the new URL.
        </p>
        <a href="{NEW_URL}"
           style="display:inline-block; background:#0C34CA; color:white;
                  padding:14px 32px; border-radius:10px; font-weight:600;
                  text-decoration:none; margin-top:1rem;">
            Open the new Lead Finder →
        </a>
        <p style="margin-top:2rem; color:#888; font-size:0.85rem;">
            Redirecting automatically in 5 seconds…<br>
            Update your bookmarks to: <code>{NEW_URL}</code>
        </p>
        <hr style="border:none; border-top:1px solid #eee; margin:2.5rem auto; max-width:300px;">
        <p style="color:#aaa; font-size:0.75rem;">
            <strong>Fast Hippo Media</strong> — Award Winning Digital Marketing Agency<br>
            <a href="https://fasthippomedia.com" style="color:#0C34CA; text-decoration:none;">fasthippomedia.com</a>
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Prevent anything below from rendering, even if a stale link tries to deep-link.
st.stop()
