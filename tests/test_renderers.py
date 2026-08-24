import json

import pytest

from yt_transcript.models import (
    CaptionTrack,
    Chapter,
    TranscriptDocument,
    TranscriptSegment,
    VideoMetadata,
)
from yt_transcript.renderers import render_transcript, summary_source_text


@pytest.fixture
def document() -> TranscriptDocument:
    return TranscriptDocument(
        metadata=VideoMetadata(
            video_id="dQw4w9WgXcQ",
            title="Test video",
            duration=90,
            description="Description",
            language="en",
            chapters=(Chapter("Opening", 0.0, 30.0), Chapter("Details", 30.0, 90.0)),
        ),
        track=CaptionTrack((), "en", "manual"),
        segments=(
            TranscriptSegment(1.25, 2.5, "First sentence."),
            TranscriptSegment(30.5, 32.75, "Second sentence."),
        ),
    )


@pytest.mark.parametrize("output_format", ["md", "txt", "json", "srt", "vtt"])
def test_all_transcript_formats_use_canonical_document(
    document: TranscriptDocument,
    output_format: str,
) -> None:
    artifact = render_transcript(document, output_format)  # type: ignore[arg-type]

    assert artifact.kind == "transcript"
    assert artifact.format == output_format
    assert artifact.filename == f"dQw4w9WgXcQ_transcript.{output_format}"
    assert "First sentence." in artifact.content
    assert "Second sentence." in artifact.content


def test_markdown_has_source_chapters_and_clickable_timestamps(
    document: TranscriptDocument,
) -> None:
    content = render_transcript(document, "md").content

    assert "## Chapters" in content
    assert "[00:00:30 — Details](https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s)" in content
    assert "[00:00:01](https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=1s)" in content


def test_json_preserves_metadata_track_chapters_and_segments(
    document: TranscriptDocument,
) -> None:
    payload = json.loads(render_transcript(document, "json").content)

    assert payload["metadata"]["video_id"] == "dQw4w9WgXcQ"
    assert payload["metadata"]["description"] == "Description"
    assert payload["track"] == {
        "language": "en",
        "kind": "manual",
        "label": "Manual captions (en)",
    }
    assert payload["chapters"][1] == {"title": "Details", "start": 30.0, "end": 90.0}
    assert payload["segments"][0] == {
        "start": 1.25,
        "end": 2.5,
        "text": "First sentence.",
    }


def test_subtitle_formats_use_segment_start_and_end_times(
    document: TranscriptDocument,
) -> None:
    srt = render_transcript(document, "srt").content
    vtt = render_transcript(document, "vtt").content

    assert "1\n00:00:01,250 --> 00:00:02,500\nFirst sentence." in srt
    assert vtt.startswith("WEBVTT\n\n")
    assert "00:00:30.500 --> 00:00:32.750\nSecond sentence." in vtt


def test_summary_source_contains_only_caption_text(document: TranscriptDocument) -> None:
    assert summary_source_text(document) == "First sentence.\nSecond sentence."
