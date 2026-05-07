from __future__ import annotations
import sys
from pathlib import Path

# Add v0.4 to path so 'app' and 'config' packages are importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import create_app
from config import load_settings


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    settings = load_settings(base_dir)
    app = create_app()
    if settings.env == "production":
        from waitress import serve
        print(f"VAECOS v0.4 — http://{settings.host}:{settings.port}")
        serve(app, host=settings.host, port=settings.port, threads=4)
    else:
        print(f"VAECOS v0.4 dev — http://{settings.host}:{settings.port}")
        app.run(host=settings.host, port=settings.port, debug=True, use_reloader=False)


if __name__ == "__main__":
    main()
