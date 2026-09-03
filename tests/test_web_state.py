from dataclasses import fields

import pytest

from yttext.models import (
    CaptionTrack,
    OutputArtifact,
    TranscriptDocument,
    TranscriptSegment,
    VideoMetadata,
)
from yttext.service import ExtractionResult
from yttext.web_state import (
    PendingSummaryJob,
    PendingSummaryStore,
    SummaryJobBusy,
    SummaryJobExpired,
    SummaryJobNotFound,
    SummaryStoreFull,
)


def _result(character_count: int = 6) -> ExtractionResult:
    document = TranscriptDocument(
        metadata=VideoMetadata("dQw4w9WgXcQ", "Test", 10, "", "en"),
        track=CaptionTrack(
            ({"ext": "vtt", "url": "https://captions.example/source"},),
            "en",
            "manual",
        ),
        segments=(TranscriptSegment(0.0, 1.0, "Hello."),),
    )
    return ExtractionResult(
        document=document,
        transcript=OutputArtifact(
            "transcript",
            "txt",
            "dQw4w9WgXcQ_transcript.txt",
            "Hello.\n",
        ),
        summary=None,
        summary_limit=None,
        warning=None,
        character_count=character_count,
        word_count=1,
    )


def test_store_uses_random_unguessable_job_ids_and_accepts_no_credentials() -> None:
    store = PendingSummaryStore()

    first, _ttl = store.create(_result())
    second, _ttl = store.create(_result())

    assert first != second
    assert len(first) >= 40
    assert len(second) >= 40
    assert {field.name for field in fields(PendingSummaryJob)} == {
        "result",
        "expires_at",
        "busy",
    }


def test_store_removes_caption_download_details_from_summary_context() -> None:
    result = _result()
    result.document.track.formats[0]["url"] = "https://captions.example/signed-token"
    store = PendingSummaryStore()
    job_id, _ttl = store.create(result)

    stored = store.begin(job_id)

    assert stored.document.track.formats == ()
    assert stored.document.metadata.description == ""
    assert stored.document.metadata.chapters == ()


def test_store_expires_jobs_and_distinguishes_missing_ids() -> None:
    now = [100.0]
    store = PendingSummaryStore(ttl_seconds=10, clock=lambda: now[0])
    job_id, _ttl = store.create(_result())

    now[0] = 110.0
    with pytest.raises(SummaryJobExpired):
        store.begin(job_id)
    with pytest.raises(SummaryJobNotFound):
        store.begin(job_id)


def test_store_locks_active_jobs_and_deletes_completed_jobs() -> None:
    store = PendingSummaryStore()
    job_id, _ttl = store.create(_result())

    result = store.begin(job_id)
    assert result.character_count == 6
    with pytest.raises(SummaryJobBusy):
        store.begin(job_id)
    with pytest.raises(SummaryJobBusy):
        store.discard(job_id)

    store.finish(job_id, result=result)
    assert store.begin(job_id) == result
    store.finish(job_id, delete=True)
    assert len(store) == 0


def test_store_enforces_job_and_character_capacity() -> None:
    job_limited = PendingSummaryStore(max_jobs=1)
    job_limited.create(_result())
    with pytest.raises(SummaryStoreFull, match="Too many"):
        job_limited.create(_result())

    character_limited = PendingSummaryStore(max_characters=10)
    character_limited.create(_result(6))
    with pytest.raises(SummaryStoreFull, match="temporarily full"):
        character_limited.create(_result(5))


def test_finish_refreshes_the_expiration_for_a_retry() -> None:
    now = [1.0]
    store = PendingSummaryStore(ttl_seconds=10, clock=lambda: now[0])
    job_id, _ttl = store.create(_result())
    result = store.begin(job_id)

    now[0] = 9.0
    store.finish(job_id, result=result)
    now[0] = 18.0

    assert store.begin(job_id) == result
