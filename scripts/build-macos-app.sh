#!/bin/sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
BUILD_CONFIG="$PROJECT_ROOT/packaging/macos"
PYTHON_VERSION=$(tr -d '[:space:]' < "$PROJECT_ROOT/.python-version")
APP_PATH="$PROJECT_ROOT/dist/YouTubeTranscript.app"
LEGACY_APP_PATH="$PROJECT_ROOT/dist/YouTube Transcript.app"

if [ "$(uname -s)" != "Darwin" ]; then
    echo "error: macOS .app can only be built on macOS." >&2
    exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "error: uv is required. Install it from https://docs.astral.sh/uv/." >&2
    exit 1
fi

if [ ! -f "$PROJECT_ROOT/pyproject.toml" ] || [ ! -f "$PROJECT_ROOT/YouTubeTranscript.py" ]; then
    echo "error: project root could not be verified: $PROJECT_ROOT" >&2
    exit 1
fi

# Only generated output is removed. Source files and the development .venv are untouched.
rm -rf "$PROJECT_ROOT/build" "$APP_PATH" "$LEGACY_APP_PATH"

cd "$BUILD_CONFIG"

# py2app 0.28.10 rejects both editable projects and distributions containing
# install_requires. Build in an isolated, non-project uv environment so the
# development .venv is never converted between editable and wheel installs.
uv run \
    --no-project \
    --python "$PYTHON_VERSION" \
    --with "$PROJECT_ROOT[desktop]" \
    --with "py2app==0.28.10" \
    --with "setuptools>=77,<82" \
    python setup.py py2app

if [ ! -d "$APP_PATH" ]; then
    echo "error: py2app finished without creating $APP_PATH" >&2
    exit 1
fi

echo "Created $APP_PATH"
