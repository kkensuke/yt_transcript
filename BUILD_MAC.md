# Building macOS App

## Quick Build (using uv)

```bash
# Install mac dependencies
uv sync --extra mac

# Build the app
uv run python setup.py py2app

# The app will be in dist/YT Transcript.app
```

## Quick Build (using pip)

```bash
# Install dependencies
pip install py2app setuptools

# Build the app
python setup.py py2app

# The app will be in dist/YT Transcript.app
```

## Development Build (faster, uses aliases)

```bash
python setup.py py2app -A
```

## Running Without Building

```bash
python launcher.py
```

This will start the server and open your browser automatically.

## Custom Icon (Optional)

To add a custom icon:
1. Create a 1024x1024 PNG image
2. Convert to `.icns` format using:
   ```bash
   mkdir icon.iconset
   sips -z 16 16 icon.png --out icon.iconset/icon_16x16.png
   sips -z 32 32 icon.png --out icon.iconset/icon_16x16@2x.png
   sips -z 32 32 icon.png --out icon.iconset/icon_32x32.png
   sips -z 64 64 icon.png --out icon.iconset/icon_32x32@2x.png
   sips -z 128 128 icon.png --out icon.iconset/icon_128x128.png
   sips -z 256 256 icon.png --out icon.iconset/icon_128x128@2x.png
   sips -z 256 256 icon.png --out icon.iconset/icon_256x256.png
   sips -z 512 512 icon.png --out icon.iconset/icon_256x256@2x.png
   sips -z 512 512 icon.png --out icon.iconset/icon_512x512.png
   sips -z 1024 1024 icon.png --out icon.iconset/icon_512x512@2x.png
   iconutil -c icns icon.iconset
   ```
3. Place `icon.icns` in the project root

## Distribution

The built app in `dist/` can be:
- Moved to `/Applications`
- Zipped for distribution
- Signed with a Developer ID for wider distribution
