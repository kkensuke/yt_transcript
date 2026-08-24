# YouTube Transcript

YouTube Transcript is a command-line tool and macOS desktop app that turns original-language YouTube captions into reusable Markdown, text, JSON, SRT, or VTT files, with optional Gemini summarization.

## Features

- Extract the original-language manual or auto-generated captions from a YouTube URL or 11-character video ID
- Create Markdown, plain text, JSON, SRT, or VTT from one structured transcript
- Include timestamps in every format, with clickable YouTube timestamps in Markdown
- Include source chapters reported by YouTube in Markdown, text, and JSON output
- Summarize in the transcript's primary language, one of 10 common languages, or another language identified by a BCP 47 tag with Gemini
- Ask before summarizing captions longer than 50,000 characters: summarize a segment-boundary prefix, send all captions, or keep only the transcript
- Load the currently available Gemini `generateContent` models in the CLI or desktop UI
- Select a Gemini Model ID from the CLI or desktop UI
- Save transcript and summary files together with `--output-dir`
- Use browser cookies for unlisted or age-restricted videos
- Preview either result, copy or save transcript and summary directly, or save both together from the desktop app
- Switch between Light and Dark in the app

## Requirements

- CLI or source-based desktop app: Python 3.11–3.13 and [uv](https://docs.astral.sh/uv/)
- Building the macOS app: macOS 11 or later
- Gemini summarization and model discovery: a Gemini API key; caption extraction works without one

```bash
git clone https://github.com/kkensuke/yt_transcript.git
cd yt_transcript
```

## CLI

A CLI-only environment does not install `pywebview`.

```bash
# Transcript and Gemini summary when GEMINI_API_KEY is available
export GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
uv run yt-transcript "https://www.youtube.com/watch?v=VIDEO_ID"

# Transcript only
uv run yt-transcript "VIDEO_ID" --no-summary

# Save a WebVTT transcript (timestamps are always included)
uv run yt-transcript "VIDEO_ID" --format vtt --no-summary

# For captions over 50,000 characters, send the full transcript to Gemini
uv run yt-transcript "VIDEO_ID" --long-summary full

# Use Chrome cookies for a restricted video
uv run yt-transcript "VIDEO_ID" --cookies-from-browser chrome

# Select a Gemini Model ID from the CLI
uv run yt-transcript "VIDEO_ID" --gemini-model "gemini-flash-latest"

# List Gemini models that can generate summaries (no video URL is required)
uv run yt-transcript --list-gemini-models

# Write the summary in French or another language identified by a BCP 47 tag
uv run yt-transcript "VIDEO_ID" --summary-lang fr

# Recommended when writing files to another directory
uv run yt-transcript "VIDEO_ID" --output-dir output/
```

### CLI options

| Option | Description |
|---|---|
| `url` | YouTube URL or 11-character video ID; omitted with `--list-gemini-models` |
| `--output-dir DIR` | Directory for transcript and summary files |
| `--format {md,txt,json,srt,vtt}` | Transcript format; defaults to `md` |
| `--no-summary` | Skip Gemini summarization |
| `--summary-lang LANGUAGE` | `auto` for the transcript's primary language, a common language tag, or another valid BCP 47 tag |
| `--long-summary {skip,truncate,full}` | Behavior above 50,000 caption characters; defaults to `skip` |
| `--cookies-from-browser BROWSER` | Use cookies from `chrome`, `chromium`, `edge`, `firefox`, `safari`, or `brave` |
| `--gemini-model MODEL_ID` | Gemini Model ID for summarization |
| `--list-gemini-models` | List models that support `generateContent`, one ID per line, then exit |

With `--output-dir output/`, the transcript is saved as `output/<VIDEO_ID>_transcript.<FORMAT>` and, when summarization succeeds, its Markdown summary is saved as `output/<VIDEO_ID>_summarized.md`.

Run `uv run yt-transcript --help` to see the complete CLI help.

The CLI attempts summarization by default. If `GEMINI_API_KEY` is missing or summarization fails, the transcript is still saved and the reason is shown as a warning. For captions above 50,000 characters, the non-interactive default is `--long-summary skip`; select `truncate` to use the largest complete-segment prefix within the limit or `full` to send every caption character in one request. The selected Gemini model can still reject a full request if it exceeds that model's context limit.

The Gemini Model ID is selected in this order:

1. `--gemini-model`
2. `GEMINI_MODEL`
3. The built-in default, `gemini-flash-lite-latest`

The API key cannot be passed as a command-line argument. Set `GEMINI_API_KEY` for CLI use so the key does not appear in the command history.

`--summary-lang auto` asks Gemini to write in the same primary language as the transcript. The shared common choices are English (`en`), Japanese (`ja`), Simplified Chinese (`zh-Hans`), Traditional Chinese (`zh-Hant`), Korean (`ko`), Spanish (`es`), French (`fr`), German (`de`), Brazilian Portuguese (`pt-BR`), and Hindi (`hi`). Other valid BCP 47 tags, such as `it`, `ar`, or `uk`, are also accepted.

## Desktop app

![YouTube Transcript desktop app](example.png)

### Run from source

```bash
./scripts/run-app.sh
```

The launcher syncs the `desktop` extra, starts the current code directly from `src/`, and opens it in a native desktop window.

Gemini summarization is enabled by default. Disable it in Settings to create only a transcript. To summarize, either enter an API key in Settings or define it before launching the app:

```bash
export GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
export GEMINI_MODEL="gemini-flash-latest"  # Optional
./scripts/run-app.sh
```

Settings shows whether the API key and model came from the environment or the app default, but it never reveals the environment API key. A key or Model ID entered in the UI overrides the environment for that run only and is never saved.

Select the transcript format and summary language in Settings. **Same as transcript** asks Gemini to use the captions' primary language. Ten common languages are available directly; select **Other…** to enter another BCP 47 language tag. Timestamps are always present, and Markdown timestamps open the video at that position. When YouTube reports source chapters, they are included without AI-generated chapter inference. The result toolbar groups Copy and Save actions with their transcript or summary target, so either artifact can be handled without changing the preview. Save both writes the transcript and Markdown summary after one folder selection; existing files require confirmation before replacement.

If the caption text exceeds 50,000 characters, the app shows the measured size before calling Gemini and offers three choices: summarize the first complete segments that fit within 50,000 characters, summarize all captions in one request, or keep only the transcript. The resulting summary records whether a prefix or the full over-limit source was used.

### Available Gemini models

Run `uv run yt-transcript --list-gemini-models` in the CLI or select **Load available models** in Settings to query the Gemini Models API. Both list only models that advertise support for `generateContent`. The CLI reads `GEMINI_API_KEY` and prints one Model ID per line. In the app, the current text field remains editable, so a Model ID can still be entered manually. If `GEMINI_API_KEY` is already configured, the app also attempts to load the list when the desktop bridge becomes ready.

### Appearance and zoom

When the app opens, it reads the current macOS appearance once and starts in the matching Light or Dark mode. While the app is open, use the **Light** and **Dark** controls in the header to switch manually. The manual choice is intentionally session-only: the next launch starts from the current macOS appearance again.

Use these keyboard shortcuts to change the UI scale:
- `Command` + `=`: zoom in
- `Command` + `-`: zoom out
- `Command` + `0`: reset to 100%

### Build the macOS `.app`

py2app cannot cross-compile, so build the app on macOS:

```bash
./scripts/build-macos-app.sh
open dist/YouTubeTranscript.app
```

The bundle is created at `dist/YouTubeTranscript.app`. It includes Python and its runtime dependencies, so users do not need to install Python or uv.

### Environment variables and the `.app`

When environment variables are set in a terminal and the app is opened from that same terminal, the app reads `GEMINI_API_KEY` and `GEMINI_MODEL`:

```bash
export GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
export GEMINI_MODEL="gemini-flash-latest"  # Optional
open dist/YouTubeTranscript.app
```

When the `.app` is opened directly from Finder or Launchpad, shell environment variables are normally not inherited. Enter `GEMINI_API_KEY` in Settings each time you launch the app. The key is not saved and is discarded when the app quits.

After changing an environment variable, quit any running instance completely before opening the app again from the same terminal.

### Distribution

An unsigned app triggers a macOS Gatekeeper warning. General distribution requires signing with a Developer ID certificate from the Apple Developer Program and notarization by Apple. See Apple's [Notarizing macOS software before distribution](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution).

## Project naming

The project uses the same base name consistently across GitHub, Python packaging, imports, and the CLI, using the separator conventional for each context:

- GitHub repository: `yt_transcript`
- Python distribution: `yt-transcript`
- Python package: `yt_transcript`
- CLI command: `yt-transcript`
- GUI entry point: `yt-transcript-app`
- macOS bundle: `YouTubeTranscript.app`

## Captions and browser cookies

Try caption extraction without cookies first. Use `--cookies-from-browser` in the CLI or **Browser cookies** in the desktop app only when a video requires a signed-in session, such as an age-restricted or unlisted video.

Caption cues such as `[音楽]`, `[拍手]`, and `♪` are preserved. The ingestion step normalizes whitespace, including unwanted spaces between Japanese characters, without deleting cue text.

## Development and verification

```bash
uv sync --extra dev
uv run --extra dev pytest
uv run --extra dev ruff check .
./scripts/run-app.sh --check
```

Automated tests do not contact YouTube. Results can vary with YouTube changes, region, rate limits, and login state, so test a public video with captions manually before release.

## Troubleshooting

### No captions are found

- Confirm that the video has manual or auto-generated captions
- Confirm that YouTube identifies an original-language caption track
- Update `yt-dlp`: `uv lock --upgrade-package yt-dlp && uv sync`

### `HTTP 429` appears

YouTube is temporarily rate-limiting caption requests. Wait and try again. If the problem persists, select cookies from a signed-in browser.

### Only Gemini summarization fails

- Check the API key, Model ID, and quota
- Use **Load available models** to confirm that the selected model is currently advertised for `generateContent`
- The transcript remains available to save or copy; review the warning and try summarization again

### The `.app` does not launch

Run the executable from a terminal to view its log:

```bash
./dist/YouTubeTranscript.app/Contents/MacOS/YouTubeTranscript
```

## Technical references

- [pywebview JavaScript–Python bridge](https://pywebview.flowrl.com/guide/interdomain.html)
- [pywebview freezing](https://pywebview.flowrl.com/guide/freezing.html)
- [py2app tutorial](https://py2app.readthedocs.io/en/latest/tutorial.html)
- [Gemini models API](https://ai.google.dev/api/models)

## License

This project is licensed under the [MIT License](LICENSE). Third-party dependencies remain under their respective licenses.
