"""
py2app setup script for YouTube Transcript Extractor macOS app.

Build with:
    python setup.py py2app

For development/testing:
    python setup.py py2app -A
"""

from setuptools import setup

APP = ['launcher.py']
APP_NAME = 'YT Transcript'

DATA_FILES = [
    ('', ['app.py', 'url_extractor.py', 'transcript_processor.py',
          'gemini_api.py', 'utils.py']),
]

OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'icon.icns',  # Optional: add your own icon
    'plist': {
        'CFBundleName': APP_NAME,
        'CFBundleDisplayName': APP_NAME,
        'CFBundleIdentifier': 'com.yttranscript.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSMinimumSystemVersion': '10.15',
        'NSHighResolutionCapable': True,
        'LSBackgroundOnly': False,
    },
    'packages': ['uvicorn', 'fastapi', 'yt_dlp', 'pydantic', 'starlette',
                 'anyio', 'httptools', 'watchfiles', 'websockets'],
    'includes': ['app', 'url_extractor', 'transcript_processor',
                 'gemini_api', 'utils'],
}

setup(
    name=APP_NAME,
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
