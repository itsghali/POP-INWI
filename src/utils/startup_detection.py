"""
Module de détection du démarrage du serveur Streamlit
"""
import os
import time
import atexit
import streamlit as st

# File-based startup detection
STARTUP_MARKER_FILE = ".streamlit_startup_marker"


def cleanup_startup_marker():
    """Remove startup marker when server shuts down"""
    if os.path.exists(STARTUP_MARKER_FILE):
        os.remove(STARTUP_MARKER_FILE)


def is_server_startup():
    """Check if this is actual server startup (not browser refresh or new tab)"""
    # Cache the result in session state to avoid multiple calls changing the detection
    if 'startup_detection_cached' in st.session_state:
        return st.session_state.startup_detection_result
    
    marker_exists = os.path.exists(STARTUP_MARKER_FILE)
    
    if not marker_exists:
        # First time - create marker and register cleanup
        with open(STARTUP_MARKER_FILE, 'w') as f:
            f.write(str(time.time()))
        atexit.register(cleanup_startup_marker)
        result = True
    else:
        # For existing marker, only consider it server startup if marker is very old (>300 seconds = 5 minutes)
        # This ensures browser refreshes/new tabs don't trigger automatic preloading
        try:
            with open(STARTUP_MARKER_FILE, 'r') as f:
                marker_time = float(f.read().strip())
            # Only if marker is older than 5 minutes, consider this a true server restart
            if time.time() - marker_time > 300:
                with open(STARTUP_MARKER_FILE, 'w') as f:
                    f.write(str(time.time()))
                result = True
            else:
                result = False
        except (ValueError, FileNotFoundError):
            # Invalid marker file, recreate
            with open(STARTUP_MARKER_FILE, 'w') as f:
                f.write(str(time.time()))
            result = True
    
    # Cache the result so multiple calls don't change the detection
    st.session_state.startup_detection_cached = True
    st.session_state.startup_detection_result = result
    return result
