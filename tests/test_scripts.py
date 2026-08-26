import subprocess
import sys
import tomllib
from pathlib import Path

from yt_transcript import __version__

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_CONFIG = PROJECT_ROOT / "pyproject.toml"
RUN_APP_SCRIPT = PROJECT_ROOT / "scripts" / "run-app.sh"
HOMEBREW_RENDERER = PROJECT_ROOT / "scripts" / "render_homebrew_formula.py"
LICENSE_FILE = PROJECT_ROOT / "LICENSE"


def test_run_app_script_has_valid_shell_syntax() -> None:
    subprocess.run(["sh", "-n", str(RUN_APP_SCRIPT)], check=True)


def test_run_app_script_launches_the_current_web_source() -> None:
    script = RUN_APP_SCRIPT.read_text(encoding="utf-8")

    assert "uv sync --no-install-project --extra web --inexact" in script
    assert 'export PYTHONPATH="$PROJECT_ROOT/src' in script
    assert "uv run --no-sync python -m yt_transcript.web" in script
    assert 'src" / "yt_transcript"' in script
    assert "import yt_transcript" in script
    assert "actual == expected" in script
    assert 'create_app(mode="local")' in script
    assert "uv run --no-editable" not in script
    assert "--reinstall-package" not in script
    assert '"${1:-}" = "--check"' in script


def test_web_dependency_is_optional_for_cli_users() -> None:
    project = tomllib.loads(PROJECT_CONFIG.read_text(encoding="utf-8"))["project"]

    assert project["version"] == __version__
    assert project["requires-python"] == ">=3.11,<3.15"
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]
    assert LICENSE_FILE.read_text(encoding="utf-8").startswith("MIT License\n")
    assert not any(dependency.startswith("fastapi") for dependency in project["dependencies"])
    assert any(
        dependency.startswith("fastapi") for dependency in project["optional-dependencies"]["web"]
    )
    assert "desktop" not in project["optional-dependencies"]


def test_project_entry_points_use_clean_python_package_name() -> None:
    config = tomllib.loads(PROJECT_CONFIG.read_text(encoding="utf-8"))

    scripts = config["project"]["scripts"]
    assert scripts["yt-transcript"] == "yt_transcript.cli:main"
    assert scripts["yt-transcript-web"] == "yt_transcript.web:main"
    assert "gui-scripts" not in config["project"]
    assert "yt_transcript.ui" in config["tool"]["setuptools"]["package-data"]


def test_readme_documents_cli_web_and_byok_configuration() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    contributing = (PROJECT_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    deployment = (PROJECT_ROOT / "docs" / "deployment.md").read_text(encoding="utf-8")
    architecture = (PROJECT_ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    security = (PROJECT_ROOT / "SECURITY.md").read_text(encoding="utf-8")

    assert "brew install kkensuke/tap/yt-transcript" in readme
    assert "yt-transcript web" in readme
    assert "yt-transcript web --no-open" in readme
    assert "./scripts/run-app.sh" in readme
    assert "./scripts/run-app.sh --check" in contributing
    assert "--gemini-model" in readme
    assert "--output-dir" in readme
    assert "GEMINI_MODEL" in readme
    assert "Load available models" in readme
    assert "YT_TRANSCRIPT_MODE=hosted" in deployment
    assert "X-Gemini-Api-Key" in architecture
    assert "Short-term Job Store" in architecture
    assert "one application worker" in (deployment + security).lower()
    assert "open dist/YouTubeTranscript.app" not in readme
    assert "pywebview" not in readme.lower()


def test_homebrew_formula_is_rendered_from_runtime_and_web_dependencies(tmp_path) -> None:
    output = tmp_path / "Formula" / "yt-transcript.rb"
    subprocess.run(
        [
            sys.executable,
            str(HOMEBREW_RENDERER),
            "--version",
            __version__,
            "--source-sha256",
            "a" * 64,
            "--output",
            str(output),
        ],
        check=True,
    )

    formula = output.read_text(encoding="utf-8")
    assert "class YtTranscript < Formula" in formula
    assert f"refs/tags/v{__version__}.tar.gz" in formula
    assert 'depends_on "python@3.14"' in formula
    assert 'depends_on "pydantic" => :no_linkage' in formula
    assert 'resource "fastapi"' in formula
    assert 'resource "uvicorn"' in formula
    assert 'resource "yt-dlp"' in formula
    assert 'resource "pytest"' not in formula
    assert 'resource "ruff"' not in formula
    assert 'resource "pydantic-core"' not in formula
    assert "yt-transcript web --help" in formula
    assert "/healthz" in formula
