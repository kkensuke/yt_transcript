import re

JAPANESE_PATTERN = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def format_timestamp(seconds: float | int | None) -> str:
    """Convert seconds to a stable HH:MM:SS timestamp."""
    total = max(0, int(seconds or 0))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def vtt_time_to_seconds(value: str) -> float:
    """Convert a WebVTT timestamp into seconds."""
    try:
        parts = value.strip().replace(",", ".").split(":")
        if len(parts) == 3:
            hours, minutes = int(parts[0]), int(parts[1])
            seconds = float(parts[2])
        elif len(parts) == 2:
            hours, minutes, seconds = 0, int(parts[0]), float(parts[1])
        else:
            hours, minutes, seconds = 0, 0, float(parts[0])
        return hours * 3600 + minutes * 60 + seconds
    except (TypeError, ValueError):
        return 0.0


def detect_language(
    title: str,
    description: str = "",
    metadata_language: str | None = None,
) -> str:
    """Detect Japanese/English, preferring YouTube's language metadata."""
    normalized = (metadata_language or "").lower()
    if normalized.startswith("ja"):
        return "ja"
    if normalized.startswith("en"):
        return "en"

    text = f"{title} {description}".strip()
    if not text:
        return "en"
    japanese_count = len(JAPANESE_PATTERN.findall(text))
    visible_count = sum(not char.isspace() for char in text)
    return "ja" if visible_count and japanese_count / visible_count >= 0.12 else "en"


def clean_japanese_text(text: str) -> str:
    """Remove common caption noise and spaces between Japanese characters."""
    for tag in (
        "[音楽]",
        "♪",
        "♫",
        "♬",
        "♩",
        "[拍手]",
        "[笑い]",
        "[笑]",
        "[音響効果]",
        "[効果音]",
    ):
        text = text.replace(tag, "")

    japanese_range = r"\u3040-\u30ff\u3400-\u9fff"
    text = re.sub(rf"(?<=[{japanese_range}])\s+(?=[{japanese_range}])", "", text)
    return re.sub(r"\s+", " ", text).strip()
