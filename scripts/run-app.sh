#!/bin/sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

if ! command -v uv >/dev/null 2>&1; then
    echo "error: uv is required. Install it from https://docs.astral.sh/uv/." >&2
    exit 1
fi

if [ ! -f "$PROJECT_ROOT/pyproject.toml" ] || [ ! -d "$PROJECT_ROOT/src/yt_transcript" ]; then
    echo "error: project root could not be verified: $PROJECT_ROOT" >&2
    exit 1
fi

cd "$PROJECT_ROOT"

# Install only third-party dependencies. The application itself is loaded
# directly from src/, so this launcher neither depends on uv's editable .pth
# file nor keeps a stale non-editable copy of HTML/CSS/JavaScript.
echo "Preparing the application environment..."
uv sync --no-install-project --extra web --inexact

if [ -n "${PYTHONPATH:-}" ]; then
    export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"
else
    export PYTHONPATH="$PROJECT_ROOT/src"
fi

if [ "${1:-}" = "--check" ]; then
    uv run --no-sync python -c '
import sys
from pathlib import Path

import yt_transcript
from yt_transcript.web import UI_ROOT, create_app

expected = (Path(sys.argv[1]) / "src" / "yt_transcript").resolve()
actual = Path(yt_transcript.__file__).resolve().parent
assert actual == expected, f"Expected source package {expected}, loaded {actual}"
app = create_app(mode="local")
assert {"/", "/api/info", "/api/extract", "/api/summarize"}.issubset(
    {route.path for route in app.routes}
)
assert "/static/app.js" in (UI_ROOT / "index.html").read_text(encoding="utf-8")
print("Source application check passed.")
' "$PROJECT_ROOT"
    exit 0
fi

exec uv run --no-sync python -m yt_transcript.web
