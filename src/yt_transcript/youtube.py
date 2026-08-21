from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

import yt_dlp

from .errors import (
    InvalidVideoError,
    NoTranscriptError,
    TranscriptDownloadError,
    VideoFetchError,
)
from .utils import clean_japanese_text, detect_language, format_timestamp, vtt_time_to_seconds

VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
YOUTUBE_HOST_PATTERN = re.compile(
    r"^(?:[a-z0-9-]+\.)?youtube\.(?:com|[a-z]{2}|co\.[a-z]{2})$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class VideoMetadata:
    video_id: str
    title: str
    duration: int
    description: str
    language: str

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


@dataclass(frozen=True)
class CaptionTrack:
    formats: list[dict[str, Any]]
    language: str
    kind: str

    @property
    def label(self) -> str:
        prefix = "Manual captions" if self.kind == "manual" else "Auto-generated captions"
        return f"{prefix} ({self.language})"


TranscriptEntry = dict[str, float | str]


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
    caption_language: str = "auto",
    cookie_browser: str | None = None,
) -> tuple[VideoMetadata, CaptionTrack]:
    """Fetch compact video metadata and choose the best caption track."""
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

    metadata = VideoMetadata(
        video_id=str(info.get("id") or video_id),
        title=str(info.get("title") or "Untitled video"),
        duration=int(info.get("duration") or 0),
        description=str(info.get("description") or ""),
        language=detect_language(
            str(info.get("title") or ""),
            str(info.get("description") or ""),
            str(info.get("language") or ""),
        ),
    )
    track = _select_caption_track(info, caption_language, metadata.language)
    return metadata, track


def _select_caption_track(
    info: dict[str, Any],
    requested_language: str,
    detected_language: str,
) -> CaptionTrack:
    manual = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}
    preferred = detected_language if requested_language == "auto" else requested_language

    for source, kind in ((manual, "manual"), (automatic, "automatic")):
        language = _find_language(source, preferred)
        if language:
            return CaptionTrack(list(source[language]), language, kind)

    for source, kind in ((manual, "manual"), (automatic, "automatic")):
        languages = [key for key in source if key != "live_chat"]
        if languages:
            language = languages[0]
            return CaptionTrack(list(source[language]), language, kind)

    raise NoTranscriptError("No available captions were found for this video.")


def _find_language(source: dict[str, Any], preferred: str) -> str | None:
    candidates = {
        "ja": ("ja", "ja-JP", "ja-orig"),
        "en": ("en", "en-US", "en-GB", "en-orig"),
    }.get(preferred, (preferred,))
    for candidate in candidates:
        if candidate in source:
            return candidate
    prefix = f"{preferred}-"
    return next((key for key in source if key.startswith(prefix) and key != "live_chat"), None)


def download_and_parse_captions(track: CaptionTrack) -> list[TranscriptEntry]:
    """Download a selected caption file and parse it into normalized entries."""
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


def parse_json3_transcript(content: str) -> list[TranscriptEntry]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise TranscriptDownloadError("The JSON caption data was invalid.") from exc

    transcript: list[TranscriptEntry] = []
    for event in data.get("events", []):
        segments = event.get("segs") or []
        text = "".join(str(segment.get("utf8") or "") for segment in segments).strip()
        if text:
            transcript.append(
                {
                    "text": text,
                    "start": float(event.get("tStartMs") or 0) / 1000,
                    "duration": float(event.get("dDurationMs") or 0) / 1000,
                }
            )
    return transcript


def parse_vtt_transcript(content: str) -> list[TranscriptEntry]:
    transcript: list[TranscriptEntry] = []
    lines = content.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if "-->" not in line:
            index += 1
            continue

        start_text = line.split("-->", 1)[0].strip()
        index += 1
        text_lines: list[str] = []
        while index < len(lines) and lines[index].strip():
            text_lines.append(lines[index].strip())
            index += 1
        text = " ".join(text_lines)
        text = html.unescape(re.sub(r"<[^>]+>", "", text)).strip()
        if text:
            transcript.append(
                {"text": text, "start": vtt_time_to_seconds(start_text), "duration": 0.0}
            )
        index += 1
    return transcript


def parse_srv1_transcript(content: str) -> list[TranscriptEntry]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise TranscriptDownloadError("The XML caption data was invalid.") from exc

    transcript: list[TranscriptEntry] = []
    for element in root.findall(".//text"):
        text = (element.text or "").strip()
        if text:
            transcript.append(
                {
                    "text": text,
                    "start": float(element.get("start", 0)),
                    "duration": float(element.get("dur", 0)),
                }
            )
    return transcript


def _normalize_entries(entries: list[TranscriptEntry]) -> list[TranscriptEntry]:
    normalized: list[TranscriptEntry] = []
    previous_text = ""
    for entry in entries:
        text = re.sub(r"\s+", " ", str(entry.get("text") or "")).strip()
        if not text or text == previous_text:
            continue
        normalized.append(
            {
                "text": text,
                "start": float(entry.get("start") or 0),
                "duration": float(entry.get("duration") or 0),
            }
        )
        previous_text = text
    return normalized


def transcript_to_markdown(
    transcript: list[TranscriptEntry],
    metadata: VideoMetadata,
    track: CaptionTrack,
    *,
    include_timestamps: bool = True,
) -> str:
    """Convert normalized caption entries into readable Markdown paragraphs."""
    markdown = [
        f"# {metadata.title}",
        "",
        f"**Video ID:** {metadata.video_id}  ",
        f"**YouTube URL:** {metadata.url}  ",
        f"**Duration:** {format_timestamp(metadata.duration)}  ",
        f"**Captions:** {track.label}",
        "",
        "---",
        "",
    ]

    paragraph_parts: list[str] = []
    paragraph_start: float | None = None
    paragraph_length = 0

    def flush() -> None:
        nonlocal paragraph_parts, paragraph_start, paragraph_length
        if not paragraph_parts:
            return
        final_text = " ".join(paragraph_parts).strip()
        if metadata.language == "ja":
            final_text = clean_japanese_text(final_text)
        if final_text:
            prefix = (
                f"**[{format_timestamp(paragraph_start)}]** "
                if include_timestamps and paragraph_start is not None
                else ""
            )
            markdown.extend((f"{prefix}{final_text}", ""))
        paragraph_parts = []
        paragraph_start = None
        paragraph_length = 0

    for entry in transcript:
        text = str(entry["text"]).strip()
        if metadata.language == "ja":
            text = clean_japanese_text(text)
        if not text:
            continue
        if paragraph_start is None:
            paragraph_start = float(entry["start"])
        paragraph_parts.append(text)
        paragraph_length += len(text)
        if text.endswith((".", "!", "?", "。", "！", "？")) or paragraph_length >= 480:
            flush()

    flush()
    return "\n".join(markdown).rstrip() + "\n"
