from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from .errors import GeminiApiError
from .models import VideoMetadata
from .summary_languages import (
    AUTO_SUMMARY_LANGUAGE,
    normalize_summary_language,
    summary_language_prompt_name,
)
from .utils import format_timestamp

DEFAULT_GEMINI_MODEL = "gemini-flash-lite-latest"
GEMINI_API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


def list_gemini_models(api_key: str) -> list[str]:
    """Return Gemini model IDs that support generateContent."""
    key = api_key.strip()
    if not key:
        raise GeminiApiError("No Gemini API key is configured.")

    models: set[str] = set()
    page_token = ""
    while True:
        query_values = {"pageSize": "100"}
        if page_token:
            query_values["pageToken"] = page_token
        url = f"{GEMINI_API_ROOT}/models?{urllib.parse.urlencode(query_values)}"
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "X-Goog-Api-Key": key},
        )
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
    """Summarize normalized caption text with Gemini's generateContent endpoint."""
    if not api_key.strip():
        raise GeminiApiError("No Gemini API key is configured.")

    prompt = _build_prompt(text, language)
    model_name = urllib.parse.quote(model.strip(), safe="-_.")
    url = f"{GEMINI_API_ROOT}/models/{model_name}:generateContent"
    body = json.dumps(
        {"contents": [{"parts": [{"text": prompt}]}]},
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key.strip(),
        },
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
    normalized_language = normalize_summary_language(language)
    if normalized_language == AUTO_SUMMARY_LANGUAGE:
        language_instruction = "Write the summary in the same primary language as the transcript."
    else:
        language_name = summary_language_prompt_name(normalized_language)
        language_instruction = f"Write the complete summary in {language_name}."

    return f"""Summarize the following YouTube transcript as a clear, structured Markdown document.

- {language_instruction}
- Preserve important claims, evidence, and conclusions
- Use the Markdown features supported by the preview: paragraphs, H1-H6 headings, emphasis,
  strikethrough, links, blockquotes, fenced code blocks, nested ordered or unordered lists,
  tables, and horizontal rules
- Correct obvious ASR errors from context
- Mark uncertain interpretations with [Uncertain]
- Retain important source-language technical terms in parentheses when helpful
- Do not use raw HTML, images, task lists, or LaTeX; write formulas as plain text or inline code
- Return only the summary document, without a preface or acknowledgement

---

{text}"""


def create_summary_markdown(
    metadata: VideoMetadata,
    summary: str,
    *,
    source_note: str | None = None,
) -> str:
    note = f"\n*{source_note}*\n" if source_note else ""
    return (
        f"# {metadata.title} - Summary\n\n"
        f"**Video ID:** {metadata.video_id}  \n"
        f"**YouTube URL:** {metadata.url}  \n"
        f"**Duration:** {format_timestamp(metadata.duration)}\n\n"
        f"---\n\n{summary.strip()}\n{note}\n"
        "---\n\n*Summary generated using Gemini*\n"
    )
