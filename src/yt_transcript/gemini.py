from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .errors import GeminiApiError
from .utils import detect_language, format_timestamp
from .youtube import VideoMetadata

DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-flash-lite-latest"
GEMINI_API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


def list_gemini_models(api_key: str) -> list[str]:
    """Return Gemini model IDs that support generateContent."""
    key = api_key.strip()
    if not key:
        raise GeminiApiError("No Gemini API key is configured.")

    models: set[str] = set()
    page_token = ""
    while True:
        query_values = {"key": key, "pageSize": "100"}
        if page_token:
            query_values["pageToken"] = page_token
        url = f"{GEMINI_API_ROOT}/models?{urllib.parse.urlencode(query_values)}"
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = _http_error_message(exc)
            raise GeminiApiError(f"Gemini API error ({exc.code}): {detail}") from exc
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise GeminiApiError(f"Could not load Gemini models: {exc}") from exc

        for item in result.get("models", []):
            if "generateContent" not in (item.get("supportedGenerationMethods") or []):
                continue
            name = str(item.get("name") or "")
            model_id = name.removeprefix("models/").strip()
            if model_id:
                models.add(model_id)

        page_token = str(result.get("nextPageToken") or "")
        if not page_token:
            break

    return sorted(models)


def call_gemini_api(
    text: str,
    api_key: str,
    *,
    language: str = "auto",
    model: str = DEFAULT_GEMINI_MODEL,
) -> str:
    """Summarize transcript Markdown with Gemini's generateContent endpoint."""
    if not api_key.strip():
        raise GeminiApiError("No Gemini API key is configured.")

    resolved_language = detect_language(text) if language == "auto" else language
    prompt = _build_prompt(text, resolved_language)
    query = urllib.parse.urlencode({"key": api_key.strip()})
    model_name = urllib.parse.quote(model.strip(), safe="-_.")
    url = f"{GEMINI_API_ROOT}/models/{model_name}:generateContent?{query}"
    body = json.dumps(
        {"contents": [{"parts": [{"text": prompt}]}]},
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = _http_error_message(exc)
        raise GeminiApiError(f"Gemini API error ({exc.code}): {detail}") from exc
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise GeminiApiError(f"Could not connect to the Gemini API: {exc}") from exc

    try:
        summary = result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        feedback = result.get("promptFeedback", {}) if isinstance(result, dict) else {}
        reason = feedback.get("blockReason") or "the response did not contain summary text"
        raise GeminiApiError(f"Could not generate a summary: {reason}") from exc

    if not str(summary).strip():
        raise GeminiApiError("The Gemini API returned an empty summary.")
    return str(summary).strip()


def _http_error_message(error: urllib.error.HTTPError) -> str:
    try:
        payload = json.loads(error.read().decode("utf-8", errors="replace"))
        return str(payload.get("error", {}).get("message") or "The request was rejected")
    except (AttributeError, json.JSONDecodeError):
        return "The request was rejected"


def _build_prompt(text: str, language: str) -> str:
    if language == "ja":
        return f"""Summarize the following YouTube transcript in Japanese as a clear,
structured Markdown document.

- Write the complete summary in natural Japanese
- Preserve important claims, evidence, and conclusions
- Use headings and lists where they improve readability
- Correct obvious ASR errors from context
- Mark uncertain interpretations with [Uncertain]
- Include English equivalents for technical terms in parentheses when helpful
- Use LaTeX for formulas when helpful
- Return only the summary document, without a preface or acknowledgement

---

{text}"""

    return f"""Summarize the following YouTube transcript as a clear, structured Markdown document.

- Preserve important claims, evidence, and conclusions
- Use headings and lists where they improve readability
- Correct obvious ASR errors from context
- Mark uncertain interpretations with [Uncertain]
- Use LaTeX for formulas when helpful
- Return only the summary document, without a preface or acknowledgement

---

{text}"""


def create_summary_markdown(metadata: VideoMetadata, summary: str) -> str:
    return (
        f"# {metadata.title} - Summary\n\n"
        f"**Video ID:** {metadata.video_id}  \n"
        f"**YouTube URL:** {metadata.url}  \n"
        f"**Duration:** {format_timestamp(metadata.duration)}\n\n"
        f"---\n\n{summary.strip()}\n\n"
        "---\n\n*Summary generated using Gemini*\n"
    )
