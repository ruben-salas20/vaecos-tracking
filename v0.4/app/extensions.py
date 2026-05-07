"""Shared Flask extensions instantiated at module level.
Initialized inside create_app() via .init_app(app)."""
from __future__ import annotations
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# In-memory store is fine for single-process Waitress with 4 threads.
# If we ever scale to multi-process workers, switch to a Redis backend.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://",
    strategy="fixed-window",
    headers_enabled=False,
)
