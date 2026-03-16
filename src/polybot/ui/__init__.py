"""Bundled Vue.js dashboard for PolyBot.

The `dist/` directory contains the pre-built frontend assets
which are served by the FastAPI application at `/ui`.

To rebuild the frontend:
    cd frontend
    npm ci
    npm run build
    cp -r dist ../src/polybot/ui/
"""

from pathlib import Path

# Path to the built frontend assets
DIST_DIR = Path(__file__).parent / "dist"


def has_bundled_ui() -> bool:
    """Check if the bundled UI is available."""
    return (DIST_DIR / "index.html").exists()
