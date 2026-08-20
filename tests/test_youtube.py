import json
import urllib.error

import pytest

from yt_dlp_transcript.errors import NoTranscriptError, TranscriptDownloadError
from yt_dlp_transcript.youtube import (
    CaptionTrack,
    VideoMetadata,
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


def test_select_caption_prefers_requested_language() -> None:
    info = {
        "subtitles": {"en": [{"ext": "vtt", "url": "manual"}]},
        "automatic_captions": {"ja": [{"ext": "json3", "url": "auto"}]},
    }
    selected = _select_caption_track(info, "ja", "en")
    assert selected.language == "ja"
    assert selected.kind == "automatic"


def test_select_caption_raises_when_none_exist() -> None:
    with pytest.raises(NoTranscriptError):
        _select_caption_track({}, "auto", "en")


def test_caption_parsers() -> None:
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
    assert parse_json3_transcript(json3)[0] == {
        "text": "Hello world",
        "start": 1.5,
        "duration": 0.9,
    }

    vtt = "WEBVTT\n\n00:00:02.500 --> 00:00:04.000\n<c>Hello &amp; welcome</c>\n"
    assert parse_vtt_transcript(vtt)[0]["text"] == "Hello & welcome"
    assert parse_vtt_transcript(vtt)[0]["start"] == 2.5

    srv1 = '<transcript><text start="3.5" dur="1.2">Hello XML</text></transcript>'
    assert parse_srv1_transcript(srv1)[0]["duration"] == 1.2


def test_caption_download_explains_rate_limit(monkeypatch) -> None:
    def rate_limited(*_args, **_kwargs):
        raise urllib.error.HTTPError("https://example.test", 429, "rate limited", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", rate_limited)
    track = CaptionTrack([{"ext": "vtt", "url": "https://example.test"}], "en", "manual")
    with pytest.raises(TranscriptDownloadError) as captured:
        download_and_parse_captions(track)
    assert "HTTP 429" in captured.value.message
    assert "Wait and try again" in captured.value.hint


def test_transcript_markdown_includes_compact_metadata() -> None:
    metadata = VideoMetadata("dQw4w9WgXcQ", "Test video", 61, "", "en")
    track = CaptionTrack([], "en", "manual")
    result = transcript_to_markdown(
        [{"text": "First sentence.", "start": 5.0, "duration": 1.0}],
        metadata,
        track,
    )
    assert "# Test video" in result
    assert "**Duration:** 00:01:01" in result
    assert "**Captions:** Manual captions (en)" in result
    assert "**[00:00:05]** First sentence." in result
