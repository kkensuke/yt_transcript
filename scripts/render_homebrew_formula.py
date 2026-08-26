#!/usr/bin/env python3
"""Render the Homebrew tap formula from the project's locked Web dependency graph."""

from __future__ import annotations

import argparse
import re
import tomllib
from collections import deque
from pathlib import Path

from packaging.markers import Marker, default_environment
from packaging.utils import canonicalize_name

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
LOCK_PATH = PROJECT_ROOT / "uv.lock"
REPOSITORY = "kkensuke/yt_transcript"
FORMULA_CLASS = "YtTranscript"
WEB_EXTRA = "web"
TARGET_PYTHON = "3.14"

# Homebrew's pydantic formula installs importable modules for each supported
# Python version. Keeping this compiled dependency in Homebrew avoids building
# pydantic-core independently in the tap formula.
HOMEBREW_PROVIDED_PACKAGES = frozenset(
    {
        "annotated-types",
        "pydantic",
        "pydantic-core",
        "typing-extensions",
        "typing-inspection",
    }
)


def _load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as source:
        return tomllib.load(source)


def _marker_applies(marker: str | None) -> bool:
    if not marker:
        return True

    parsed = Marker(marker)
    for sys_platform, platform_system in (("darwin", "Darwin"), ("linux", "Linux")):
        environment = default_environment()
        environment.update(
            {
                "extra": "",
                "python_full_version": f"{TARGET_PYTHON}.0",
                "python_version": TARGET_PYTHON,
                "sys_platform": sys_platform,
                "platform_system": platform_system,
            }
        )
        if parsed.evaluate(environment):
            return True
    return False


def _dependency_names(dependencies: list[dict[str, object]]) -> list[str]:
    names = []
    for dependency in dependencies:
        marker = dependency.get("marker")
        if marker is not None and not isinstance(marker, str):
            raise ValueError(f"Unsupported dependency marker: {marker!r}")
        if _marker_applies(marker):
            names.append(canonicalize_name(str(dependency["name"])))
    return names


def locked_formula_resources() -> list[dict[str, str]]:
    pyproject = _load_toml(PYPROJECT_PATH)
    lock = _load_toml(LOCK_PATH)
    project = pyproject["project"]
    if not isinstance(project, dict):
        raise ValueError("pyproject.toml has no [project] table")

    project_name = canonicalize_name(str(project["name"]))
    packages = lock.get("package")
    if not isinstance(packages, list):
        raise ValueError("uv.lock has no package list")

    packages_by_name: dict[str, dict[str, object]] = {}
    for package in packages:
        if not isinstance(package, dict):
            raise ValueError("uv.lock contains an invalid package entry")
        name = canonicalize_name(str(package["name"]))
        if name in packages_by_name:
            raise ValueError(f"Multiple locked variants for {name} are not supported")
        packages_by_name[name] = package

    root = packages_by_name.get(project_name)
    if root is None:
        raise ValueError(f"uv.lock does not contain the project package {project_name}")

    root_dependencies = root.get("dependencies", [])
    optional_dependencies = root.get("optional-dependencies", {})
    if not isinstance(root_dependencies, list) or not isinstance(optional_dependencies, dict):
        raise ValueError("uv.lock contains invalid project dependencies")
    web_dependencies = optional_dependencies.get(WEB_EXTRA, [])
    if not isinstance(web_dependencies, list):
        raise ValueError(f"uv.lock contains an invalid {WEB_EXTRA!r} extra")

    pending = deque(_dependency_names(root_dependencies + web_dependencies))
    selected: dict[str, dict[str, object]] = {}
    while pending:
        name = pending.popleft()
        if name in HOMEBREW_PROVIDED_PACKAGES or name in selected:
            continue
        package = packages_by_name.get(name)
        if package is None:
            raise ValueError(f"uv.lock does not contain dependency {name}")
        selected[name] = package
        dependencies = package.get("dependencies", [])
        if not isinstance(dependencies, list):
            raise ValueError(f"uv.lock contains invalid dependencies for {name}")
        pending.extend(_dependency_names(dependencies))

    resources = []
    for name, package in sorted(selected.items()):
        sdist = package.get("sdist")
        if not isinstance(sdist, dict) or not sdist.get("url") or not sdist.get("hash"):
            raise ValueError(f"Locked dependency {name} has no source distribution")
        digest = str(sdist["hash"])
        if not digest.startswith("sha256:"):
            raise ValueError(f"Locked dependency {name} does not use a SHA-256 digest")
        resources.append(
            {
                "name": name,
                "url": str(sdist["url"]),
                "sha256": digest.removeprefix("sha256:"),
            }
        )
    return resources


def project_version() -> str:
    project = _load_toml(PYPROJECT_PATH)["project"]
    if not isinstance(project, dict):
        raise ValueError("pyproject.toml has no [project] table")
    return str(project["version"])


def render_formula(*, version: str, source_sha256: str) -> str:
    if version != project_version():
        raise ValueError(
            f"Release version {version} does not match project version {project_version()}"
        )
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("Release version must use MAJOR.MINOR.PATCH format")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", source_sha256):
        raise ValueError("Source SHA-256 must contain exactly 64 hexadecimal characters")

    lines = [
        "# This file is generated by kkensuke/yt_transcript. Do not edit it manually.",
        f"class {FORMULA_CLASS} < Formula",
        "  include Language::Python::Virtualenv",
        "",
        '  desc "Turn YouTube captions into reusable transcripts and summaries"',
        f'  homepage "https://github.com/{REPOSITORY}"',
        f'  url "https://github.com/{REPOSITORY}/archive/refs/tags/v{version}.tar.gz"',
        f'  sha256 "{source_sha256.lower()}"',
        '  license "MIT"',
        "",
        '  depends_on "pydantic" => :no_linkage',
        '  depends_on "python@3.14"',
    ]
    for resource in locked_formula_resources():
        lines.extend(
            [
                "",
                f'  resource "{resource["name"]}" do',
                f'    url "{resource["url"]}"',
                f'    sha256 "{resource["sha256"]}"',
                "  end",
            ]
        )
    lines.extend(
        [
            "",
            "  def install",
            "    virtualenv_install_with_resources",
            "  end",
            "",
            "  test do",
            '    assert_match version.to_s, shell_output("#{bin}/yt-transcript --version")',
            '    assert_match "--no-open", shell_output("#{bin}/yt-transcript web --help")',
            "",
            "    port = free_port",
            "    pid = nil",
            '    pid = spawn bin/"yt-transcript", "web", "--no-open", "--port", port.to_s',
            "    output = shell_output(",
            '      "curl --silent --retry 5 --retry-connrefused http://127.0.0.1:#{port}/healthz",',
            "    )",
            '    assert_equal \'{"status":"ok"}\', output',
            "  ensure",
            '    Process.kill("TERM", pid) if pid',
            "    Process.wait(pid) if pid",
            "  end",
            "end",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Release version without the v prefix")
    parser.add_argument("--source-sha256", required=True, help="SHA-256 of the GitHub tag archive")
    parser.add_argument("--output", required=True, type=Path, help="Formula path to write")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    formula = render_formula(version=args.version, source_sha256=args.source_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(formula, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
