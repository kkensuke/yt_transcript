from yt_transcript.utils import (
    detect_language,
    format_timestamp,
    normalize_caption_spacing,
    vtt_time_to_seconds,
)


def test_format_timestamp_is_zero_padded() -> None:
    assert format_timestamp(0) == "00:00:00"
    assert format_timestamp(3661.9) == "01:01:01"


def test_vtt_time_supports_milliseconds() -> None:
    assert vtt_time_to_seconds("01:02:03.500") == 3723.5
    assert vtt_time_to_seconds("02:03.250") == 123.25


def test_language_detection_prefers_metadata() -> None:
    assert detect_language("English title", metadata_language="ja-JP") == "ja"
    assert detect_language("日本語の動画です") == "ja"
    assert detect_language("An English video") == "en"


def test_caption_spacing_preserves_cues_and_removes_japanese_spacing() -> None:
    assert normalize_caption_spacing("[音楽] こ れ は テ ス ト です  ♪") == (
        "[音楽] これはテストです ♪"
    )
