"""
Logging configuration for the POP-INWI application.

Call setup_logging() once at application startup (in app.py).
All modules should use:
    import logging
    logger = logging.getLogger(__name__)
"""
import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Configure the root logger with a consistent format."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root = logging.getLogger()
    # Avoid duplicate handlers on Streamlit reruns
    if not root.handlers:
        root.addHandler(handler)
    root.setLevel(level)

    # Quiet noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("streamlit").setLevel(logging.WARNING)
