from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

OutputFormat = Literal["md", "txt", "json", "srt", "vtt"]
ArtifactKind = Literal["transcript", "summary"]
CaptionKind = Literal["manual", "automatic"]


@dataclass(frozen=True, slots=True)
class Chapter:
    title: str
    start: float
    end: float


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    video_id: str
    title: str
    duration: int
    description: str
    language: str
    chapters: tuple[Chapter, ...] = ()

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"


@dataclass(frozen=True, slots=True)
class CaptionTrack:
    formats: tuple[dict[str, Any], ...]
    language: str
    kind: CaptionKind

    @property
    def label(self) -> str:
        prefix = "Manual captions" if self.kind == "manual" else "Auto-generated captions"
        return f"{prefix} ({self.language})"


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    start: float
    end: float
    text: str

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass(frozen=True, slots=True)
class TranscriptDocument:
    metadata: VideoMetadata
    track: CaptionTrack
    segments: tuple[TranscriptSegment, ...]


@dataclass(frozen=True, slots=True)
class OutputArtifact:
    kind: ArtifactKind
    format: OutputFormat
    filename: str
    content: str


@dataclass(frozen=True, slots=True)
class SummaryLimit:
    source_characters: int
    limit_characters: int
    requires_confirmation: bool
