import json

from yt_transcript import gemini


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_list_gemini_models_filters_generate_content_and_follows_pagination(monkeypatch) -> None:
    responses = [
        {
            "models": [
                {
                    "name": "models/gemini-flash-latest",
                    "supportedGenerationMethods": ["generateContent", "countTokens"],
                },
                {
                    "name": "models/embedding-001",
                    "supportedGenerationMethods": ["embedContent"],
                },
            ],
            "nextPageToken": "page-2",
        },
        {
            "models": [
                {
                    "name": "models/gemini-pro-latest",
                    "supportedGenerationMethods": ["generateContent"],
                }
            ]
        },
    ]
    requested_urls = []

    def fake_urlopen(request, timeout):
        requested_urls.append(request.full_url)
        assert timeout == 30
        return FakeResponse(responses.pop(0))

    monkeypatch.setattr(gemini.urllib.request, "urlopen", fake_urlopen)

    assert gemini.list_gemini_models("secret-key") == [
        "gemini-flash-latest",
        "gemini-pro-latest",
    ]
    assert "pageToken=page-2" in requested_urls[1]
    assert "secret-key" in requested_urls[0]


def test_auto_prompt_asks_gemini_to_follow_the_transcript_language() -> None:
    prompt = gemini._build_prompt("字幕 text", "auto")

    assert "Write the summary in the same primary language as the transcript." in prompt
    assert "Retain important source-language technical terms" in prompt
    assert "字幕 text" in prompt


def test_explicit_and_custom_languages_use_the_same_prompt_structure() -> None:
    japanese_prompt = gemini._build_prompt("Source", "ja")
    custom_prompt = gemini._build_prompt("Source", "it")

    assert "Write the complete summary in Japanese." in japanese_prompt
    assert 'Write the complete summary in the language identified by BCP 47 tag "it".' in (
        custom_prompt
    )
    for instruction in (
        "Preserve important claims, evidence, and conclusions",
        "Retain important source-language technical terms in parentheses when helpful",
        "Return only the summary document",
    ):
        assert instruction in japanese_prompt
        assert instruction in custom_prompt
