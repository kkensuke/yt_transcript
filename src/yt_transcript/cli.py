from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .errors import AppError
from .gemini import DEFAULT_GEMINI_MODEL
from .service import ExtractionOptions, extract_transcript


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yt-transcript",
        description="Extract YouTube captions as Markdown.",
    )
    parser.add_argument("url", help="YouTube URL or 11-character video ID")
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("-o", "--output", type=Path, help="Transcript output path")
    output_group.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for <VIDEO_ID>_transcript.md and <VIDEO_ID>_summarized.md",
    )
    parser.add_argument("--no-timestamps", action="store_true", help="Omit timestamps")
    parser.add_argument("--no-summary", action="store_true", help="Skip Gemini summarization")
    parser.add_argument(
        "--summary-lang",
        choices=("auto", "en", "ja"),
        default="auto",
        help="Summary language (default: auto)",
    )
    parser.add_argument(
        "--caption-lang",
        choices=("auto", "en", "ja"),
        default="auto",
        help="Preferred caption language (default: auto)",
    )
    parser.add_argument(
        "--cookies-from-browser",
        choices=("chrome", "chromium", "edge", "firefox", "safari", "brave"),
        help="Browser cookies for unlisted or age-restricted videos",
    )
    parser.add_argument(
        "--gemini-model",
        default=DEFAULT_GEMINI_MODEL,
        help=f"Gemini model ID (default: {DEFAULT_GEMINI_MODEL})",
    )
    return parser


def _transcript_output_path(args: argparse.Namespace, video_id: str) -> Path:
    if args.output:
        return args.output
    output_dir = args.output_dir or Path.cwd()
    return output_dir / f"{video_id}_transcript.md"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    options = ExtractionOptions(
        url=args.url,
        include_timestamps=not args.no_timestamps,
        generate_summary=not args.no_summary,
        summary_language=args.summary_lang,
        caption_language=args.caption_lang,
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
        print(f"Error: {exc.message}", file=sys.stderr)
        print(f"Hint: {exc.hint}", file=sys.stderr)
        return 1

    transcript_path = _transcript_output_path(args, result.video_id)
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(result.transcript, encoding="utf-8")
    print(f"Transcript saved to: {transcript_path}")

    if result.summary:
        summary_path = transcript_path.with_name(f"{result.video_id}_summarized.md")
        summary_path.write_text(result.summary, encoding="utf-8")
        print(f"Summary saved to: {summary_path}")
    if result.warning:
        print(f"Note: {result.warning}", file=sys.stderr)
    return 0
