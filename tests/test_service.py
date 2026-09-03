import pytest

from yttext import service
from yttext.errors import GeminiApiError, InvalidVideoError
from yttext.models import CaptionTrack, TranscriptSegment, VideoMetadata
from yttext.service import ExtractionOptions


def test_options_validate_mapping_payload() -> None:
    options = ExtractionOptions.from_mapping(
        {
            "url": " dQw4w9WgXcQ ",
            "transcript_format": "json",
            "summary_language": "ja",
            "long_summary_mode": "ask",
            "cookie_browser": "Safari",
        }
    )
    assert options.url == "dQw4w9WgXcQ"
    assert options.transcript_format == "json"
    assert options.summary_language == "ja"
    assert options.cookie_browser == "safari"

    with pytest.raises(InvalidVideoError):
        ExtractionOptions.from_mapping({"url": "x", "transcript_format": "pdf"})
    with pytest.raises(InvalidVideoError):
        ExtractionOptions.from_mapping({"url": "x", "cookie_browser": "unknown"})


def test_options_accept_common_and_custom_bcp47_summary_languages() -> None:
    common = ExtractionOptions.from_mapping({"url": "x", "summary_language": "zh-hans"})
    custom = ExtractionOptions.from_mapping({"url": "x", "summary_language": "it"})

    assert common.summary_language == "zh-Hans"
    assert custom.summary_language == "it"

    with pytest.raises(InvalidVideoError, match="BCP 47"):
        ExtractionOptions.from_mapping({"url": "x", "summary_language": "custom"})


def test_service_returns_transcript_when_summary_fails(monkeypatch) -> None:
    metadata = VideoMetadata("dQw4w9WgXcQ", "Test", 90, "", "en")
    track = CaptionTrack(({"ext": "vtt", "url": "unused"},), "en", "manual")
    monkeypatch.setattr(service, "extract_video_id", lambda _value: "dQw4w9WgXcQ")
    monkeypatch.setattr(
        service,
        "fetch_video_and_captions",
        lambda *_args, **_kwargs: (metadata, track),
    )
    monkeypatch.setattr(
        service,
        "download_and_parse_captions",
        lambda _track: (TranscriptSegment(0.0, 1.0, "Hello."),),
    )

    def fail_summary(*_args, **_kwargs):
        raise GeminiApiError("quota exceeded")

    monkeypatch.setattr(service, "call_gemini_api", fail_summary)
    progress = []
    result = service.extract_transcript(
        ExtractionOptions(url="dQw4w9WgXcQ", generate_summary=True, api_key="secret"),
        progress=lambda percent, _message: progress.append(percent),
    )

    assert "Hello." in result.transcript.content
    assert result.summary is None
    assert "quota exceeded" in (result.warning or "")
    assert progress[-1] == 100


def _pending_long_result(monkeypatch):
    metadata = VideoMetadata("dQw4w9WgXcQ", "Long test", 120, "", "en")
    track = CaptionTrack(({"ext": "json3", "url": "unused"},), "en", "automatic")
    segments = (
        TranscriptSegment(0.0, 1.0, "First."),
        TranscriptSegment(1.0, 2.0, "Second."),
    )
    monkeypatch.setattr(service, "MAX_SUMMARY_LENGTH", 10)
    monkeypatch.setattr(service, "extract_video_id", lambda _value: "dQw4w9WgXcQ")
    monkeypatch.setattr(
        service,
        "fetch_video_and_captions",
        lambda *_args, **_kwargs: (metadata, track),
    )
    monkeypatch.setattr(service, "download_and_parse_captions", lambda _track: segments)
    calls = []
    monkeypatch.setattr(
        service,
        "call_gemini_api",
        lambda text, *_args, **_kwargs: calls.append(text) or "Summary body",
    )
    result = service.extract_transcript(
        ExtractionOptions(
            url="dQw4w9WgXcQ",
            generate_summary=True,
            long_summary_mode="ask",
            api_key="secret",
        )
    )
    return result, calls


def test_long_transcript_waits_for_user_choice_before_calling_gemini(monkeypatch) -> None:
    result, calls = _pending_long_result(monkeypatch)

    assert calls == []
    assert result.summary is None
    assert result.summary_limit is not None
    assert result.summary_limit.source_characters == 14
    assert result.summary_limit.limit_characters == 10
    assert result.summary_limit.requires_confirmation is True


def test_long_transcript_can_summarize_segment_boundary_prefix(monkeypatch) -> None:
    result, calls = _pending_long_result(monkeypatch)

    resolved = service.resolve_long_summary(
        result,
        mode="truncate",
        api_key="secret",
        language="auto",
        model="gemini-test",
    )

    assert calls == ["First."]
    assert resolved.summary is not None
    assert "6 of 14 caption characters" in resolved.summary.content
    assert resolved.summary_limit is not None
    assert resolved.summary_limit.requires_confirmation is False


def test_long_transcript_can_send_all_captions(monkeypatch) -> None:
    result, calls = _pending_long_result(monkeypatch)

    resolved = service.resolve_long_summary(
        result,
        mode="full",
        api_key="secret",
        language="ja",
        model="gemini-test",
    )

    assert calls == ["First.\nSecond."]
    assert resolved.summary is not None
    assert "all 14 caption characters" in resolved.summary.content


def test_long_transcript_can_skip_summary(monkeypatch) -> None:
    result, calls = _pending_long_result(monkeypatch)

    resolved = service.resolve_long_summary(
        result,
        mode="skip",
        api_key="",
        language="auto",
        model="gemini-test",
    )

    assert calls == []
    assert resolved.summary is None
    assert resolved.summary_limit is not None
    assert resolved.summary_limit.requires_confirmation is False
    assert "[14/10 characters]" in (resolved.warning or "").replace(",", "")


def test_failed_long_summary_keeps_the_three_choices_available(monkeypatch) -> None:
    result, _calls = _pending_long_result(monkeypatch)
    monkeypatch.setattr(
        service,
        "call_gemini_api",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(GeminiApiError("input too long")),
    )

    resolved = service.resolve_long_summary(
        result,
        mode="full",
        api_key="secret",
        language="auto",
        model="gemini-test",
    )

    assert resolved.summary is None
    assert resolved.summary_limit is not None
    assert resolved.summary_limit.requires_confirmation is True
    assert "input too long" in (resolved.warning or "")


def test_summary_source_is_independent_of_transcript_output_format(monkeypatch) -> None:
    metadata = VideoMetadata("dQw4w9WgXcQ", "Test", 90, "", "en")
    track = CaptionTrack((), "en", "manual")
    segments = (TranscriptSegment(5.0, 6.0, "Caption text."),)
    monkeypatch.setattr(service, "extract_video_id", lambda _value: "dQw4w9WgXcQ")
    monkeypatch.setattr(
        service,
        "fetch_video_and_captions",
        lambda *_args, **_kwargs: (metadata, track),
    )
    monkeypatch.setattr(service, "download_and_parse_captions", lambda _track: segments)
    observed = []
    monkeypatch.setattr(
        service,
        "call_gemini_api",
        lambda text, *_args, **_kwargs: observed.append(text) or "Summary",
    )

    result = service.extract_transcript(
        ExtractionOptions(
            url="dQw4w9WgXcQ",
            transcript_format="json",
            generate_summary=True,
            api_key="secret",
        )
    )

    assert result.transcript.format == "json"
    assert observed == ["Caption text."]
    assert result.summary is not None
    assert result.summary.format == "md"
