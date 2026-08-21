from pathlib import Path

from yt_transcript.cli import _transcript_output_path, build_parser


def test_cli_accepts_gemini_model_override() -> None:
    args = build_parser().parse_args(
        ["dQw4w9WgXcQ", "--gemini-model", "gemini-custom-model"]
    )

    assert args.gemini_model == "gemini-custom-model"


def test_cli_supports_output_directory() -> None:
    args = build_parser().parse_args(["dQw4w9WgXcQ", "--output-dir", "output"])

    assert args.output_dir == Path("output")
    assert _transcript_output_path(args, "dQw4w9WgXcQ") == Path(
        "output/dQw4w9WgXcQ_transcript.md"
    )


def test_cli_help_lists_all_extended_options() -> None:
    help_text = build_parser().format_help()

    assert "--gemini-model" in help_text
    assert "--output-dir" in help_text
    assert "--output " not in help_text
    assert "--caption-lang" in help_text
    assert "--cookies-from-browser" in help_text
