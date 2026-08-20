from yt_dlp_transcript.cli import build_parser


def test_cli_accepts_gemini_model_override() -> None:
    args = build_parser().parse_args(
        ["dQw4w9WgXcQ", "--gemini-model", "gemini-custom-model"]
    )

    assert args.gemini_model == "gemini-custom-model"


def test_cli_help_lists_all_extended_options() -> None:
    help_text = build_parser().format_help()

    assert "--gemini-model" in help_text
    assert "--caption-lang" in help_text
    assert "--cookies-from-browser" in help_text
