import runpy
import subprocess
import tomllib
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_CONFIG = PROJECT_ROOT / "pyproject.toml"
RUN_APP_SCRIPT = PROJECT_ROOT / "scripts" / "run-app.sh"
BUILD_APP_SCRIPT = PROJECT_ROOT / "scripts" / "build-macos-app.sh"
MACOS_SETUP = PROJECT_ROOT / "packaging" / "macos" / "setup.py"
PY2APP_COMPAT = PROJECT_ROOT / "packaging" / "macos" / "py2app_compat.py"
LICENSE_FILE = PROJECT_ROOT / "LICENSE"


def test_run_app_script_has_valid_shell_syntax() -> None:
    subprocess.run(["sh", "-n", str(RUN_APP_SCRIPT)], check=True)


def test_run_app_script_launches_the_current_source_without_editable_install() -> None:
    script = RUN_APP_SCRIPT.read_text(encoding="utf-8")

    assert "uv sync --no-install-project --extra desktop --inexact" in script
    assert 'export PYTHONPATH="$PROJECT_ROOT/src' in script
    assert 'uv run --no-sync python "$PROJECT_ROOT/YouTubeTranscript.py"' in script
    assert "actual == expected" in script
    assert "uv run --no-editable" not in script
    assert "--reinstall-package" not in script
    assert '"${1:-}" = "--check"' in script


def test_desktop_dependency_is_optional_for_cli_users() -> None:
    project = tomllib.loads(PROJECT_CONFIG.read_text(encoding="utf-8"))["project"]

    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]
    assert LICENSE_FILE.read_text(encoding="utf-8").startswith("MIT License\n")
    assert not any(dependency.startswith("pywebview") for dependency in project["dependencies"])
    assert any(
        dependency.startswith("pywebview")
        for dependency in project["optional-dependencies"]["desktop"]
    )


def test_readme_documents_cli_and_desktop_configuration() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    assert "./scripts/run-app.sh" in readme
    assert "./scripts/run-app.sh --check" in readme
    assert "--gemini-model" in readme
    assert "GEMINI_MODEL" in readme
    assert "open dist/YouTubeTranscript.app" in readme
    assert "Finder" in readme
    assert "each time you launch the app" in readme


def test_build_app_script_has_valid_shell_syntax_and_expected_bundle_path() -> None:
    subprocess.run(["sh", "-n", str(BUILD_APP_SCRIPT)], check=True)

    script = BUILD_APP_SCRIPT.read_text(encoding="utf-8")
    assert 'APP_PATH="$PROJECT_ROOT/dist/YouTubeTranscript.app"' in script
    assert 'LEGACY_APP_PATH="$PROJECT_ROOT/dist/YouTube Transcript.app"' in script
    assert 'rm -rf "$PROJECT_ROOT/build" "$APP_PATH" "$LEGACY_APP_PATH"' in script
    assert '--with "$PROJECT_ROOT[desktop]"' in script


def test_macos_bundle_keeps_filename_and_display_name_distinct() -> None:
    setup_text = MACOS_SETUP.read_text(encoding="utf-8")

    assert '"CFBundleName": "YouTubeTranscript"' in setup_text
    assert '"CFBundleDisplayName": "YouTube Transcript"' in setup_text
    assert '"resources": [str(PROJECT_ROOT / "LICENSE")]' in setup_text


def test_py2app_compat_skips_copying_builtin_zlib() -> None:
    patch = runpy.run_path(str(PY2APP_COMPAT))["patch_py2app_for_builtin_zlib"]
    builtin_zlib = SimpleNamespace()

    class FakePy2App:
        def __init__(self) -> None:
            self.copied = []

        def copy_file(self, source, destination):
            self.copied.append((source, destination))
            return destination, True

        def build_executable(self):
            self.copy_file(builtin_zlib.__file__, "lib-dynload")
            self.copy_file("real-extension.so", "lib-dynload")
            return "built"

    assert patch(FakePy2App, builtin_zlib) is True
    command = FakePy2App()

    assert command.build_executable() == "built"
    assert command.copied == [("real-extension.so", "lib-dynload")]
    assert not hasattr(builtin_zlib, "__file__")
    assert "copy_file" not in vars(command)
    assert patch(FakePy2App, builtin_zlib) is False
