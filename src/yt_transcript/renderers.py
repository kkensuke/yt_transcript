from __future__ import annotations

import json
from collections.abc import Iterable

from .models import OutputArtifact, OutputFormat, TranscriptDocument, TranscriptSegment
from .utils import format_timestamp

SUPPORTED_OUTPUT_FORMATS: tuple[OutputFormat, ...] = ("md", "txt", "json", "srt", "vtt")


def render_transcript(
    document: TranscriptDocument,
    output_format: OutputFormat = "md",
) -> OutputArtifact:
    """Render one canonical transcript document in the selected output format."""
    renderers = {
        "md": _render_markdown,
        "txt": _render_text,
        "json": _render_json,
        "srt": _render_srt,
        "vtt": _render_vtt,
    }
    try:
        content = renderers[output_format](document)
    except KeyError as exc:
        raise ValueError(f"Unsupported transcript format: {output_format}") from exc
    return OutputArtifact(
        kind="transcript",
        format=output_format,
        filename=f"{document.metadata.video_id}_transcript.{output_format}",
        content=content,
    )


def summary_source_text(document: TranscriptDocument) -> str:
    """Return stable, format-independent caption text for summarization."""
    return "\n".join(segment.text for segment in document.segments).strip()


def truncated_summary_source(document: TranscriptDocument, limit: int) -> str:
    """Return a prefix no longer than limit, preferring complete segment boundaries."""
    if limit <= 0:
        return ""
    parts: list[str] = []
    used = 0
    for segment in document.segments:
        separator = 1 if parts else 0
        required = separator + len(segment.text)
        if used + required > limit:
            break
        parts.append(segment.text)
        used += required
    if parts:
        return "\n".join(parts)
    source = summary_source_text(document)
    return source[:limit]


def timestamp_url(document: TranscriptDocument, seconds: float) -> str:
    return f"{document.metadata.url}&t={max(0, int(seconds))}s"


def _render_markdown(document: TranscriptDocument) -> str:
    metadata = document.metadata
    lines = [
        f"# {_escape_markdown(metadata.title)}",
        "",
        f"**Video ID:** {metadata.video_id}  ",
        f"**YouTube URL:** {metadata.url}  ",
        f"**Duration:** {format_timestamp(metadata.duration)}  ",
        f"**Captions:** {document.track.label}",
        "",
    ]
    if metadata.chapters:
        lines.extend(("## Chapters", ""))
        for chapter in metadata.chapters:
            label = f"{format_timestamp(chapter.start)} — {_escape_markdown(chapter.title)}"
            lines.append(f"- [{label}]({timestamp_url(document, chapter.start)})")
        lines.append("")
    lines.extend(("---", ""))
    for start, text in _paragraphs(document.segments):
        link = f"[{format_timestamp(start)}]({timestamp_url(document, start)})"
        lines.extend((f"**{link}** {text}", ""))
    return "\n".join(lines).rstrip() + "\n"


def _render_text(document: TranscriptDocument) -> str:
    metadata = document.metadata
    lines = [
        metadata.title,
        f"Video ID: {metadata.video_id}",
        f"YouTube URL: {metadata.url}",
        f"Duration: {format_timestamp(metadata.duration)}",
        f"Captions: {document.track.label}",
        "",
    ]
    if metadata.chapters:
        lines.append("Chapters")
        for chapter in metadata.chapters:
            lines.append(f"[{format_timestamp(chapter.start)}] {chapter.title}")
        lines.append("")
    for start, text in _paragraphs(document.segments):
        lines.extend((f"[{format_timestamp(start)}] {text}", ""))
    return "\n".join(lines).rstrip() + "\n"


def _render_json(document: TranscriptDocument) -> str:
    metadata = document.metadata
    payload = {
        "metadata": {
            "video_id": metadata.video_id,
            "title": metadata.title,
            "url": metadata.url,
            "duration": metadata.duration,
            "description": metadata.description,
            "language": metadata.language,
        },
        "track": {
            "language": document.track.language,
            "kind": document.track.kind,
            "label": document.track.label,
        },
        "chapters": [
            {"title": chapter.title, "start": chapter.start, "end": chapter.end}
            for chapter in metadata.chapters
        ],
        "segments": [
            {"start": segment.start, "end": segment.end, "text": segment.text}
            for segment in document.segments
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _render_srt(document: TranscriptDocument) -> str:
    blocks = []
    for index, segment in enumerate(document.segments, start=1):
        blocks.append(
            f"{index}\n{_subtitle_timestamp(segment.start, ',')} --> "
            f"{_subtitle_timestamp(segment.end, ',')}\n{segment.text}"
        )
    return "\n\n".join(blocks).rstrip() + "\n"


def _render_vtt(document: TranscriptDocument) -> str:
    blocks = ["WEBVTT"]
    for segment in document.segments:
        blocks.append(
            f"{_subtitle_timestamp(segment.start, '.')} --> "
            f"{_subtitle_timestamp(segment.end, '.')}\n{segment.text}"
        )
    return "\n\n".join(blocks).rstrip() + "\n"


def _paragraphs(segments: Iterable[TranscriptSegment]) -> list[tuple[float, str]]:
    paragraphs: list[tuple[float, str]] = []
    parts: list[str] = []
    start = 0.0
    length = 0

    def flush() -> None:
        nonlocal parts, start, length
        if not parts:
            return
        text = " ".join(parts).strip()
        if text:
            paragraphs.append((start, text))
        parts = []
        start = 0.0
        length = 0

    for segment in segments:
        if not parts:
            start = segment.start
        parts.append(segment.text)
        length += len(segment.text)
        if segment.text.endswith((".", "!", "?", "。", "！", "？")) or length >= 480:
            flush()
    flush()
    return paragraphs


def _subtitle_timestamp(seconds: float, decimal_separator: str) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{decimal_separator}{millis:03d}"


def _escape_markdown(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
