# Hosted deployment

This guide is for operators running the browser app as a service. Read [Security](../SECURITY.md) before exposing it publicly.

## Start the service

Install the Web dependencies and configure exact hosted-mode allowlists:

```bash
uv sync --extra web

export YT_TRANSCRIPT_MODE=hosted
export YT_TRANSCRIPT_ALLOWED_HOSTS="transcript.example.com"
export YT_TRANSCRIPT_ALLOWED_ORIGINS="https://transcript.example.com"

uv run --extra web uvicorn yt_transcript.web:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers 1
```

Terminate TLS at a trusted reverse proxy or hosting platform and forward requests to the application. `GET /healthz` returns a small process-health response suitable for a health check.

## Gemini configuration

Do not configure `GEMINI_API_KEY` or `GEMINI_MODEL` for a hosted Web service. Hosted mode intentionally ignores both variables; each user enters a key in the UI, and the built-in model is the initial selection.

`./scripts/run-app.sh` starts local mode. In that mode, loopback requests may use `GEMINI_API_KEY` when the UI field is empty, and `GEMINI_MODEL` becomes the initial model. A key entered in the UI takes precedence. The server reports only whether a fallback key is available; it never returns the key itself to the browser. Environment changes take effect after restarting the app.

`API_KEY` is not a recognized variable.

## Environment variables

| Variable | Default | Purpose |
|---|---:|---|
| `YT_TRANSCRIPT_MODE` | `local` | Select `local` or `hosted` capabilities and defaults |
| `YT_TRANSCRIPT_ALLOWED_HOSTS` | Local hosts | Comma-separated Host allowlist; required in hosted mode |
| `YT_TRANSCRIPT_ALLOWED_ORIGINS` | Derived locally | Comma-separated Origin allowlist for state-changing API calls |
| `YT_TRANSCRIPT_HOST` | Mode-dependent | Host used by `yt-transcript web`, `yt-transcript-web`, and `run-app.sh` |
| `PORT` | `8000` | Listening port and local allowed-origin port |
| `YT_TRANSCRIPT_OPEN_BROWSER` | `1` locally | Set to `0` to suppress automatic browser opening |
| `YT_TRANSCRIPT_JOB_TTL` | `600` | Pending summary lifetime in seconds |
| `YT_TRANSCRIPT_MAX_JOBS` | `64` | Maximum pending summary jobs per process |
| `YT_TRANSCRIPT_MAX_PENDING_CHARACTERS` | `5000000` | Total pending caption characters per process |
| `YT_TRANSCRIPT_MAX_WORKERS` | `4` | Maximum concurrent blocking extraction and Gemini operations |
| `GEMINI_API_KEY` | Unset | Local loopback fallback for summaries and model discovery; ignored in hosted mode |
| `GEMINI_MODEL` | `gemini-flash-lite-latest` | Initial local model; ignored in hosted mode |

Every configured numeric limit must be a positive integer. In hosted mode, omit wildcard hosts and use exact public origins.

## Process model and scaling

Use exactly one application worker with the current in-memory Short-term Job Store. Extraction and summarization are separate requests; multiple workers or replicas can route the second request to a process that does not hold the job.

Scaling out requires one of the following while continuing to exclude credentials from stored job data:

- a shared bounded TTL store; or
- verified session affinity for the full extraction-to-summary flow.

The `YT_TRANSCRIPT_MAX_WORKERS` setting controls concurrent blocking work inside the single application process; it does not create Uvicorn worker processes.

Hosted mode cannot use cookies from a visitor's browser. Restricted videos that require local browser cookies must be processed with a local instance or the CLI.

## Operational checklist

- Keep the Host and Origin allowlists exact.
- Configure the proxy not to log credential-bearing request headers.
- Apply request-rate limits and abuse controls at the edge.
- Monitor memory use because pending caption context is stored in process memory.
- Keep `yt-dlp` and other dependencies updated.
- Review the [security considerations](../SECURITY.md) before launch.
