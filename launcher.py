#!/usr/bin/env python3
"""
Minimal macOS app launcher for YouTube Transcript Extractor.
Starts the web server and opens the browser automatically.
"""

import threading
import webbrowser
import time
import sys
import os

# Add the app directory to path for imports
if getattr(sys, 'frozen', False):
    # Running as bundled app
    app_dir = os.path.dirname(sys.executable)
    # For py2app, resources are in ../Resources
    resources_dir = os.path.join(os.path.dirname(app_dir), 'Resources')
    sys.path.insert(0, resources_dir)
    os.chdir(resources_dir)
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, app_dir)
    os.chdir(app_dir)

HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"


def start_server():
    """Start the uvicorn server."""
    import uvicorn
    from app import app
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


def open_browser():
    """Open browser after short delay to let server start."""
    time.sleep(1.5)
    webbrowser.open(URL)


def main():
    print(f"Starting YouTube Transcript Extractor...")
    print(f"Opening {URL} in your browser...")

    # Start browser opener in background
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    # Run server (blocks until interrupted)
    try:
        start_server()
    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)


if __name__ == "__main__":
    main()
