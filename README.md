# YouTube Transcript

YouTube Transcript provides a browser app and CLI that turn original-language YouTube captions into reusable Markdown, text, JSON, SRT, or VTT files. Caption extraction works without an API key; Gemini summaries use a key supplied by the person making the request.

## Features

- Extract manual or auto-generated original-language captions from a YouTube URL or 11-character video ID
- Include timestamps in every format and source chapters in Markdown, text, and JSON
- Create a Gemini summary in the transcript language or another BCP 47 language
- Ask what to do before sending captions longer than 50,000 characters
- Preview, copy, and download transcript and summary files in the browser
- Use local browser cookies for restricted videos when running on the same computer
- Keep the CLI for scripts and batch-friendly file output

## Requirements and installation

- Python 3.11–3.13
- [uv](https://docs.astral.sh/uv/)
- A personal [Gemini API key](https://aistudio.google.com/api-keys) for summaries and model discovery

```bash
git clone https://github.com/kkensuke/yt_transcript.git
cd yt_transcript
```

## Browser app

Start the local browser app:

```bash
./scripts/run-app.sh
```

The launcher installs the Web dependencies, starts the app on `127.0.0.1:8000`, and opens the system browser.

Paste a YouTube URL or video ID, adjust the transcript and summary settings if needed, and run the extraction. Completed transcripts and summaries can be previewed, copied, or downloaded from the browser.

### Gemini API key behavior

The key is needed only for Gemini summaries and model discovery. The browser sends it to the app for that operation, and the app forwards it to Google without placing it in a URL or saving it. The summary flow clears the input after sending it; clearing, reloading, or closing the tab also removes it.

The Web app intentionally ignores `GEMINI_API_KEY` and `GEMINI_MODEL`, including when started with `./scripts/run-app.sh`. Enter the key in the UI. Environment-based Gemini configuration is available only in the CLI.

Local mode can use cookies from a supported browser profile for videos that require sign-in. Try without cookies first. A hosted instance cannot access a visitor's browser profile.

The Web UI leaves zoom controls to the browser. For self-hosting, see [Hosted deployment](docs/deployment.md).

## CLI

The CLI reads `GEMINI_API_KEY` and optional `GEMINI_MODEL` from its environment. The API key cannot be passed as a command-line argument.

```bash
# Transcript and summary
export GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
uv run yt-transcript "https://www.youtube.com/watch?v=VIDEO_ID"

# Transcript only
uv run yt-transcript "VIDEO_ID" --no-summary

# WebVTT transcript
uv run yt-transcript "VIDEO_ID" --format vtt --no-summary

# Use local Chrome cookies for a restricted video
uv run yt-transcript "VIDEO_ID" --cookies-from-browser chrome

# Select a model and summary language
uv run yt-transcript "VIDEO_ID" \
  --gemini-model "gemini-flash-latest" \
  --summary-lang fr

# List models available to the environment key
uv run yt-transcript --list-gemini-models

# Write results to another directory
uv run yt-transcript "VIDEO_ID" --output-dir output/
```

### CLI options

| Option | Description |
|---|---|
| `url` | YouTube URL or 11-character video ID; omitted with `--list-gemini-models` |
| `--output-dir DIR` | Directory for transcript and summary files |
| `--format {md,txt,json,srt,vtt}` | Transcript format; defaults to `md` |
| `--no-summary` | Skip Gemini summarization |
| `--summary-lang LANGUAGE` | `auto` or a BCP 47 tag such as `en`, `ja`, `zh-Hans`, `pt-BR`, or `it` |
| `--long-summary {skip,truncate,full}` | Above 50,000 characters, skip, summarize a prefix, or send the full transcript |
| `--cookies-from-browser BROWSER` | Use local `chrome`, `chromium`, `edge`, `firefox`, `safari`, or `brave` cookies |
| `--gemini-model MODEL_ID` | Select the Gemini model |
| `--list-gemini-models` | List models supporting `generateContent` |

The CLI selects the model in this order: `--gemini-model`, `GEMINI_MODEL`, then the built-in `gemini-flash-lite-latest`. If its key is missing or summarization fails, the transcript is still written and a warning is shown.

## Troubleshooting

### No captions are found

- Confirm that the video has manual or auto-generated captions.
- Confirm that YouTube exposes an original-language caption track.
- Update `yt-dlp`: `uv lock --upgrade-package yt-dlp && uv sync`.

### `HTTP 429` appears

YouTube is temporarily rate-limiting requests. Wait and retry. Local users can try a signed-in browser profile; hosted mode cannot access it.

### Only Gemini summarization fails

- Re-enter the API key; it is cleared after each summary request.
- Check the selected model, quota, and key restrictions.
- Use **Load available models** with the same key.
- The transcript remains downloadable. A failed short-term job can be retried until it expires.

## Further documentation

- [Architecture](docs/architecture.md) — request flow, internal HTTP boundary, and short-term job store
- [Hosted deployment](docs/deployment.md) — server setup, environment variables, and process model
- [Security](SECURITY.md) — credential handling, deployment checklist, and vulnerability reporting
- [Contributing](CONTRIBUTING.md) — development setup, verification, and project structure

## License

This project is licensed under the [MIT License](LICENSE). Third-party dependencies retain their own licenses.
