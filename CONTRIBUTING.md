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
uv run yttext web
```

Set `YTTEXT_OPEN_BROWSER=0` when you want to start the server without opening a browser.

## Verification

Run the automated and static checks before submitting a change:

```bash
uv run --extra web --extra dev pytest
uv run --extra web --extra dev ruff check .
uv run --extra web --extra dev ruff format --check .
node --check src/yttext/ui/app.js
node --check src/yttext/ui/enhancements.js
node --check src/yttext/ui/theme-control.js
./scripts/run-app.sh --check
```

Automated tests mock YouTube and Gemini. Do not put real credentials in tests, fixtures, screenshots, logs, or commits.

Before a release, manually test a public captioned video because YouTube behavior can vary by region, rate limit, and upstream changes. Check both transcript-only and bring-your-own-key summary flows when possible.

## Project layout

```text
src/yttext/
├── web.py              # FastAPI UI/HTTP boundary and local-loopback Gemini environment fallback
├── web_state.py        # Bounded, expiring summary jobs (no credentials)
├── cli.py              # CLI boundary and CLI Gemini environment configuration
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
- `.github/workflows/release.yml` publishes tagged PyPI and GitHub releases and updates the Tap formula.
- `docs/architecture.md` documents internal request and credential boundaries.
- `docs/deployment.md` documents hosted operation.

## Naming conventions

- GitHub repository: `yttext`
- Python distribution: `yttext`
- Python package: `yttext`
- CLI command: `yttext`
- Browser app command: `yttext web`

## Releases

The project version in `pyproject.toml` and `src/yttext/__init__.py` must match. Stable `vMAJOR.MINOR.PATCH` tags run the release workflow, publish to PyPI, create a GitHub Release, and update `kkensuke/homebrew-tap`. See [PyPI releases](docs/pypi.md) and [Homebrew releases](docs/homebrew.md) for setup and verification.

## Change guidelines

- Keep changes scoped and add or update tests for behavior changes.
- Preserve the separation between transcript extraction and Gemini credential handling.
- Do not add a server-side Gemini key path for hosted or non-loopback Web requests. Preserve the existing local-loopback-only environment fallback boundary.
- Keep browser assets self-contained and same-origin unless the security model and Content Security Policy are deliberately updated.
- Update README user guidance or the appropriate architecture, deployment, security, or contributor document when behavior changes.
