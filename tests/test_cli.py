from pathlib import Path

import pytest

from yt_transcript import cli
from yt_transcript.cli import build_parser


def test_cli_accepts_gemini_model_override() -> None:
    args = build_parser().parse_args(["dQw4w9WgXcQ", "--gemini-model", "gemini-custom-model"])

    assert args.gemini_model == "gemini-custom-model"


def test_cli_reads_its_default_model_from_the_launch_environment(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_MODEL", "gemini-environment-model")

    args = build_parser().parse_args(["dQw4w9WgXcQ"])

    assert args.gemini_model == "gemini-environment-model"


def test_cli_supports_output_directory() -> None:
    args = build_parser().parse_args(["dQw4w9WgXcQ", "--output-dir", "output"])

    assert args.output_dir == Path("output")


def test_cli_supports_transcript_formats_and_long_summary_modes() -> None:
    args = build_parser().parse_args(["dQw4w9WgXcQ", "--format", "vtt", "--long-summary", "full"])

    assert args.format == "vtt"
    assert args.long_summary == "full"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("auto", "auto"),
        ("zh-hans", "zh-Hans"),
        ("PT-br", "pt-BR"),
        ("it", "it"),
    ],
)
def test_cli_accepts_common_and_custom_summary_languages(value: str, expected: str) -> None:
    args = build_parser().parse_args(["dQw4w9WgXcQ", "--summary-lang", value])

    assert args.summary_lang == expected


def test_cli_rejects_invalid_summary_language() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["dQw4w9WgXcQ", "--summary-lang", "custom"])


def test_cli_lists_generate_content_models_without_a_video_url(monkeypatch, capsys) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "environment-secret")
    observed = []
    monkeypatch.setattr(
        cli,
        "list_gemini_models",
        lambda key: observed.append(key) or ["gemini-flash-latest", "gemini-pro-latest"],
    )

    assert cli.main(["--list-gemini-models"]) == 0
    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["gemini-flash-latest", "gemini-pro-latest"]
    assert captured.err == ""
    assert observed == ["environment-secret"]


def test_cli_model_listing_reports_a_missing_api_key(monkeypatch, capsys) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert cli.main(["--list-gemini-models"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "No Gemini API key is configured" in captured.err


def test_cli_help_lists_all_extended_options() -> None:
    help_text = build_parser().format_help()

    assert "--gemini-model" in help_text
    assert "--list-gemini-models" in help_text
    assert "--output-dir" in help_text
    assert "--format" in help_text
    assert "--long-summary" in help_text
    assert "--cookies-from-browser" in help_text
    assert "--caption-lang" not in help_text
    assert "--no-timestamps" not in help_text
