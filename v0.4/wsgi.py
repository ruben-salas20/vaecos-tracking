"""WSGI entry point for production servers (Waitress, Gunicorn, uWSGI).

Usage:
    waitress-serve --listen=127.0.0.1:8765 --threads=4 wsgi:application
    gunicorn -b 127.0.0.1:8765 -w 1 --threads 4 wsgi:application
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import create_app

application = create_app()
# Some WSGI runners look for `app`, others for `application`. Expose both.
app = application
