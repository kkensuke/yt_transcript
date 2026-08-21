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
