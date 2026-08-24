import json
import urllib.error

import pytest

from yt_transcript.errors import NoTranscriptError, TranscriptDownloadError
from yt_transcript.models import CaptionTrack, TranscriptSegment, VideoMetadata
from yt_transcript.youtube import (
    _extract_chapters,
    _normalize_entries,
    _select_caption_track,
    download_and_parse_captions,
    extract_video_id,
    parse_json3_transcript,
    parse_srv1_transcript,
    parse_vtt_transcript,
    transcript_to_markdown,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=12", "dQw4w9WgXcQ"),
        ("youtu.be/dQw4w9WgXcQ?si=abc", "dQw4w9WgXcQ"),
        ("https://music.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com.evil.example/watch?v=dQw4w9WgXcQ", None),
        ("https://www.youtube.com/channel/UC-lHJZR3Gqxm24_Vd_AJ5Yw", None),
        ("not a url", None),
    ],
)
def test_extract_video_id(value: str, expected: str | None) -> None:
    assert extract_video_id(value) == expected


def test_select_caption_prefers_original_language_and_manual_track() -> None:
    info = {
        "subtitles": {"ja": [{"ext": "vtt", "url": "manual-ja"}]},
        "automatic_captions": {
            "ja-orig": [{"ext": "json3", "url": "auto-ja"}],
            "en": [{"ext": "json3", "url": "translated-en"}],
        },
    }

    selected = _select_caption_track(info, "ja")

    assert selected.language == "ja"
    assert selected.kind == "manual"
    assert selected.formats[0]["url"] == "manual-ja"


def test_select_caption_uses_original_auto_track_before_translation() -> None:
    info = {
        "automatic_captions": {
            "en": [{"ext": "json3", "url": "translated-en"}],
            "fr-orig": [{"ext": "json3", "url": "original-fr"}],
        }
    }

    selected = _select_caption_track(info, "fr-FR")

    assert selected.language == "fr-orig"
    assert selected.formats[0]["url"] == "original-fr"


def test_select_caption_raises_when_none_exist() -> None:
    with pytest.raises(NoTranscriptError):
        _select_caption_track({}, "en")


def test_caption_parsers_keep_segment_boundaries_and_end_times() -> None:
    json3 = json.dumps(
        {
            "events": [
                {
                    "tStartMs": 1500,
                    "dDurationMs": 900,
                    "segs": [{"utf8": "Hello "}, {"utf8": "world"}],
                }
            ]
        }
    )
    assert parse_json3_transcript(json3)[0] == TranscriptSegment(
        start=1.5,
        end=2.4,
        text="Hello world",
    )

    vtt = "WEBVTT\n\n00:00:02.500 --> 00:00:04.000\n<c>Hello &amp; welcome</c>\n"
    assert parse_vtt_transcript(vtt)[0] == TranscriptSegment(
        start=2.5,
        end=4.0,
        text="Hello & welcome",
    )

    srv1 = '<transcript><text start="3.5" dur="1.2">Hello XML</text></transcript>'
    assert parse_srv1_transcript(srv1)[0] == TranscriptSegment(
        start=3.5,
        end=4.7,
        text="Hello XML",
    )


def test_json3_parser_inserts_missing_spaces_between_english_words() -> None:
    content = json.dumps(
        {
            "events": [
                {
                    "tStartMs": 0,
                    "dDurationMs": 1000,
                    "segs": [
                        {"utf8": "Chat"},
                        {"utf8": "GPT"},
                        {"utf8": "を"},
                        {"utf8": "使う"},
                    ],
                }
            ]
        }
    )

    assert parse_json3_transcript(content)[0].text == "Chat GPTを使う"


def test_json3_parser_does_not_add_spaces_inside_numbers() -> None:
    content = json.dumps(
        {
            "events": [
                {
                    "tStartMs": 0,
                    "dDurationMs": 1000,
                    "segs": [{"utf8": "50"}, {"utf8": ","}, {"utf8": "000"}],
                }
            ]
        }
    )

    assert parse_json3_transcript(content)[0].text == "50,000"


def test_normalization_preserves_intentional_repeated_lines() -> None:
    repeated = [
        TranscriptSegment(0.0, 1.0, "Again."),
        TranscriptSegment(1.0, 2.0, "Again."),
    ]

    assert _normalize_entries(repeated) == tuple(repeated)


def test_normalization_preserves_caption_cues() -> None:
    normalized = _normalize_entries(
        [TranscriptSegment(0.0, 1.0, "[音楽] こ れ は テ ス ト です ♪")]
    )

    assert normalized[0].text == "[音楽] これはテストです ♪"


def test_chapter_extraction_uses_source_chapters_and_infers_missing_ends() -> None:
    chapters = _extract_chapters(
        {
            "chapters": [
                {"title": "Second", "start_time": 20},
                {"title": "First", "start_time": 0, "end_time": 20},
            ]
        },
        duration=45,
    )

    assert [(item.title, item.start, item.end) for item in chapters] == [
        ("First", 0.0, 20.0),
        ("Second", 20.0, 45.0),
    ]


def test_caption_download_explains_rate_limit(monkeypatch) -> None:
    def rate_limited(*_args, **_kwargs):
        raise urllib.error.HTTPError("https://example.test", 429, "rate limited", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", rate_limited)
    track = CaptionTrack(
        ({"ext": "vtt", "url": "https://example.test"},),
        "en",
        "manual",
    )
    with pytest.raises(TranscriptDownloadError) as captured:
        download_and_parse_captions(track)
    assert "HTTP 429" in captured.value.message
    assert "Wait and try again" in captured.value.hint


def test_transcript_markdown_always_has_clickable_timestamp() -> None:
    metadata = VideoMetadata("dQw4w9WgXcQ", "Test video", 61, "", "en")
    track = CaptionTrack((), "en", "manual")
    result = transcript_to_markdown(
        [TranscriptSegment(start=5.0, end=6.0, text="First sentence.")],
        metadata,
        track,
        include_timestamps=False,
    )
    assert "# Test video" in result
    assert "**Duration:** 00:01:01" in result
    assert "**Captions:** Manual captions (en)" in result
    assert (
        "**[00:00:05](https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=5s)** First sentence."
    ) in result
