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
from .gemini import DEFAULT_GEMINI_MODEL
from .gemini import list_gemini_models as fetch_gemini_models
from .service import (
    ExtractionOptions,
    ExtractionResult,
    error_payload,
    extract_transcript,
    resolve_long_summary,
)
from .summary_languages import summary_language_options


class DesktopApi:
    """Small, explicit bridge exposed to the bundled JavaScript UI."""

    def __init__(self) -> None:
        self._window: Any = None
        self._latest: ExtractionResult | None = None
        self._pending_save_directory: Path | None = None
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
            "summary_languages": summary_language_options(),
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
            self._pending_save_directory = None
            return {"ok": True, "result": result.to_dict()}
        except Exception as exc:  # The bridge must always return serializable data.
            return {"ok": False, "error": error_payload(exc)}
        finally:
            self._work_lock.release()

    def summarize_latest(
        self,
        mode: str,
        api_key_override: str = "",
        summary_language: str = "auto",
        gemini_model: str = DEFAULT_GEMINI_MODEL,
    ) -> dict[str, Any]:
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
            if not self._latest:
                return {"ok": False, "error": "There is no transcript to summarize."}
            result = resolve_long_summary(
                self._latest,
                mode=mode,  # type: ignore[arg-type]
                api_key=str(api_key_override or ""),
                language=str(summary_language or "auto"),
                model=str(gemini_model or DEFAULT_GEMINI_MODEL),
                progress=self._emit_progress,
            )
            self._latest = result
            return {"ok": True, "result": result.to_dict()}
        except Exception as exc:
            return {"ok": False, "error": error_payload(exc)}
        finally:
            self._work_lock.release()

    def save_result(self, kind: str) -> dict[str, Any]:
        if not self._latest:
            return {"ok": False, "error": "There is no result to save."}
        if kind not in {"transcript", "summary"}:
            return {"ok": False, "error": "The requested result type is invalid."}

        artifact = self._latest.transcript if kind == "transcript" else self._latest.summary
        if not artifact:
            return {"ok": False, "error": "There is no content to save."}

        try:
            import webview

            selected = self._window.create_file_dialog(
                webview.FileDialog.SAVE,
                save_filename=artifact.filename,
                file_types=(_file_type_label(artifact.format),),
            )
            if not selected:
                return {"ok": True, "cancelled": True}
            path = Path(selected[0] if not isinstance(selected, str) else selected)
            path.write_text(artifact.content, encoding="utf-8")
            return {"ok": True, "cancelled": False, "path": str(path)}
        except Exception as exc:
            return {"ok": False, "error": f"Could not save the file: {exc}"}

    def save_all_results(self, overwrite: bool = False) -> dict[str, Any]:
        if not self._latest:
            return {"ok": False, "error": "There are no results to save."}
        if overwrite and self._pending_save_directory is None:
            return {
                "ok": False,
                "error": "There is no pending overwrite confirmation.",
            }

        artifacts = [self._latest.transcript]
        if self._latest.summary:
            artifacts.append(self._latest.summary)
        try:
            import webview

            directory = self._pending_save_directory if overwrite else None
            if directory is None:
                selected = self._window.create_file_dialog(webview.FileDialog.FOLDER)
                if not selected:
                    self._pending_save_directory = None
                    return {"ok": True, "cancelled": True}
                directory = Path(selected[0] if not isinstance(selected, str) else selected)

            paths = [directory / artifact.filename for artifact in artifacts]
            conflicts = [str(path) for path in paths if path.exists()]
            if conflicts and not overwrite:
                self._pending_save_directory = directory
                return {
                    "ok": False,
                    "needs_overwrite_confirmation": True,
                    "conflicts": conflicts,
                }

            directory.mkdir(parents=True, exist_ok=True)
            for artifact, path in zip(artifacts, paths, strict=True):
                path.write_text(artifact.content, encoding="utf-8")
            self._pending_save_directory = None
            return {
                "ok": True,
                "cancelled": False,
                "paths": [str(path) for path in paths],
            }
        except Exception as exc:
            self._pending_save_directory = None
            return {"ok": False, "error": f"Could not save the files: {exc}"}

    def open_video(self) -> dict[str, Any]:
        if not self._latest:
            return {"ok": False, "error": "There is no video to open."}
        return {"ok": bool(webbrowser.open(self._latest.document.metadata.url))}

    def open_video_at(self, seconds: float) -> dict[str, Any]:
        if not self._latest:
            return {"ok": False, "error": "There is no video to open."}
        try:
            start = max(0, int(float(seconds)))
        except (TypeError, ValueError):
            return {"ok": False, "error": "The timestamp is invalid."}
        url = f"{self._latest.document.metadata.url}&t={start}s"
        return {"ok": bool(webbrowser.open(url))}

    def _emit_progress(self, percent: int, message: str) -> None:
        if not self._window:
            return
        payload = json.dumps(
            {"percent": percent, "message": message},
            ensure_ascii=False,
        )
        with suppress(Exception):
            self._window.run_js(f"window.App && window.App.onProgress({payload});")


def _file_type_label(output_format: str) -> str:
    labels = {
        "md": "Markdown (*.md)",
        "txt": "Text (*.txt)",
        "json": "JSON (*.json)",
        "srt": "SubRip (*.srt)",
        "vtt": "WebVTT (*.vtt)",
    }
    return labels.get(output_format, "All files (*.*)")


def load_ui_html() -> str:
    """Inline separated UI assets so pywebview never starts a local HTTP server."""
    root = files("yt_transcript.ui")
    template = root.joinpath("index.html").read_text(encoding="utf-8")
    styles = root.joinpath("styles.css").read_text(encoding="utf-8")
    styles += "\n" + root.joinpath("enhancements.css").read_text(encoding="utf-8")
    styles += "\n" + root.joinpath("theme-control.css").read_text(encoding="utf-8")
    script = root.joinpath("app.js").read_text(encoding="utf-8")
    script += "\n" + root.joinpath("enhancements.js").read_text(encoding="utf-8")
    script += "\n" + root.joinpath("theme-control.js").read_text(encoding="utf-8")
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
