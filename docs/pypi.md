# PyPI releases

The PyPI distribution, Python package, import name, and command are all named `yttext`:

```text
PyPI distribution  yttext
Python package     yttext
Python import      yttext
CLI command        yttext
```

The release workflow publishes a wheel and source distribution to PyPI with OpenID Connect (OIDC). It does not store a long-lived PyPI API token in GitHub.

## One-time Trusted Publisher setup

Complete these steps before pushing the first `yttext` release tag.

### 1. Prepare the accounts

Create a [PyPI account](https://pypi.org/account/register/) if needed, verify its email address, and enable two-factor authentication. The GitHub repository must already be available as `kkensuke/yttext`.

### 2. Create the GitHub environment

In `kkensuke/yttext`, open **Settings → Environments**, create an environment named `pypi`, and add any desired deployment protection rules. The workflow gives OIDC permission only to the dedicated PyPI publishing job that uses this environment.

Do not add a `PYPI_TOKEN` secret. Trusted Publishing provides a short-lived credential for each release.

### 3. Register a pending publisher on PyPI

Sign in to PyPI, open **Your account → Publishing**, and add a pending GitHub publisher with these exact values:

| Field | Value |
|---|---|
| PyPI project name | `yttext` |
| GitHub owner | `kkensuke` |
| GitHub repository | `yttext` |
| Workflow filename | `release.yml` |
| Environment name | `pypi` |

A pending publisher creates the PyPI project during the first successful upload and then becomes a normal publisher. It does not reserve the project name before that upload, so publish the first release soon after registering it.

See the PyPI guides for [creating a project with a Trusted Publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/) and [publishing with a Trusted Publisher](https://docs.pypi.org/trusted-publishers/using-a-publisher/).

## Publishing a release

The version in `pyproject.toml`, `src/yttext/__init__.py`, and `uv.lock` must match. Run the local checks, merge the release commit to `main`, and push a signed version tag as described in [Homebrew releases](homebrew.md#publishing-a-release).

For the first renamed release, the project is prepared as version `0.5.0`:

```bash
VERSION=0.5.0
git tag -s "v${VERSION}" -m "yttext ${VERSION}"
git tag -v "v${VERSION}"
git push origin "v${VERSION}"
```

The tag starts three ordered jobs:

1. Verify the tag and version, run lint and tests, and build the wheel and source distribution without publishing credentials.
2. Download those exact build artifacts and publish them to PyPI from the isolated `pypi` environment with OIDC and signed attestations.
3. Create the GitHub Release and update `Formula/yttext.rb` in `kkensuke/homebrew-tap`.

If the PyPI job succeeds but the later GitHub/Homebrew job fails, use **Re-run failed jobs**. Do not rerun every job, move the tag, or reuse the version for different files. PyPI release files are immutable.

## Verifying the release

Confirm that the release page and both distributions exist at [pypi.org/project/yttext](https://pypi.org/project/yttext/), then test in isolated environments:

```bash
uvx --refresh-package yttext yttext --version
uvx yttext "YOUTUBE_URL" --no-summary

uv tool install yttext
yttext --version

pipx install yttext
yttext --version
```

The CLI is the default lightweight installation. Include the `web` extra for the browser app:

```bash
uvx --from 'yttext[web]' yttext web
# or
pipx install 'yttext[web]'
yttext web
```

The package can also be imported inside a Python environment:

```python
import yttext

print(yttext.__version__)
```

## Troubleshooting

### Trusted Publisher authentication fails

Check every publisher field for an exact match. In particular, the repository must be `yttext`, the workflow must be `release.yml`, and both the GitHub job and PyPI publisher must name the `pypi` environment.

### The project name becomes unavailable

The pending publisher does not reserve `yttext`. If another account publishes that name first, choose a new name and update the package metadata, repository, workflow, documentation, and publisher together before tagging.

### A release file already exists

Never rebuild different content under the same version. If the original PyPI job succeeded, rerun only the failed downstream job. If an upload partially failed, inspect the PyPI release before retrying and keep the original tag and artifacts unchanged.
