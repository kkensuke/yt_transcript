from yt_dlp_transcript import service
from yt_dlp_transcript.errors import GeminiApiError, InvalidVideoError
from yt_dlp_transcript.service import ExtractionOptions
from yt_dlp_transcript.youtube import CaptionTrack, VideoMetadata


def test_options_validate_bridge_payload() -> None:
    options = ExtractionOptions.from_mapping(
        {
            "url": " dQw4w9WgXcQ ",
            "summary_language": "ja",
            "caption_language": "auto",
            "cookie_browser": "Safari",
        }
    )
    assert options.url == "dQw4w9WgXcQ"
    assert options.cookie_browser == "safari"

    try:
        ExtractionOptions.from_mapping({"url": "x", "cookie_browser": "unknown"})
    except InvalidVideoError as error:
        assert error.code == "invalid_video"
    else:
        raise AssertionError("invalid cookie browser should be rejected")


def test_service_returns_transcript_when_summary_fails(monkeypatch) -> None:
    metadata = VideoMetadata("dQw4w9WgXcQ", "Test", 90, "", "en")
    track = CaptionTrack([{"ext": "vtt", "url": "unused"}], "en", "manual")
    monkeypatch.setattr(service, "extract_video_id", lambda _value: "dQw4w9WgXcQ")
    monkeypatch.setattr(
        service,
        "fetch_video_and_captions",
        lambda *_args, **_kwargs: (metadata, track),
    )
    monkeypatch.setattr(
        service,
        "download_and_parse_captions",
        lambda _track: [{"text": "Hello.", "start": 0.0, "duration": 1.0}],
    )

    def fail_summary(*_args, **_kwargs):
        raise GeminiApiError("quota exceeded")

    monkeypatch.setattr(service, "call_gemini_api", fail_summary)
    progress = []
    result = service.extract_transcript(
        ExtractionOptions(url="dQw4w9WgXcQ", generate_summary=True, api_key="secret"),
        progress=lambda percent, _message: progress.append(percent),
    )

    assert "Hello." in result.transcript
    assert result.summary is None
    assert "quota exceeded" in (result.warning or "")
    assert progress[-1] == 100
