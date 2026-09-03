from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, replace

from .service import ExtractionResult


class SummaryJobError(Exception):
    """Base class for short-lived summary job failures."""


class SummaryJobNotFound(SummaryJobError):
    pass


class SummaryJobExpired(SummaryJobError):
    pass


class SummaryJobBusy(SummaryJobError):
    pass


class SummaryStoreFull(SummaryJobError):
    pass


@dataclass(slots=True)
class PendingSummaryJob:
    result: ExtractionResult
    expires_at: float
    busy: bool = False


class PendingSummaryStore:
    """Bounded in-memory store for transcript state; credentials are never accepted."""

    def __init__(
        self,
        *,
        ttl_seconds: int = 600,
        max_jobs: int = 64,
        max_characters: int = 5_000_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0 or max_jobs <= 0 or max_characters <= 0:
            raise ValueError("Summary store limits must be positive.")
        self.ttl_seconds = ttl_seconds
        self.max_jobs = max_jobs
        self.max_characters = max_characters
        self._clock = clock
        self._jobs: dict[str, PendingSummaryJob] = {}
        self._lock = threading.Lock()

    def create(self, result: ExtractionResult) -> tuple[str, int]:
        with self._lock:
            self._purge_expired_locked()
            total_characters = sum(job.result.character_count for job in self._jobs.values())
            if len(self._jobs) >= self.max_jobs:
                raise SummaryStoreFull("Too many summaries are waiting to be processed.")
            if total_characters + result.character_count > self.max_characters:
                raise SummaryStoreFull("The pending summary store is temporarily full.")

            job_id = secrets.token_urlsafe(32)
            while job_id in self._jobs:
                job_id = secrets.token_urlsafe(32)
            self._jobs[job_id] = PendingSummaryJob(
                result=_minimal_summary_context(result),
                expires_at=self._clock() + self.ttl_seconds,
            )
            return job_id, self.ttl_seconds

    def begin(self, job_id: str) -> ExtractionResult:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise SummaryJobNotFound("The summary job was not found.")
            if not job.busy and job.expires_at <= self._clock():
                del self._jobs[job_id]
                raise SummaryJobExpired("The summary job has expired.")
            if job.busy:
                raise SummaryJobBusy("The summary job is already being processed.")
            job.busy = True
            return job.result

    def finish(
        self,
        job_id: str,
        *,
        result: ExtractionResult | None = None,
        delete: bool = False,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            if delete:
                del self._jobs[job_id]
                return
            if result is not None:
                job.result = _minimal_summary_context(result)
            job.busy = False
            job.expires_at = self._clock() + self.ttl_seconds

    def discard(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            if job.busy:
                raise SummaryJobBusy("The summary job is already being processed.")
            del self._jobs[job_id]

    def __len__(self) -> int:
        with self._lock:
            self._purge_expired_locked()
            return len(self._jobs)

    def _purge_expired_locked(self) -> None:
        now = self._clock()
        expired = [
            job_id for job_id, job in self._jobs.items() if not job.busy and job.expires_at <= now
        ]
        for job_id in expired:
            del self._jobs[job_id]


def _minimal_summary_context(result: ExtractionResult) -> ExtractionResult:
    """Drop caption download details and unused video metadata before temporary storage."""
    metadata = replace(result.document.metadata, description="", chapters=())
    track = replace(result.document.track, formats=())
    document = replace(result.document, metadata=metadata, track=track)
    return replace(result, document=document)
