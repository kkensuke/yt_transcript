from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from typing import Any
from urllib.parse import parse_qs, urlparse

import yt_dlp

from .errors import (
    InvalidVideoError,
    NoTranscriptError,
    TranscriptDownloadError,
    VideoFetchError,
)
from .models import CaptionTrack, Chapter, TranscriptDocument, TranscriptSegment, VideoMetadata
from .utils import detect_language, normalize_caption_spacing, vtt_time_to_seconds

VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_HOST_PATTERN = re.compile(
    r"^(?:[a-z0-9-]+\.)?youtube\.(?:com|[a-z]{2}|co\.[a-z]{2})$",
    re.IGNORECASE,
)


def extract_video_id(value: str) -> str | None:
    """Extract a validated YouTube video ID from common URL formats."""
    value = (value or "").strip()
    if VIDEO_ID_PATTERN.fullmatch(value):
        return value

    candidate = value if re.match(r"^https?://", value, re.IGNORECASE) else f"https://{value}"
    parsed = urlparse(candidate)
    hostname = (parsed.hostname or "").lower().rstrip(".")

    if hostname in {"youtu.be", "www.youtu.be"}:
        path_parts = [part for part in parsed.path.split("/") if part]
        video_id = path_parts[0] if path_parts else ""
        return video_id if VIDEO_ID_PATTERN.fullmatch(video_id) else None

    is_youtube = bool(YOUTUBE_HOST_PATTERN.fullmatch(hostname))
    is_privacy_host = hostname in {"youtube-nocookie.com", "www.youtube-nocookie.com"}
    if not (is_youtube or is_privacy_host):
        return None

    if parsed.path.rstrip("/") == "/watch":
        video_id = parse_qs(parsed.query).get("v", [""])[0]
    else:
        path_parts = [part for part in parsed.path.split("/") if part]
        video_id = (
            path_parts[1]
            if len(path_parts) >= 2 and path_parts[0] in {"embed", "shorts", "live", "v"}
            else ""
        )

    return video_id if VIDEO_ID_PATTERN.fullmatch(video_id) else None


def fetch_video_and_captions(
    value: str,
    *,
    cookie_browser: str | None = None,
) -> tuple[VideoMetadata, CaptionTrack]:
    """Fetch compact video metadata and choose an original-language caption track."""
    video_id = extract_video_id(value)
    if not video_id:
        raise InvalidVideoError("Could not identify a valid YouTube video.")

    options: dict[str, Any] = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    if cookie_browser:
        options["cookiesfrombrowser"] = (cookie_browser,)

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}",
                download=False,
            )
    except Exception as exc:
        message = str(exc).removeprefix("ERROR: ").strip()
        raise VideoFetchError(f"Could not fetch video details: {message}") from exc

    if not isinstance(info, dict):
        raise VideoFetchError("The video metadata response was invalid.")

    duration = int(info.get("duration") or 0)
    declared_language = str(info.get("language") or "").strip()
    metadata = VideoMetadata(
        video_id=str(info.get("id") or video_id),
        title=str(info.get("title") or "Untitled video"),
        duration=duration,
        description=str(info.get("description") or ""),
        language=declared_language
        or detect_language(
            str(info.get("title") or ""),
            str(info.get("description") or ""),
        ),
        chapters=_extract_chapters(info, duration),
    )
    track = _select_caption_track(info, metadata.language)
    return metadata, track


def _select_caption_track(
    info: dict[str, Any],
    detected_language: str,
) -> CaptionTrack:
    manual = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}

    manual_language = _find_language(manual, detected_language)
    if manual_language:
        return CaptionTrack(tuple(manual[manual_language]), manual_language, "manual")

    automatic_language = _find_language(
        automatic,
        detected_language,
        prefer_original_marker=True,
    )
    if automatic_language:
        return CaptionTrack(
            tuple(automatic[automatic_language]),
            automatic_language,
            "automatic",
        )

    original_automatic = next(
        (language for language in automatic if language.endswith("-orig")),
        None,
    )
    if original_automatic:
        return CaptionTrack(
            tuple(automatic[original_automatic]),
            original_automatic,
            "automatic",
        )

    manual_languages = [key for key in manual if key != "live_chat"]
    if manual_languages:
        language = manual_languages[0]
        return CaptionTrack(tuple(manual[language]), language, "manual")

    raise NoTranscriptError("No original-language captions were found for this video.")


def _find_language(
    source: dict[str, Any],
    preferred: str,
    *,
    prefer_original_marker: bool = False,
) -> str | None:
    normalized = preferred.strip()
    base_language = re.split(r"[-_]", normalized, maxsplit=1)[0].lower()
    common_locales = {
        "ja": ("ja", "ja-JP"),
        "en": ("en", "en-US", "en-GB"),
    }.get(base_language, (base_language,))
    locale_candidates = tuple(
        dict.fromkeys(
            candidate for candidate in (normalized, base_language, *common_locales) if candidate
        )
    )
    original_candidates = tuple(f"{candidate}-orig" for candidate in locale_candidates)
    candidates = (
        (*original_candidates, *locale_candidates)
        if prefer_original_marker
        else (*locale_candidates, *original_candidates)
    )
    for candidate in candidates:
        if candidate in source:
            return candidate
    if prefer_original_marker:
        return None
    prefix = f"{base_language}-"
    return next((key for key in source if key.startswith(prefix) and key != "live_chat"), None)


def _extract_chapters(info: dict[str, Any], duration: int) -> tuple[Chapter, ...]:
    raw_chapters = info.get("chapters") or []
    chapter_data: list[tuple[str, float, float | None]] = []
    for index, item in enumerate(raw_chapters, start=1):
        if not isinstance(item, dict):
            continue
        try:
            start = max(0.0, float(item.get("start_time") or 0))
            raw_end = item.get("end_time")
            end = float(raw_end) if raw_end is not None else None
        except (TypeError, ValueError):
            continue
        title = str(item.get("title") or "").strip() or f"Chapter {index}"
        chapter_data.append((title, start, end))

    chapter_data.sort(key=lambda item: item[1])
    chapters: list[Chapter] = []
    for index, (title, start, raw_end) in enumerate(chapter_data):
        next_start = chapter_data[index + 1][1] if index + 1 < len(chapter_data) else None
        fallback_end = next_start if next_start is not None else float(duration)
        end = raw_end if raw_end is not None and raw_end > start else fallback_end
        chapters.append(Chapter(title=title, start=start, end=max(start, end)))
    return tuple(chapters)


def download_and_parse_captions(track: CaptionTrack) -> tuple[TranscriptSegment, ...]:
    """Download a selected caption file and parse it into normalized segments."""
    priorities = {"json3": 0, "vtt": 1, "srv1": 2}
    supported = [item for item in track.formats if item.get("ext") in priorities]
    if not supported:
        raise TranscriptDownloadError("No supported caption format was found.")

    selected = min(supported, key=lambda item: priorities[str(item.get("ext"))])
    try:
        headers = {str(key): str(value) for key, value in selected.get("http_headers", {}).items()}
        request = urllib.request.Request(str(selected["url"]), headers=headers)
        with urllib.request.urlopen(request, timeout=45) as response:
            content = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise TranscriptDownloadError(
                "YouTube temporarily rate-limited caption requests (HTTP 429).",
                hint=(
                    "Wait and try again. If the problem persists, select cookies "
                    "from a signed-in browser."
                ),
            ) from exc
        if exc.code == 403:
            raise TranscriptDownloadError(
                "Access to the captions was denied (HTTP 403).",
                hint="Select cookies from a browser that can view this video.",
            ) from exc
        raise TranscriptDownloadError(f"Could not download the captions: {exc}") from exc
    except (KeyError, OSError, urllib.error.URLError) as exc:
        raise TranscriptDownloadError(f"Could not download the captions: {exc}") from exc

    extension = selected.get("ext")
    if extension == "json3":
        entries = parse_json3_transcript(content)
    elif extension == "vtt":
        entries = parse_vtt_transcript(content)
    else:
        entries = parse_srv1_transcript(content)

    entries = _normalize_entries(entries)
    if not entries:
        raise TranscriptDownloadError("Caption data was downloaded but could not be parsed.")
    return entries


def parse_json3_transcript(content: str) -> list[TranscriptSegment]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise TranscriptDownloadError("The JSON caption data was invalid.") from exc

    transcript: list[TranscriptSegment] = []
    for event in data.get("events", []):
        segments = event.get("segs") or []
        text = _join_json3_segments(str(segment.get("utf8") or "") for segment in segments).strip()
        if text:
            start = float(event.get("tStartMs") or 0) / 1000
            duration = float(event.get("dDurationMs") or 0) / 1000
            transcript.append(TranscriptSegment(start=start, end=start + duration, text=text))
    return transcript


def parse_vtt_transcript(content: str) -> list[TranscriptSegment]:
    transcript: list[TranscriptSegment] = []
    lines = content.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if "-->" not in line:
            index += 1
            continue

        start_text, end_and_settings = line.split("-->", 1)
        end_text = end_and_settings.strip().split(maxsplit=1)[0]
        index += 1
        text_lines: list[str] = []
        while index < len(lines) and lines[index].strip():
            text_lines.append(lines[index].strip())
            index += 1
        text = " ".join(text_lines)
        text = html.unescape(re.sub(r"<[^>]+>", "", text)).strip()
        if text:
            start = vtt_time_to_seconds(start_text.strip())
            end = vtt_time_to_seconds(end_text)
            transcript.append(TranscriptSegment(start=start, end=end, text=text))
        index += 1
    return transcript


def parse_srv1_transcript(content: str) -> list[TranscriptSegment]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise TranscriptDownloadError("The XML caption data was invalid.") from exc

    transcript: list[TranscriptSegment] = []
    for element in root.findall(".//text"):
        text = (element.text or "").strip()
        if text:
            start = float(element.get("start", 0))
            duration = float(element.get("dur", 0))
            transcript.append(TranscriptSegment(start=start, end=start + duration, text=text))
    return transcript


def _join_json3_segments(parts: Iterable[str]) -> str:
    text = ""
    for raw_part in parts:
        part = html.unescape(str(raw_part or "")).replace("\n", " ")
        if not part:
            continue
        if text and _needs_segment_space(text[-1], part[0]):
            text += " "
        text += part
    return text.strip()


def _needs_segment_space(left: str, right: str) -> bool:
    if left.isspace() or right.isspace():
        return False
    return left.isascii() and left.isalnum() and right.isascii() and right.isalnum()


def _normalize_entries(entries: list[TranscriptSegment]) -> tuple[TranscriptSegment, ...]:
    prepared: list[TranscriptSegment] = []
    for entry in entries:
        text = normalize_caption_spacing(entry.text)
        if text:
            prepared.append(
                TranscriptSegment(
                    start=max(0.0, float(entry.start)),
                    end=max(0.0, float(entry.end)),
                    text=text,
                )
            )

    normalized: list[TranscriptSegment] = []
    for index, entry in enumerate(prepared):
        next_start = prepared[index + 1].start if index + 1 < len(prepared) else None
        end = entry.end
        if end <= entry.start:
            end = (
                next_start
                if next_start is not None and next_start > entry.start
                else entry.start + 2
            )
        normalized.append(TranscriptSegment(start=entry.start, end=end, text=entry.text))
    return tuple(normalized)


def transcript_to_markdown(
    transcript: list[TranscriptSegment | dict[str, float | str]],
    metadata: VideoMetadata,
    track: CaptionTrack,
    *,
    include_timestamps: bool = True,
) -> str:
    """Compatibility wrapper; Markdown timestamps are always included."""
    del include_timestamps
    segments: list[TranscriptSegment] = []
    for entry in transcript:
        if isinstance(entry, TranscriptSegment):
            segments.append(entry)
            continue
        start = float(entry.get("start") or 0)
        duration = float(entry.get("duration") or 0)
        segments.append(
            TranscriptSegment(
                start=start,
                end=start + duration,
                text=str(entry.get("text") or ""),
            )
        )
    from .renderers import render_transcript

    document = TranscriptDocument(metadata, track, _normalize_entries(segments))
    return render_transcript(document, "md").content
