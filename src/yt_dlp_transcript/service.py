from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

from .errors import AppError, GeminiApiError, InvalidVideoError
from .gemini import DEFAULT_GEMINI_MODEL, call_gemini_api, create_summary_markdown
from .youtube import (
    download_and_parse_captions,
    extract_video_id,
    fetch_video_and_captions,
    transcript_to_markdown,
)

MAX_SUMMARY_LENGTH = 50_000
ProgressCallback = Callable[[int, str], None]
ALLOWED_LANGUAGES = {"auto", "en", "ja"}
ALLOWED_COOKIE_BROWSERS = {"chrome", "chromium", "edge", "firefox", "safari", "brave"}


@dataclass(frozen=True)
class ExtractionOptions:
    url: str
    include_timestamps: bool = True
    generate_summary: bool = False
    summary_language: str = "auto"
    caption_language: str = "auto"
    cookie_browser: str | None = None
    api_key: str = ""
    gemini_model: str = DEFAULT_GEMINI_MODEL

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExtractionOptions:
        url = str(value.get("url") or "").strip()
        summary_language = str(value.get("summary_language") or "auto")
        caption_language = str(value.get("caption_language") or "auto")
        cookie_browser = str(value.get("cookie_browser") or "").lower() or None
        gemini_model = str(value.get("gemini_model") or DEFAULT_GEMINI_MODEL).strip()

        if summary_language not in ALLOWED_LANGUAGES:
            raise InvalidVideoError("The summary language is invalid.")
        if caption_language not in ALLOWED_LANGUAGES:
            raise InvalidVideoError("The caption language is invalid.")
        if cookie_browser and cookie_browser not in ALLOWED_COOKIE_BROWSERS:
            raise InvalidVideoError("The selected browser is not supported for cookies.")
        if not gemini_model or len(gemini_model) > 100:
            raise InvalidVideoError("The Gemini model ID is invalid.")

        return cls(
            url=url,
            include_timestamps=bool(value.get("include_timestamps", True)),
            generate_summary=bool(value.get("generate_summary", False)),
            summary_language=summary_language,
            caption_language=caption_language,
            cookie_browser=cookie_browser,
            api_key=str(value.get("api_key") or "").strip(),
            gemini_model=gemini_model,
        )


@dataclass(frozen=True)
class ExtractionResult:
    video_id: str
    video_title: str
    video_url: str
    duration: int
    language: str
    caption_label: str
    transcript: str
    summary: str | None
    warning: str | None
    character_count: int
    word_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_transcript(
    options: ExtractionOptions,
    progress: ProgressCallback | None = None,
) -> ExtractionResult:
    """Run the complete extraction flow shared by desktop and CLI."""
    emit = progress or (lambda _percent, _message: None)
    emit(5, "Validating the URL…")
    if not extract_video_id(options.url):
        raise InvalidVideoError("Could not identify a valid YouTube video.")

    emit(18, "Checking video details and available captions…")
    metadata, track = fetch_video_and_captions(
        options.url,
        caption_language=options.caption_language,
        cookie_browser=options.cookie_browser,
    )

    emit(42, f"Downloading {track.label}…")
    entries = download_and_parse_captions(track)

    emit(66, "Formatting captions as readable Markdown…")
    transcript_markdown = transcript_to_markdown(
        entries,
        metadata,
        track,
        include_timestamps=options.include_timestamps,
    )

    summary_markdown: str | None = None
    warning: str | None = None
    if options.generate_summary:
        api_key = options.api_key or os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            warning = "No Gemini API key was provided, so only the transcript was created."
        else:
            emit(78, "Generating a summary with Gemini…")
            text_for_summary = transcript_markdown[:MAX_SUMMARY_LENGTH]
            if len(transcript_markdown) > MAX_SUMMARY_LENGTH:
                text_for_summary += "\n\n[Transcript truncated for summarization]"
            try:
                summary = call_gemini_api(
                    text_for_summary,
                    api_key,
                    language=options.summary_language,
                    model=options.gemini_model,
                )
                summary_markdown = create_summary_markdown(metadata, summary)
            except GeminiApiError as exc:
                warning = f"The transcript was created, but summarization failed: {exc.message}"

    emit(100, "Complete")
    words = transcript_markdown.split()
    return ExtractionResult(
        video_id=metadata.video_id,
        video_title=metadata.title,
        video_url=metadata.url,
        duration=metadata.duration,
        language=metadata.language,
        caption_label=track.label,
        transcript=transcript_markdown,
        summary=summary_markdown,
        warning=warning,
        character_count=len(transcript_markdown),
        word_count=len(words),
    )


def error_payload(error: Exception) -> dict[str, str]:
    if isinstance(error, AppError):
        return {"code": error.code, "message": error.message, "hint": error.hint}
    return {
        "code": "unexpected_error",
        "message": "An unexpected error occurred.",
        "hint": str(error),
    }
