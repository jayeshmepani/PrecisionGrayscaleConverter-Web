# Enhanced Precision Grayscale Converter — Web

A FastAPI web application for single-image and batch grayscale conversion. The responsive JavaScript interface sends selected images to the application's own FastAPI server for processing; images are not sent to a third-party image-conversion API.

## Features

- Single-image and batch conversion.
- Seven grayscale modes: Rec. 601, Rec. 709, Rec. 2100, Gamma-corrected Rec. 709, CIE L*a*b* L*, HSL Lightness, and HSV Value.
- 8-bit and 16-bit grayscale output.
- PNG, JPEG, HEIC/HEIF, TIFF, WEBP, and BMP export options (format/bit-depth support varies).
- Optional transparency preservation where the selected output format supports it.
- JPEG/HEIC quality controls and JPEG chroma-subsampling controls.
- Optional metadata stripping; ICC profile and DPI metadata can be carried through supported save paths.
- Adjustable output dimensions for single-image conversion.
- ZIP download for batch output.

## Requirements

- Python 3
- Dependencies listed in `requirements.txt`
- Node.js/npm only when rebuilding the optional Tailwind CSS assets

HEIC/HEIF support depends on `pillow-heif` and the available system codec support. TIFF handling uses `tifffile`.

## Run locally

```bash
git clone https://github.com/jayeshmepani/PrecisionGrayscaleConverter-Web.git
cd PrecisionGrayscaleConverter-Web

python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

Open http://127.0.0.1:8001.

To rebuild frontend CSS when changing the Tailwind source/configuration:

```bash
npm install
npm run build:css
```

## API

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | Web interface |
| `/api/convert` | POST | Convert one uploaded image and return conversion metadata/result |
| `/api/batch-convert` | POST | Convert multiple uploaded images and return a ZIP archive |

Interactive API documentation is available at `/docs` while the server is running.

## Processing and privacy

Conversion happens on the FastAPI server that hosts this application, not locally inside the browser. Uploaded files are handled by that server, and temporary output is stored in the application's `temp_output/` directory. The startup lifecycle clears files in that directory. Deployments should use appropriate request limits, access controls, temporary-storage policies, and HTTPS.

The conversion modes are mathematical transforms, not interchangeable standards. Gamma-corrected Rec. 709, Rec. 601/709/2100 luma weighting, CIE Lab L*, HSL lightness, and HSV value produce different results. Choose the mode appropriate to the intended workflow.

## License

MIT. See [LICENSE](LICENSE).
