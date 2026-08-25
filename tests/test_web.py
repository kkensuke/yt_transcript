import json
from dataclasses import replace

from fastapi.testclient import TestClient

from yt_transcript import web
from yt_transcript.models import (
    CaptionTrack,
    OutputArtifact,
    TranscriptDocument,
    TranscriptSegment,
    VideoMetadata,
)
from yt_transcript.service import ExtractionResult
from yt_transcript.web_state import PendingSummaryStore


def _result(*, character_count: int = 6) -> ExtractionResult:
    document = TranscriptDocument(
        metadata=VideoMetadata("dQw4w9WgXcQ", "Test video", 10, "", "en"),
        track=CaptionTrack((), "en", "manual"),
        segments=(TranscriptSegment(0.0, 1.0, "Hello."),),
    )
    return ExtractionResult(
        document=document,
        transcript=OutputArtifact(
            "transcript",
            "md",
            "dQw4w9WgXcQ_transcript.md",
            "# Test video\n\nHello.\n",
        ),
        summary=None,
        summary_limit=None,
        warning=None,
        character_count=character_count,
        word_count=1,
    )


def _summary(result: ExtractionResult) -> ExtractionResult:
    return replace(
        result,
        summary=OutputArtifact(
            "summary",
            "md",
            "dQw4w9WgXcQ_summarized.md",
            "# Summary\n\nShort summary.\n",
        ),
        warning=None,
    )


def _extract_job(client: TestClient) -> str:
    response = client.post(
        "/api/extract",
        json={"url": "dQw4w9WgXcQ", "prepare_summary": True},
    )
    assert response.status_code == 200
    return response.json()["summary_job"]["id"]


def test_info_and_static_ui_do_not_expose_server_credentials(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "environment-secret")
    monkeypatch.setenv("GEMINI_MODEL", "environment-model")
    client = TestClient(web.create_app(mode="local"))

    info = client.get("/api/info")
    index = client.get("/")

    assert info.status_code == 200
    assert info.json()["capabilities"] == {
        "byok": True,
        "server_api_key": False,
        "browser_cookies": True,
    }
    assert info.json()["gemini_model"] == web.DEFAULT_GEMINI_MODEL
    assert "environment-secret" not in info.text + index.text
    assert "environment-model" not in info.text + index.text


def test_extract_never_accepts_or_forwards_an_api_key(monkeypatch) -> None:
    observed = []
    monkeypatch.setattr(
        web,
        "extract_transcript_only",
        lambda options: observed.append(options) or _result(),
    )
    store = PendingSummaryStore()
    client = TestClient(web.create_app(mode="local", store=store))
    secret = "user-secret-key"

    rejected = client.post(
        "/api/extract",
        json={"url": "dQw4w9WgXcQ", "prepare_summary": True, "api_key": secret},
    )
    accepted = client.post(
        "/api/extract",
        json={"url": "dQw4w9WgXcQ", "prepare_summary": True},
    )

    assert rejected.status_code == 422
    assert secret not in rejected.text
    assert accepted.status_code == 200
    assert len(observed) == 1
    assert observed[0].generate_summary is False
    assert observed[0].api_key == ""
    assert accepted.json()["summary_job"]["id"]
    assert secret not in repr(store._jobs)


def test_summary_requires_the_user_header_and_deletes_completed_job(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "operator-key-must-be-ignored")
    monkeypatch.setattr(web, "extract_transcript_only", lambda _options: _result())
    observed = []

    def summarize(result, **kwargs):
        observed.append(kwargs)
        return _summary(result)

    monkeypatch.setattr(web, "summarize_transcript", summarize)
    store = PendingSummaryStore()
    client = TestClient(web.create_app(mode="local", store=store))
    job_id = _extract_job(client)
    secret = "user-secret-key"
    payload = {
        "job_id": job_id,
        "mode": "full",
        "summary_language": "ja",
        "gemini_model": "gemini-test",
    }

    missing = client.post("/api/summarize", json=payload)
    completed = client.post(
        "/api/summarize",
        json=payload,
        headers={web.API_KEY_HEADER: secret},
    )

    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "missing_api_key"
    assert "operator-key-must-be-ignored" not in missing.text
    assert completed.status_code == 200
    assert completed.json()["result"]["summary"]["content"].startswith("# Summary")
    assert completed.json()["summary_job"] is None
    assert observed == [
        {
            "mode": "full",
            "api_key": secret,
            "language": "ja",
            "model": "gemini-test",
        }
    ]
    assert secret not in missing.text + completed.text
    assert len(store) == 0


def test_failed_summary_keeps_only_the_job_context_for_retry(monkeypatch) -> None:
    monkeypatch.setattr(web, "extract_transcript_only", lambda _options: _result())
    attempts = []

    def summarize(result, **kwargs):
        attempts.append(kwargs["api_key"])
        if len(attempts) == 1:
            return replace(result, warning="The transcript was created, but summarization failed.")
        return _summary(result)

    monkeypatch.setattr(web, "summarize_transcript", summarize)
    store = PendingSummaryStore()
    client = TestClient(web.create_app(mode="local", store=store))
    job_id = _extract_job(client)
    payload = {
        "job_id": job_id,
        "mode": "full",
        "summary_language": "auto",
        "gemini_model": "gemini-test",
    }

    failed = client.post(
        "/api/summarize",
        json=payload,
        headers={web.API_KEY_HEADER: "first-key"},
    )
    assert failed.status_code == 200
    assert failed.json()["summary_job"]["id"] == job_id
    assert len(store) == 1

    retried = client.post(
        "/api/summarize",
        json=payload,
        headers={web.API_KEY_HEADER: "second-key"},
    )

    assert len(store) == 0
    assert retried.status_code == 200
    assert retried.json()["summary_job"] is None
    assert attempts == ["first-key", "second-key"]
    assert "first-key" not in failed.text
    assert "second-key" not in retried.text


def test_summary_can_be_skipped_without_a_key(monkeypatch) -> None:
    monkeypatch.setattr(web, "extract_transcript_only", lambda _options: _result())
    observed = []

    def skip(result, **kwargs):
        observed.append(kwargs)
        return replace(result, warning="Summary skipped by the user.")

    monkeypatch.setattr(web, "summarize_transcript", skip)
    store = PendingSummaryStore()
    client = TestClient(web.create_app(mode="local", store=store))
    job_id = _extract_job(client)

    response = client.post(
        "/api/summarize",
        json={
            "job_id": job_id,
            "mode": "skip",
            "summary_language": "auto",
            "gemini_model": "gemini-test",
        },
    )

    assert response.status_code == 200
    assert observed[0]["api_key"] == ""
    assert len(store) == 0


def test_model_discovery_uses_only_the_explicit_header(monkeypatch) -> None:
    observed = []
    monkeypatch.setattr(
        web,
        "fetch_gemini_models",
        lambda key: observed.append(key) or ["gemini-flash-latest"],
    )
    client = TestClient(web.create_app(mode="local"))
    secret = "model-list-key"

    missing = client.post("/api/gemini/models", json={})
    oversized_key = "s" * 513
    rejected = client.post(
        "/api/gemini/models",
        json={},
        headers={web.API_KEY_HEADER: oversized_key},
    )
    response = client.post(
        "/api/gemini/models",
        json={},
        headers={web.API_KEY_HEADER: secret},
    )

    assert missing.status_code == 400
    assert rejected.status_code == 422
    assert oversized_key not in rejected.text
    assert response.json() == {"ok": True, "models": ["gemini-flash-latest"]}
    assert observed == [secret]
    assert secret not in response.text


def test_hosted_mode_disables_browser_cookie_access(monkeypatch) -> None:
    called = []
    monkeypatch.setattr(
        web,
        "extract_transcript_only",
        lambda _options: called.append(True) or _result(),
    )
    client = TestClient(
        web.create_app(
            mode="hosted",
            allowed_hosts=["testserver"],
            allowed_origins={"https://transcript.example"},
        )
    )

    response = client.post(
        "/api/extract",
        json={"url": "dQw4w9WgXcQ", "cookie_browser": "chrome"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "browser_cookies_unavailable"
    assert client.get("/api/info").json()["capabilities"]["browser_cookies"] is False
    assert called == []


def test_request_guards_and_security_headers() -> None:
    client = TestClient(
        web.create_app(
            mode="hosted",
            allowed_hosts=["testserver"],
            allowed_origins={"https://transcript.example"},
        )
    )
    job_payload = {"job_id": "x" * 24}

    wrong_type = client.post(
        "/api/summary/discard",
        content=json.dumps(job_payload),
        headers={"Content-Type": "text/plain"},
    )
    wrong_origin = client.post(
        "/api/summary/discard",
        json=job_payload,
        headers={"Origin": "https://evil.example"},
    )
    allowed_origin = client.post(
        "/api/summary/discard",
        json=job_payload,
        headers={"Origin": "https://transcript.example"},
    )
    wrong_host = client.get("/", headers={"Host": "evil.example"})
    index = client.get("/")
    script = client.get("/static/app.js")
    hidden_python = client.get("/static/__init__.py")
    info = client.get("/api/info")

    assert wrong_type.status_code == 415
    assert wrong_origin.status_code == 403
    assert allowed_origin.status_code == 200
    assert wrong_host.status_code == 400
    assert script.status_code == 200
    assert hidden_python.status_code == 404
    assert "default-src 'self'" in index.headers["content-security-policy"]
    assert index.headers["referrer-policy"] == "no-referrer"
    assert index.headers["x-content-type-options"] == "nosniff"
    assert index.headers["x-frame-options"] == "DENY"
    assert wrong_origin.headers["cache-control"] == "no-store"
    assert info.headers["cache-control"] == "no-store"


def test_oversized_and_unexpected_errors_are_safe(monkeypatch) -> None:
    client = TestClient(web.create_app(mode="local"), raise_server_exceptions=False)
    secret = "body-secret-value"
    oversized = json.dumps({"url": secret * 5_000})

    too_large = client.post(
        "/api/extract",
        content=oversized,
        headers={"Content-Type": "application/json"},
    )
    monkeypatch.setattr(
        web,
        "extract_transcript_only",
        lambda _options: (_ for _ in ()).throw(RuntimeError("private backend detail")),
    )
    unexpected = client.post("/api/extract", json={"url": "dQw4w9WgXcQ"})

    assert too_large.status_code == 413
    assert too_large.json()["error"]["code"] == "request_too_large"
    assert secret not in too_large.text
    assert too_large.headers["cache-control"] == "no-store"
    assert "default-src 'self'" in too_large.headers["content-security-policy"]
    assert unexpected.status_code == 500
    assert unexpected.json()["error"]["code"] == "unexpected_error"
    assert "private backend detail" not in unexpected.text


def test_expired_summary_job_returns_gone(monkeypatch) -> None:
    now = [10.0]
    store = PendingSummaryStore(ttl_seconds=5, clock=lambda: now[0])
    monkeypatch.setattr(web, "extract_transcript_only", lambda _options: _result())
    client = TestClient(web.create_app(mode="local", store=store))
    job_id = _extract_job(client)
    now[0] = 16.0

    response = client.post(
        "/api/summarize",
        json={
            "job_id": job_id,
            "mode": "full",
            "summary_language": "auto",
            "gemini_model": "gemini-test",
        },
        headers={web.API_KEY_HEADER: "ephemeral-key"},
    )

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "summary_job_expired"
    assert "ephemeral-key" not in response.text
