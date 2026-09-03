from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, replace
from typing import Any, Literal

from .errors import GeminiApiError, InvalidVideoError
from .gemini import DEFAULT_GEMINI_MODEL, call_gemini_api, create_summary_markdown
from .models import OutputArtifact, OutputFormat, SummaryLimit, TranscriptDocument
from .renderers import (
    SUPPORTED_OUTPUT_FORMATS,
    render_transcript,
    summary_source_text,
    truncated_summary_source,
)
from .summary_languages import normalize_summary_language
from .youtube import download_and_parse_captions, extract_video_id, fetch_video_and_captions

MAX_SUMMARY_LENGTH = 50_000
ProgressCallback = Callable[[int, str], None]
LongSummaryMode = Literal["ask", "truncate", "full", "skip"]
ALLOWED_LONG_SUMMARY_MODES = {"ask", "truncate", "full", "skip"}
ALLOWED_COOKIE_BROWSERS = {"chrome", "chromium", "edge", "firefox", "safari", "brave"}


@dataclass(frozen=True, slots=True)
class ExtractionOptions:
    url: str
    transcript_format: OutputFormat = "md"
    generate_summary: bool = False
    summary_language: str = "auto"
    long_summary_mode: LongSummaryMode = "ask"
    cookie_browser: str | None = None
    api_key: str = ""
    gemini_model: str = DEFAULT_GEMINI_MODEL

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ExtractionOptions:
        url = str(value.get("url") or "").strip()
        transcript_format = str(value.get("transcript_format") or "md")
        try:
            summary_language = normalize_summary_language(value.get("summary_language", "auto"))
        except ValueError as exc:
            raise InvalidVideoError(str(exc)) from exc
        long_summary_mode = str(value.get("long_summary_mode") or "ask")
        cookie_browser = str(value.get("cookie_browser") or "").lower() or None
        gemini_model = str(value.get("gemini_model") or DEFAULT_GEMINI_MODEL).strip()

        if transcript_format not in SUPPORTED_OUTPUT_FORMATS:
            raise InvalidVideoError("The transcript output format is invalid.")
        if long_summary_mode not in ALLOWED_LONG_SUMMARY_MODES:
            raise InvalidVideoError("The long transcript summary choice is invalid.")
        if cookie_browser and cookie_browser not in ALLOWED_COOKIE_BROWSERS:
            raise InvalidVideoError("The selected browser is not supported for cookies.")
        if not gemini_model or len(gemini_model) > 100:
            raise InvalidVideoError("The Gemini model ID is invalid.")

        return cls(
            url=url,
            transcript_format=transcript_format,  # type: ignore[arg-type]
            generate_summary=bool(value.get("generate_summary", False)),
            summary_language=summary_language,
            long_summary_mode=long_summary_mode,  # type: ignore[arg-type]
            cookie_browser=cookie_browser,
            api_key=str(value.get("api_key") or "").strip(),
            gemini_model=gemini_model,
        )


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    document: TranscriptDocument
    transcript: OutputArtifact
    summary: OutputArtifact | None
    summary_limit: SummaryLimit | None
    warning: str | None
    character_count: int
    word_count: int

    def to_dict(self) -> dict[str, Any]:
        metadata = self.document.metadata
        return {
            "video_id": metadata.video_id,
            "video_title": metadata.title,
            "video_url": metadata.url,
            "duration": metadata.duration,
            "language": metadata.language,
            "caption_label": self.document.track.label,
            "transcript": asdict(self.transcript),
            "summary": asdict(self.summary) if self.summary else None,
            "summary_limit": asdict(self.summary_limit) if self.summary_limit else None,
            "warning": self.warning,
            "character_count": self.character_count,
            "word_count": self.word_count,
        }


def extract_transcript(
    options: ExtractionOptions,
    progress: ProgressCallback | None = None,
) -> ExtractionResult:
    """Run extraction and summarize immediately unless a long input needs a decision."""
    result = extract_transcript_only(options, progress=progress)
    emit = progress or (lambda _percent, _message: None)

    if not options.generate_summary:
        return result

    api_key = options.api_key.strip()
    if not api_key:
        emit(100, "Complete")
        return replace(
            result,
            warning="No Gemini API key was provided, so only the transcript was created.",
        )

    is_long = result.character_count > MAX_SUMMARY_LENGTH
    if is_long and options.long_summary_mode == "ask":
        emit(100, "Transcript ready — choose how to summarize the long captions")
        return mark_summary_pending(result)
    if is_long and options.long_summary_mode == "skip":
        return summarize_transcript(
            result,
            mode="skip",
            api_key="",
            language=options.summary_language,
            model=options.gemini_model,
            progress=progress,
        )

    summary_mode = "full" if options.long_summary_mode == "ask" else options.long_summary_mode
    return summarize_transcript(
        result,
        mode=summary_mode,
        api_key=api_key,
        language=options.summary_language,
        model=options.gemini_model,
        progress=progress,
    )


def extract_transcript_only(
    options: ExtractionOptions,
    progress: ProgressCallback | None = None,
) -> ExtractionResult:
    """Extract and render captions without resolving or using any Gemini credential."""
    emit = progress or (lambda _percent, _message: None)
    emit(5, "Validating the URL…")
    if not extract_video_id(options.url):
        raise InvalidVideoError("Could not identify a valid YouTube video.")

    emit(18, "Checking video details and original-language captions…")
    metadata, track = fetch_video_and_captions(
        options.url,
        cookie_browser=options.cookie_browser,
    )

    emit(42, f"Downloading {track.label}…")
    segments = download_and_parse_captions(track)
    document = TranscriptDocument(metadata=metadata, track=track, segments=segments)

    emit(66, f"Formatting captions as {options.transcript_format.upper()}…")
    transcript_artifact = render_transcript(document, options.transcript_format)
    source = summary_source_text(document)
    result = ExtractionResult(
        document=document,
        transcript=transcript_artifact,
        summary=None,
        summary_limit=None,
        warning=None,
        character_count=len(source),
        word_count=len(source.split()),
    )

    emit(100, "Transcript ready")
    return result


def mark_summary_pending(result: ExtractionResult) -> ExtractionResult:
    """Mark a long extraction as awaiting the user's summary choice."""
    return replace(
        result,
        summary_limit=SummaryLimit(
            source_characters=result.character_count,
            limit_characters=MAX_SUMMARY_LENGTH,
            requires_confirmation=True,
        ),
    )


def summarize_transcript(
    result: ExtractionResult,
    *,
    mode: Literal["truncate", "full", "skip"],
    api_key: str,
    language: str,
    model: str,
    progress: ProgressCallback | None = None,
) -> ExtractionResult:
    """Summarize an existing extraction using only the explicitly supplied credential."""
    if mode not in {"truncate", "full", "skip"}:
        raise InvalidVideoError("The long transcript summary choice is invalid.")
    try:
        language = normalize_summary_language(language)
    except ValueError as exc:
        raise InvalidVideoError(str(exc)) from exc
    model = model.strip()
    if not model or len(model) > 100:
        raise InvalidVideoError("The Gemini model ID is invalid.")

    if mode == "skip":
        emit = progress or (lambda _percent, _message: None)
        emit(100, "Complete")
        source_length = result.character_count
        warning = "Summary skipped by the user."
        summary_limit = None
        if source_length > MAX_SUMMARY_LENGTH:
            warning = (
                "Summary skipped by the user for captions exceeding the default limit "
                f"[{source_length:,}/{MAX_SUMMARY_LENGTH:,} characters]."
            )
            summary_limit = SummaryLimit(source_length, MAX_SUMMARY_LENGTH, False)
        return replace(result, summary=None, summary_limit=summary_limit, warning=warning)

    key = api_key.strip()
    if not key:
        raise GeminiApiError("No Gemini API key is configured.")
    return _summarize_result(
        result,
        mode=mode,
        api_key=key,
        language=language,
        model=model,
        emit=progress or (lambda _percent, _message: None),
    )


def resolve_long_summary(
    result: ExtractionResult,
    *,
    mode: Literal["truncate", "full", "skip"],
    api_key: str,
    language: str,
    model: str,
    progress: ProgressCallback | None = None,
) -> ExtractionResult:
    """Apply the user's decision to a long transcript without downloading it again."""
    if not result.summary_limit or not result.summary_limit.requires_confirmation:
        raise InvalidVideoError("There is no long transcript awaiting a summary choice.")
    if mode not in {"truncate", "full", "skip"}:
        raise InvalidVideoError("The long transcript summary choice is invalid.")

    return summarize_transcript(
        result,
        mode=mode,
        api_key=api_key,
        language=language,
        model=model,
        progress=progress,
    )


def _summarize_result(
    result: ExtractionResult,
    *,
    mode: LongSummaryMode,
    api_key: str,
    language: str,
    model: str,
    emit: ProgressCallback,
) -> ExtractionResult:
    source = summary_source_text(result.document)
    used_source = source
    source_note: str | None = None
    warning: str | None = None
    if len(source) > MAX_SUMMARY_LENGTH and mode == "truncate":
        used_source = truncated_summary_source(result.document, MAX_SUMMARY_LENGTH)
        source_note = (
            f"Summary source: {len(used_source):,} of {len(source):,} caption characters "
            f"(default limit: {MAX_SUMMARY_LENGTH:,})."
        )
        warning = source_note
    elif len(source) > MAX_SUMMARY_LENGTH and mode == "full":
        source_note = (
            f"Summary source: all {len(source):,} caption characters "
            f"(default limit: {MAX_SUMMARY_LENGTH:,})."
        )
        warning = source_note

    emit(78, "Generating a summary with Gemini…")
    try:
        summary_text = call_gemini_api(
            used_source,
            api_key,
            language=language,
            model=model,
        )
        summary_content = create_summary_markdown(
            result.document.metadata,
            summary_text,
            source_note=source_note,
        )
        summary = OutputArtifact(
            kind="summary",
            format="md",
            filename=f"{result.document.metadata.video_id}_summarized.md",
            content=summary_content,
        )
    except GeminiApiError as exc:
        summary = None
        warning = f"The transcript was created, but summarization failed: {exc.message}"

    emit(100, "Complete")
    summary_limit = (
        SummaryLimit(
            len(source),
            MAX_SUMMARY_LENGTH,
            requires_confirmation=summary is None,
        )
        if len(source) > MAX_SUMMARY_LENGTH
        else None
    )
    return replace(
        result,
        summary=summary,
        summary_limit=summary_limit,
        warning=warning,
    )
