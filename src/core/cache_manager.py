"""
Cache manager — backward-compatible wrapper.

The preload_all_pops function is no longer needed since we use on-demand loading.
This file exists for backward compatibility only.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def preload_all_pops(data_cleaner, load_data_func):
    """No-op. Background preloading has been replaced by on-demand loading."""
    logger.info("preload_all_pops called but is now a no-op (on-demand loading)")
