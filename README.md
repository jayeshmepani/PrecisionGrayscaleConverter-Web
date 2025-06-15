# Enhanced Precision Grayscale Converter

A modern web app for high-quality grayscale image conversion and batch processing, built with FastAPI (Python backend) and a responsive JavaScript frontend.

## Features

- **Single & Batch Image Conversion**: Convert one or many images at once.
- **Advanced Grayscale Modes**: Choose from Rec. 709, L*a*b\*, HSL, HSV, and more.
- **High Bit Depth Support**: 8, 16-bit output for maximum quality.
- **Format Options**: PNG, JPEG, HEIC, TIFF, WEBP, BMP.
- **Chroma Subsampling & Quality Controls**: Always defaults to best quality (4:4:4, quality=100).
- **Preserve Transparency**: Optionally keep alpha channels.
- **Metadata Handling**: Option to strip or preserve EXIF/ICC/DPI.
- **Live Preview**: See before/after instantly in the browser.
- **No Image Uploads Required**: All processing is local to your server.

## Quick Start

### 1. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
npm install  # for Tailwind CSS (optional, for development)
```

### 2. Build CSS (optional, for development)

```bash
npm run build:css
```

### 3. Run the server

```bash
uvicorn main:app --reload --port 8001
```

Then open [http://localhost:8001](http://localhost:8001) in your browser.

## Project Structure

- `main.py` — FastAPI backend (image processing, API endpoints)
- `static/` — JS, CSS, and assets
- `templates/` — HTML templates (Jinja2)
- `requirements.txt` — Python dependencies
- `package.json`, `tailwind.config.js` — Frontend build config
- `temp_output/` — Temporary output files (auto-created)

## Troubleshooting

### File Watch Limit Error

If you see an error like `OS file watch limit reached` or similar when running the server with `--reload`, you may need to increase the file watch limit on your system.

#### Linux (inotify limit)

```bash
echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf && sudo sysctl -p
```

#### Windows (watch limit)

- If you see errors about file watching on Windows, try running VS Code or your terminal as Administrator.
- For WSL, use the Linux command above inside your WSL terminal.
- If using Python's `watchdog` or similar, you may need to install the Windows C++ build tools or update your Python environment.
- If issues persist, consider disabling `--reload` or reducing the number of watched files.

### HEIC/HEIF Support

- Requires `pillow-heif` (Python) and system libraries (libheif).
- On Linux, install `libheif-dev` via your package manager (e.g., `sudo apt install libheif-dev`).
- On Windows, use pre-built wheels for `pillow-heif` or see the [pillow-heif documentation](https://github.com/carsales/pyheif) for Windows support.

## License

MIT
