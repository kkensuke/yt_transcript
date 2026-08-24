import re
import sys
from types import SimpleNamespace

from yt_transcript import desktop
from yt_transcript.desktop import DesktopApi, load_ui_html
from yt_transcript.models import (
    CaptionTrack,
    OutputArtifact,
    TranscriptDocument,
    TranscriptSegment,
    VideoMetadata,
)
from yt_transcript.service import ExtractionResult


def test_ui_assets_are_inlined_without_external_dependencies() -> None:
    html = load_ui_html()
    assert "/*__APP_STYLES__*/" not in html
    assert "/*__APP_SCRIPT__*/" not in html
    assert "window.App" in html
    assert "https://cdn" not in html
    assert "<style>" in html


def test_ui_explains_each_setting_before_its_control() -> None:
    html = load_ui_html()
    label_and_control_pairs = [
        ('for="videoUrl">YouTube video</label>', 'id="videoUrl"'),
        ('for="summaryLanguage">Summary language</label>', 'id="summaryLanguage"'),
        ('for="geminiModel">Gemini Model ID</label>', 'id="geminiModel"'),
        ('id="apiKeyLabel"', 'id="apiKey"'),
        ('for="transcriptFormat">Transcript format</label>', 'id="transcriptFormat"'),
        ('for="cookieBrowser">Browser for cookies</label>', 'id="cookieBrowser"'),
    ]
    for label, control in label_and_control_pairs:
        assert html.index(label) < html.index(control)
    assert "GEMINI_API_KEY" in html
    assert "Using environment variable ${apiKeyVariable}" in html
    assert "prefers-color-scheme: dark" in html
    assert "linear-gradient" not in html


def test_ui_labels_and_descriptions_reference_existing_controls() -> None:
    html = load_ui_html()
    ids = re.findall(r'\bid="([^"]+)"', html)

    assert len(ids) == len(set(ids))
    for target in re.findall(r'<label[^>]+for="([^"]+)"', html):
        assert target in ids
    for references in re.findall(r'aria-describedby="([^"]+)"', html):
        assert set(references.split()).issubset(ids)


def test_ui_uses_separate_execution_and_settings_tabs_without_internal_result_scroll() -> None:
    html = load_ui_html()

    execute_panel = html.index('id="executeFormPanel"')
    settings_panel = html.index('id="settingsFormPanel"')

    assert 'data-form-tab="execute"' in html
    assert 'data-form-tab="settings"' in html
    assert execute_panel < html.index('id="videoUrl"') < settings_panel
    assert execute_panel < html.index('id="runSummary"') < settings_panel
    assert execute_panel < html.index('id="extractButton"') < settings_panel
    assert settings_panel < html.index("Output")
    assert settings_panel < html.index("Advanced access settings")
    assert 'id="pasteButton"' not in html
    assert "navigator.clipboard.readText" not in html
    assert "max-height: 590px" not in html
    assert "overflow: visible" in html


def test_ui_has_required_timestamps_formats_long_summary_choices_and_save_all() -> None:
    html = load_ui_html()

    assert 'id="timestampsToggle"' not in html
    assert 'id="captionLanguage"' not in html
    assert "Timestamps are always included" in html
    for output_format in ("md", "txt", "json", "srt", "vtt"):
        assert f'<option value="{output_format}">' in html
    assert 'data-summary-mode="truncate"' in html
    assert 'data-summary-mode="full"' in html
    assert 'data-summary-mode="skip"' in html
    assert "Summarize all captions" in html
    assert 'id="saveAllButton"' in html


def test_ui_enables_gemini_summary_by_default() -> None:
    html = load_ui_html()
    summary_toggle = re.search(r'<input\s+id="summaryToggle"(?P<attrs>[^>]*)>', html, re.S)
    summary_options = re.search(r'<section\s+id="summaryOptions"(?P<attrs>[^>]*)>', html, re.S)

    assert summary_toggle is not None
    assert "checked" in summary_toggle.group("attrs")
    assert 'aria-expanded="true"' in summary_toggle.group("attrs")
    assert summary_options is not None
    assert 'class="summary-options"' in summary_options.group("attrs")
    assert 'aria-hidden="false"' in summary_options.group("attrs")


def test_ui_supports_zoom_shortcuts_and_model_discovery() -> None:
    html = load_ui_html()

    assert 'event.key === "=" || event.key === "+"' in html
    assert 'event.key === "-"' in html
    assert 'event.key === "0"' in html
    assert "Load available models" in html
    assert "geminiModelOptions" in html
    assert "list_gemini_models" in html


def test_ui_starts_from_system_theme_and_offers_only_light_dark_controls() -> None:
    html = load_ui_html()

    assert 'window.matchMedia("(prefers-color-scheme: dark)").matches' in html
    assert "data-theme-choice" in html
    assert '["light", "Light"]' in html
    assert '["dark", "Dark"]' in html
    assert "document.documentElement.dataset.theme = currentTheme" in html
    assert "localStorage" not in html
    assert ':root[data-theme="light"]' in html
    assert ':root[data-theme="dark"]' in html


def test_app_info_names_environment_sources_without_exposing_api_key(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")

    info = DesktopApi().get_app_info()

    assert info["api_key_configured"] is True
    assert info["api_key_source"] == "environment"
    assert info["api_key_environment_variable"] == "GEMINI_API_KEY"
    assert info["gemini_model"] == "gemini-test-model"
    assert info["gemini_model_source"] == "environment"
    assert info["gemini_model_environment_variable"] == "GEMINI_MODEL"
    assert "super-secret-key" not in repr(info)


def test_app_info_identifies_unconfigured_defaults(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    info = DesktopApi().get_app_info()

    assert info["api_key_configured"] is False
    assert info["api_key_source"] == "not_configured"
    assert info["gemini_model_source"] == "default"
    assert info["gemini_model"]


def test_desktop_lists_models_without_exposing_environment_key(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "environment-secret")
    observed = []
    monkeypatch.setattr(
        desktop,
        "fetch_gemini_models",
        lambda key: observed.append(key) or ["gemini-flash-latest"],
    )

    response = DesktopApi().list_gemini_models()

    assert response == {"ok": True, "models": ["gemini-flash-latest"]}
    assert observed == ["environment-secret"]
    assert "environment-secret" not in repr(response)


def test_save_all_writes_both_artifacts_and_confirms_overwrite(monkeypatch, tmp_path) -> None:
    metadata = VideoMetadata("dQw4w9WgXcQ", "Test", 10, "", "en")
    document = TranscriptDocument(
        metadata,
        CaptionTrack((), "en", "manual"),
        (TranscriptSegment(0.0, 1.0, "Hello."),),
    )
    transcript = OutputArtifact(
        "transcript",
        "txt",
        "dQw4w9WgXcQ_transcript.txt",
        "Transcript\n",
    )
    summary = OutputArtifact(
        "summary",
        "md",
        "dQw4w9WgXcQ_summarized.md",
        "# Summary\n",
    )
    api = DesktopApi()
    api._latest = ExtractionResult(
        document=document,
        transcript=transcript,
        summary=summary,
        summary_limit=None,
        warning=None,
        character_count=6,
        word_count=1,
    )
    api.bind_window(SimpleNamespace(create_file_dialog=lambda *_args, **_kwargs: [str(tmp_path)]))
    monkeypatch.setitem(
        sys.modules,
        "webview",
        SimpleNamespace(FileDialog=SimpleNamespace(FOLDER="folder")),
    )

    first = api.save_all_results()
    conflict = api.save_all_results()
    overwrite = api.save_all_results(overwrite=True)

    assert first["ok"] is True
    assert len(first["paths"]) == 2
    assert (tmp_path / transcript.filename).read_text(encoding="utf-8") == transcript.content
    assert (tmp_path / summary.filename).read_text(encoding="utf-8") == summary.content
    assert conflict["needs_overwrite_confirmation"] is True
    assert overwrite["ok"] is True
