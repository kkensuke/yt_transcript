import re
from importlib.resources import files


def _asset(name: str) -> str:
    return files("yttext.ui").joinpath(name).read_text(encoding="utf-8")


def test_ui_uses_external_same_origin_assets() -> None:
    html = _asset("index.html")

    for asset in (
        "styles.css",
        "enhancements.css",
        "theme-control.css",
        "app.js",
        "enhancements.js",
        "theme-control.js",
    ):
        assert f"/static/{asset}" in html
    assert not re.search(r"<script(?![^>]+\bsrc=)[^>]*>", html)
    assert "https://cdn" not in html


def test_ui_labels_and_descriptions_reference_existing_controls() -> None:
    html = _asset("index.html")
    ids = re.findall(r'\bid="([^"]+)"', html)

    assert len(ids) == len(set(ids))
    for target in re.findall(r'<label[^>]+for="([^"]+)"', html):
        assert target in ids
    for references in re.findall(r'aria-describedby="([^"]+)"', html):
        assert set(references.split()).issubset(ids)


def test_ui_contains_every_element_required_by_the_main_script() -> None:
    html = _asset("index.html")
    script = _asset("app.js")
    html_ids = set(re.findall(r'\bid="([^"]+)"', html))
    script_targets = set(re.findall(r'document\.getElementById\("([^"]+)"\)', script))

    assert script_targets.issubset(html_ids)


def test_ui_uses_byok_only_for_summary_requests() -> None:
    html = _asset("index.html")
    script = _asset("app.js")
    enhancements = _asset("enhancements.js")
    all_ui = html + script + enhancements + _asset("theme-control.js")

    assert "/api/extract" in script
    assert "/api/summarize" in script
    assert 'headers["X-Gemini-Api-Key"]' in script
    assert 'headers["X-Gemini-Api-Key"] = apiKey' in enhancements
    assert "hasServerApiKey" in script
    assert "!apiKey && !serverApiKey" in enhancements
    payload_start = script.index("const payload = {", script.index("async function handleSubmit"))
    payload_end = script.index("};", payload_start)
    assert "apiKey" not in script[payload_start:payload_end]
    assert "window.pywebview" not in all_ui
    assert "localStorage" not in all_ui
    assert "sessionStorage" not in all_ui


def test_ui_distinguishes_missing_environment_and_entered_api_keys() -> None:
    html = _asset("index.html")
    script = _asset("app.js")
    styles = _asset("styles.css")

    assert 'id="apiKeySource"' in html
    assert 'role="status"' in html
    assert 'aria-live="polite"' in html
    assert 'aria-atomic="true"' in html
    for source_class in (
        "config-source-missing",
        "config-source-ready",
        "config-source-entered",
    ):
        assert source_class in script
        assert f".{source_class}" in styles
    for message in (
        "API key in use",
        "API key needed",
        "Gemini API key is not configured",
        "Using environment variable GEMINI_API_KEY",
        "Using the key entered in this tab",
    ):
        assert message in script
    assert 'elements.apiKey.addEventListener("input", () =>' in script
    assert "renderApiKeyStatus();" in script
    assert "elements.apiKeySource.dataset.state" in script


def test_ui_limits_api_key_lifetime_and_omits_browser_credentials() -> None:
    html = _asset("index.html")
    script = _asset("app.js")
    enhancements = _asset("enhancements.js")

    api_key_input = re.search(r'<input\s+id="apiKey"(?P<attrs>[^>]*)>', html, re.S)
    assert api_key_input is not None
    assert 'type="password"' in api_key_input.group("attrs")
    assert 'autocomplete="off"' in api_key_input.group("attrs")
    assert "value=" not in api_key_input.group("attrs")
    assert 'id="clearApiKeyButton"' in html
    assert 'window.addEventListener("pagehide"' in script
    assert "clearApiKey({ focus: false })" in script
    assert 'credentials: "omit"' in script
    assert 'credentials: "omit"' in enhancements


def test_ui_supports_formats_summary_choices_downloads_and_model_discovery() -> None:
    html = _asset("index.html")
    script = _asset("app.js")
    enhancements = _asset("enhancements.js")

    for output_format in ("md", "txt", "json", "srt", "vtt"):
        assert f'<option value="{output_format}">' in html
    for mode in ("truncate", "full", "skip"):
        assert f'data-summary-mode="{mode}"' in html
    assert "new Blob" in script
    assert "URL.createObjectURL" in script
    assert "downloadArtifact" in script
    assert re.search(r'<select\s+id="geminiModel"\b', html)
    assert not re.search(r'<input\s+id="geminiModel"\b', html)
    assert 'fetch("/api/info"' in enhancements
    assert "appInfo?.capabilities?.server_api_key" in enhancements
    assert "if (serverApiKey) await loadModels();" in enhancements
    assert "Load available models" in enhancements
    assert "Refresh models" in enhancements
    assert "/api/gemini/models" in enhancements
    assert "Choose a Gemini model" in enhancements


def test_ui_uses_standard_css_sizing_and_leaves_zoom_to_the_browser() -> None:
    script = _asset("enhancements.js")
    styles = _asset("styles.css") + _asset("enhancements.css")

    assert "ZOOM_LEVELS" not in script
    assert "zoomIndicator" not in script
    assert "event.preventDefault()" not in script
    assert "zoom:" not in styles
    assert ".zoom-indicator" not in styles
    assert "font-size: 16px;" in styles
    assert "width: min(860px, calc(100% - 40px));" in styles
    assert "height: 44px;" in styles
