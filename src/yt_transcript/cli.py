from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .errors import AppError
from .gemini import DEFAULT_GEMINI_MODEL, list_gemini_models
from .service import ExtractionOptions, extract_transcript
from .summary_languages import COMMON_SUMMARY_LANGUAGES, normalize_summary_language


def _summary_language_argument(value: str) -> str:
    try:
        return normalize_summary_language(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    default_gemini_model = os.getenv("GEMINI_MODEL", "").strip() or DEFAULT_GEMINI_MODEL
    parser = argparse.ArgumentParser(
        prog="yt-transcript",
        description="Extract original-language YouTube captions in multiple formats.",
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="YouTube URL or 11-character video ID",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for transcript and summary files",
    )
    parser.add_argument(
        "--format",
        choices=("md", "txt", "json", "srt", "vtt"),
        default="md",
        help="Transcript output format (default: md)",
    )
    parser.add_argument("--no-summary", action="store_true", help="Skip Gemini summarization")
    parser.add_argument(
        "--summary-lang",
        type=_summary_language_argument,
        default="auto",
        metavar="LANGUAGE",
        help=(
            "Summary language: auto uses the transcript's primary language; "
            f"common tags are {', '.join(item.code for item in COMMON_SUMMARY_LANGUAGES)}; "
            "other valid BCP 47 tags are accepted (default: auto)"
        ),
    )
    parser.add_argument(
        "--long-summary",
        choices=("skip", "truncate", "full"),
        default="skip",
        help=(
            "For captions over 50,000 characters: skip, summarize a prefix, "
            "or send the full transcript (default: skip)"
        ),
    )
    parser.add_argument(
        "--cookies-from-browser",
        choices=("chrome", "chromium", "edge", "firefox", "safari", "brave"),
        help="Browser cookies for unlisted or age-restricted videos",
    )
    parser.add_argument(
        "--gemini-model",
        default=default_gemini_model,
        help=f"Gemini model ID (default: {default_gemini_model})",
    )
    parser.add_argument(
        "--list-gemini-models",
        action="store_true",
        help="List Gemini models that support generateContent, then exit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_gemini_models:
        try:
            models = list_gemini_models(os.getenv("GEMINI_API_KEY", "").strip())
        except AppError as exc:
            _print_app_error(exc)
            return 1
        for model in models:
            print(model)
        return 0

    if not args.url:
        parser.error("url is required unless --list-gemini-models is used")

    options = ExtractionOptions(
        url=args.url,
        transcript_format=args.format,
        generate_summary=not args.no_summary,
        summary_language=args.summary_lang,
        long_summary_mode=args.long_summary,
        cookie_browser=args.cookies_from_browser,
        api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=args.gemini_model,
    )

    try:
        result = extract_transcript(
            options,
            progress=lambda percent, message: print(f"[{percent:3d}%] {message}", flush=True),
        )
    except AppError as exc:
        _print_app_error(exc)
        return 1

    output_dir = args.output_dir or Path.cwd()
    transcript_path = output_dir / result.transcript.filename
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(result.transcript.content, encoding="utf-8")
    print(f"Transcript saved to: {transcript_path}")

    if result.summary:
        summary_path = output_dir / result.summary.filename
        summary_path.write_text(result.summary.content, encoding="utf-8")
        print(f"Summary saved to: {summary_path}")
    if result.warning:
        print(f"Note: {result.warning}", file=sys.stderr)
    return 0


def _print_app_error(error: AppError) -> None:
    print(f"Error: {error.message}", file=sys.stderr)
    print(f"Hint: {error.hint}", file=sys.stderr)
