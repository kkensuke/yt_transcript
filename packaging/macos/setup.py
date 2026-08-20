"""Isolated py2app configuration for the macOS application bundle.

Run this file from ``packaging/macos``. Keeping it outside the Python
project root prevents setuptools from copying the application's
``[project].dependencies`` to ``install_requires``, which py2app rejects.
"""

import zlib
from pathlib import Path

from py2app.build_app import py2app as py2app_command
from py2app_compat import patch_py2app_for_builtin_zlib
from setuptools import setup

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP = [str(PROJECT_ROOT / "YouTubeTranscript.py")]
OPTIONS = {
    "argv_emulation": False,
    "bdist_base": str(PROJECT_ROOT / "build"),
    "dist_dir": str(PROJECT_ROOT / "dist"),
    # pywebview selects Cocoa dynamically and yt-dlp loads extractors dynamically,
    # so copy these packages in full instead of relying only on import analysis.
    "packages": ["yt_dlp_transcript", "yt_dlp", "webview"],
    "includes": ["AppKit", "Foundation", "WebKit", "objc", "PyObjCTools.AppHelper"],
    "resources": [str(PROJECT_ROOT / "LICENSE")],
    "plist": {
        "CFBundleName": "YouTubeTranscript",
        "CFBundleDisplayName": "YouTube Transcript",
        "CFBundleIdentifier": "com.kkensuke.youtube-transcript",
        "CFBundleShortVersionString": "0.2.0",
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
    },
}

patch_py2app_for_builtin_zlib(py2app_command, zlib)


setup(
    name="YouTubeTranscript",
    version="0.2.0",
    app=APP,
    options={"py2app": OPTIONS},
)
