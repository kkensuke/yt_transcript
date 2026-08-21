from __future__ import annotations

import json
import os
import threading
import webbrowser
from contextlib import suppress
from importlib.resources import files
from pathlib import Path
from typing import Any

from . import __version__
from .gemini import DEFAULT_GEMINI_MODEL, list_gemini_models as fetch_gemini_models
from .service import ExtractionOptions, ExtractionResult, error_payload, extract_transcript


class DesktopApi:
    """Small, explicit bridge exposed to the bundled JavaScript UI."""

    def __init__(self) -> None:
        self._window: Any = None
        self._latest: ExtractionResult | None = None
        self._work_lock = threading.Lock()

    def bind_window(self, window: Any) -> None:
        self._window = window

    def get_app_info(self) -> dict[str, Any]:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        model_from_environment = os.getenv("GEMINI_MODEL", "").strip()
        return {
            "version": __version__,
            "api_key_configured": bool(api_key),
            "api_key_source": "environment" if api_key else "not_configured",
            "api_key_environment_variable": "GEMINI_API_KEY",
            "gemini_model": model_from_environment or DEFAULT_GEMINI_MODEL,
            "gemini_model_source": "environment" if model_from_environment else "default",
            "gemini_model_environment_variable": "GEMINI_MODEL",
        }

    def list_gemini_models(self, api_key_override: str = "") -> dict[str, Any]:
        api_key = str(api_key_override or "").strip() or os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            return {
                "ok": False,
                "error": "Enter a Gemini API key or set GEMINI_API_KEY to load available models.",
            }
        try:
            models = fetch_gemini_models(api_key)
        except Exception as exc:
            payload = error_payload(exc)
            return {"ok": False, "error": payload["message"], "hint": payload.get("hint", "")}
        return {"ok": True, "models": models}

    def extract(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._work_lock.acquire(blocking=False):
            return {
                "ok": False,
                "error": {
                    "code": "busy",
                    "message": "Another video is already being processed.",
                    "hint": "Wait for the current task to finish, then try again.",
                },
            }

        try:
            options = ExtractionOptions.from_mapping(payload)
            result = extract_transcript(options, progress=self._emit_progress)
            self._latest = result
            return {"ok": True, "result": result.to_dict()}
        except Exception as exc:  # The bridge must always return serializable data.
            return {"ok": False, "error": error_payload(exc)}
        finally:
            self._work_lock.release()

    def save_result(self, kind: str) -> dict[str, Any]:
        if not self._latest:
            return {"ok": False, "error": "There is no result to save."}
        if kind not in {"transcript", "summary"}:
            return {"ok": False, "error": "The requested result type is invalid."}

        content = self._latest.transcript if kind == "transcript" else self._latest.summary
        if not content:
            return {"ok": False, "error": "There is no content to save."}

        suffix = "transcript" if kind == "transcript" else "summarized"
        filename = f"{self._latest.video_id}_{suffix}.md"
        try:
            import webview

            selected = self._window.create_file_dialog(
                webview.FileDialog.SAVE,
                save_filename=filename,
                file_types=("Markdown (*.md)",),
            )
            if not selected:
                return {"ok": True, "cancelled": True}
            path = Path(selected[0] if not isinstance(selected, str) else selected)
            path.write_text(content, encoding="utf-8")
            return {"ok": True, "cancelled": False, "path": str(path)}
        except Exception as exc:
            return {"ok": False, "error": f"Could not save the file: {exc}"}

    def open_video(self) -> dict[str, Any]:
        if not self._latest:
            return {"ok": False, "error": "There is no video to open."}
        return {"ok": bool(webbrowser.open(self._latest.video_url))}

    def _emit_progress(self, percent: int, message: str) -> None:
        if not self._window:
            return
        payload = json.dumps(
            {"percent": percent, "message": message},
            ensure_ascii=False,
        )
        with suppress(Exception):
            self._window.run_js(f"window.App && window.App.onProgress({payload});")


def load_ui_html() -> str:
    """Inline separated UI assets so pywebview never starts a local HTTP server."""
    root = files("yt_transcript.ui")
    template = root.joinpath("index.html").read_text(encoding="utf-8")
    styles = root.joinpath("styles.css").read_text(encoding="utf-8")
    styles += "\n" + root.joinpath("enhancements.css").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    script += "\n" + root.joinpath("enhancements.js").read_text(encoding="utf-8")
    return template.replace("/*__APP_STYLES__*/", styles).replace("/*__APP_SCRIPT__*/", script)


def main() -> None:
    import webview

    api = DesktopApi()
    window = webview.create_window(
        "YouTube Transcript",
        html=load_ui_html(),
        js_api=api,
        width=1100,
        height=800,
        min_size=(760, 620),
        background_color="#f4f6f8",
        text_select=True,
    )
    api.bind_window(window)
    debug = os.getenv("YT_TRANSCRIPT_DEBUG", "").lower() in {"1", "true", "yes"}
    webview.start(debug=debug, http_server=False, private_mode=True)
