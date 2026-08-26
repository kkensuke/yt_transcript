# Contributing

## Development setup

Install the Web and development dependencies:

```bash
uv sync --extra web --extra dev
```

Run the local browser app from the current source tree:

```bash
./scripts/run-app.sh
# Equivalent after dependencies are installed:
uv run yt-transcript web
```

Set `YT_TRANSCRIPT_OPEN_BROWSER=0` when you want to start the server without opening a browser.

## Verification

Run the automated and static checks before submitting a change:

```bash
uv run --extra web --extra dev pytest
uv run --extra web --extra dev ruff check .
uv run --extra web --extra dev ruff format --check .
node --check src/yt_transcript/ui/app.js
node --check src/yt_transcript/ui/enhancements.js
node --check src/yt_transcript/ui/theme-control.js
./scripts/run-app.sh --check
```

Automated tests mock YouTube and Gemini. Do not put real credentials in tests, fixtures, screenshots, logs, or commits.

Before a release, manually test a public captioned video because YouTube behavior can vary by region, rate limit, and upstream changes. Check both transcript-only and bring-your-own-key summary flows when possible.

## Project layout

```text
src/yt_transcript/
├── web.py              # FastAPI UI and HTTP boundary
├── web_state.py        # Bounded, expiring summary jobs (no credentials)
├── cli.py              # CLI boundary and CLI-only environment lookup
├── service.py          # Shared extraction and summarization workflow
├── youtube.py          # YouTube metadata and caption ingestion
├── gemini.py           # Gemini HTTP client
├── renderers.py        # Transcript formats
└── ui/                 # Browser HTML, CSS, and JavaScript
```

Additional repository paths:

- `tests/` contains unit and Web-boundary tests.
- `scripts/run-app.sh` prepares and starts the source Web application.
- `scripts/render_homebrew_formula.py` renders locked Python resources for the Homebrew Tap.
- `.github/workflows/release.yml` publishes tagged releases and updates the Tap formula.
- `docs/architecture.md` documents internal request and credential boundaries.
- `docs/deployment.md` documents hosted operation.

## Naming conventions

- GitHub repository: `yt_transcript`
- Python distribution: `yt-transcript`
- Python package: `yt_transcript`
- CLI command: `yt-transcript`
- Browser app command: `yt-transcript web`
- Direct browser server entry point: `yt-transcript-web` (kept for compatibility and hosting)

## Releases

The project version in `pyproject.toml` and `src/yt_transcript/__init__.py` must match. Stable `vMAJOR.MINOR.PATCH` tags run the release workflow, create GitHub artifacts, and update `kkensuke/homebrew-tap`. See [Homebrew releases](docs/homebrew.md) for setup and verification.

## Change guidelines

- Keep changes scoped and add or update tests for behavior changes.
- Preserve the separation between transcript extraction and Gemini credential handling.
- Do not add a server-side Gemini key path to the Web application.
- Keep browser assets self-contained and same-origin unless the security model and Content Security Policy are deliberately updated.
- Update README user guidance or the appropriate architecture, deployment, security, or contributor document when behavior changes.
