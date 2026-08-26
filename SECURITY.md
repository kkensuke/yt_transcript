# Security

## Reporting a vulnerability

Do not open a public issue containing an API key, exploit details, or other sensitive data.

Use GitHub's private vulnerability-reporting channel for this repository when it is available. If no private channel is shown, open a minimal issue asking the maintainers for a private contact method without including sensitive details.

## Credential model

The hosted browser app uses a bring-your-own-key model. A local loopback session may instead use a Gemini key inherited by the server process.

- Caption extraction does not require or accept a Gemini key.
- Summary and model-discovery requests normally send the user's key to the FastAPI backend in `X-Gemini-Api-Key`.
- In local mode only, a loopback request without that header may use `GEMINI_API_KEY` from the server environment. An explicitly supplied header takes precedence.
- Hosted and non-loopback requests always ignore `GEMINI_API_KEY` and `GEMINI_MODEL`.
- The backend necessarily receives the key transiently and forwards it to Google in `X-Goog-Api-Key`.
- The application does not intentionally log, persist, place in a URL, return, or add the key to a summary job.
- The browser receives only a Boolean indicating whether the local fallback exists. It does not use local storage, session storage, or cookies for an entered key and clears the field after sending a summary request or leaving the page.

This is not end-to-end credential isolation between the browser and Google: the backend and its TLS terminator are part of the trust boundary.

## Built-in Web protections

- API endpoints that accept structured request bodies use strict schemas that reject unexpected fields.
- State-changing API requests require JSON and enforce configured Origin checks.
- Trusted Host middleware restricts accepted Host headers.
- Request bodies are capped at 64 KiB.
- API responses use `Cache-Control: no-store`.
- Validation responses do not reflect submitted values.
- A restrictive Content Security Policy, frame restrictions, referrer policy, MIME protections, and browser permissions policy are sent with responses.
- The pending summary store is bounded by lifetime, job count, and total caption characters and never accepts credentials.
- Concurrent blocking work is bounded inside the process.
- Environment-key fallback requires both local mode and a loopback network peer.

## Public deployment checklist

- Terminate TLS at a trusted proxy or hosting platform.
- Ensure the proxy, platform, application firewall, and observability tools do not log `X-Gemini-Api-Key` or `X-Goog-Api-Key` values.
- Leave `GEMINI_API_KEY` and `GEMINI_MODEL` unset; hosted mode ignores them as a defense in depth.
- Use exact Host and Origin allowlists; do not deploy with wildcard hosts.
- Apply per-client rate limits and abuse controls at the edge. The in-process semaphore and job bounds are not a per-user quota system.
- Run one application worker until the Short-term Job Store is replaced with a shared bounded TTL store or verified session affinity.
- Keep dependencies patched and review upstream `yt-dlp`, FastAPI, Starlette, and Uvicorn advisories.

See [Hosted deployment](docs/deployment.md) for configuration details.

## Residual risks

- A user's key is visible to that user in browser developer tools and may be readable by a compromised browser or extension.
- A compromised server, TLS terminator, dependency, or host can observe transient credentials and transcript content.
- Edge or proxy logging can defeat the application's no-persistence policy if headers are not excluded.
- While local fallback is enabled, another process on the same computer can submit loopback requests that consume the configured key's quota, even though it cannot retrieve the key from the API.
- Users should configure appropriate Gemini quotas and key restrictions and revoke a key they suspect has been exposed.
