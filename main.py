import io
import os
import uuid
import shutil
import traceback
from pathlib import Path
import zipstream
import numpy as np
from PIL import Image, ImageGrab, PngImagePlugin, ExifTags, TiffImagePlugin
import tifffile
import imageio.v2 as imageio

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:
    pass

from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Enhanced Grayscale Converter API")
TEMP_DIR = Path("temp_output")
TEMP_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/temp", StaticFiles(directory=TEMP_DIR), name="temp")
templates = Jinja2Templates(directory="templates")


def analyze_image_properties(image: Image.Image):
    info = {
        "filepath": getattr(image, "filename", "clipboard"),
        "size": image.size,
        "mode": image.mode,
    }
    info["exif"] = image.info.get("exif")
    info["icc_profile"] = image.info.get("icc_profile")
    info["dpi"] = image.info.get("dpi")
    try:
        dtype_str = str(np.array(image).dtype)
        if "16" in dtype_str:
            info["bit_depth"] = 16
        elif "32" in dtype_str:
            info["bit_depth"] = 32
        else:
            info["bit_depth"] = 8
    except Exception:
        if image.mode in ("I;16", "I;16B", "I;16L"):
            info["bit_depth"] = 16
        else:
            info["bit_depth"] = 8
    info["display_text"] = (
        f"{image.size[0]}x{image.size[1]} | {image.mode} | {info['bit_depth']}-bit"
    )
    return info


def convert_to_enhanced_grayscale(image: Image.Image, mode: str, target_bit_depth: int):
    has_alpha = "A" in image.getbands()
    alpha_image_out = image.getchannel("A") if has_alpha else None

    if image.mode not in ("RGB", "RGBA"):
        rgb_image = image.convert("RGBA" if has_alpha else "RGB")
    else:
        rgb_image = image

    gray_float = None
    final_array = None

    if mode == "L*a*b* (L*)":
        l_channel, _, _ = rgb_image.convert("LAB").split()
        final_array = np.array(l_channel)
    elif mode == "HSV (Value)":
        _, _, v_channel = rgb_image.convert("HSV").split()
        final_array = np.array(v_channel)
    else:
        source_is_16bit_depth = hasattr(image, "dtype") and np.issubdtype(
            image.dtype, np.uint16
        )
        source_dtype = np.float32
        if source_is_16bit_depth:
            rgb_array = np.array(rgb_image.convert("RGB"), dtype=source_dtype) / 65535.0
        else:
            rgb_array = np.array(rgb_image.convert("RGB"), dtype=source_dtype) / 255.0

        if mode == "HSL (Lightness)":
            cmax = np.maximum.reduce(rgb_array, axis=-1)
            cmin = np.minimum.reduce(rgb_array, axis=-1)
            gray_float = (cmax + cmin) / 2.0
        elif mode == "Gamma":
            srgb_linear = np.where(
                rgb_array <= 0.04045,
                rgb_array / 12.92,
                ((rgb_array + 0.055) / 1.055) ** 2.4,
            )
            y_linear = np.dot(srgb_linear, [0.2126, 0.7152, 0.0722])
            gray_float = np.where(
                y_linear <= 0.0031308,
                y_linear * 12.92,
                1.055 * (y_linear ** (1 / 2.4)) - 0.055,
            )
        else:
            coeffs = {
                "Rec. 601": [0.299, 0.587, 0.114],
                "Rec. 709": [0.2126, 0.7152, 0.0722],
                "Rec. 2100": [0.2627, 0.6780, 0.0593],
            }.get(mode, [0.2126, 0.7152, 0.0722])
            gray_float = np.dot(rgb_array, coeffs)

    if gray_float is not None:
        gray_float = np.clip(gray_float, 0, 1)
        if target_bit_depth == 16:
            dtype = np.uint16
            multiplier = 65535
        elif target_bit_depth == 10:
            dtype = np.uint16
            multiplier = 1023
        else:
            dtype = np.uint8
            multiplier = 255
        final_array = (gray_float * multiplier).astype(dtype)

    return final_array, alpha_image_out


def perform_save(
    gray_array: np.ndarray,
    alpha_image: Image.Image,
    filepath,
    settings: dict,
    original_info: dict,
):
    file_ext = (
        Path(str(filepath)).suffix.lower()
        if isinstance(filepath, (str, Path))
        else settings["output_format"]
    )

    is_high_bit_depth = settings["bit_depth"] > 8
    target_mode = "I;16" if is_high_bit_depth else "L"
    final_image = Image.fromarray(gray_array, mode=target_mode)

    has_alpha = alpha_image and settings["preserve_alpha"]

    if settings.get("size") and settings["size"] != final_image.size:
        final_image = final_image.resize(settings["size"], Image.Resampling.LANCZOS)

    save_kwargs = {}
    if not settings.get("strip_metadata", False):
        if original_info.get("icc_profile"):
            save_kwargs["icc_profile"] = original_info["icc_profile"]
        if settings.get("dpi"):
            save_kwargs["dpi"] = (settings["dpi"], settings["dpi"])

    # Detect if saving to a BytesIO buffer and set format explicitly
    is_buffer = isinstance(filepath, io.BytesIO)
    format_map = {
        ".jpeg": "JPEG",
        ".jpg": "JPEG",
        ".png": "PNG",
        ".tiff": "TIFF",
        ".webp": "WEBP",
        ".bmp": "BMP",
        ".heic": "HEIF",
        ".heif": "HEIF",
    }
    file_format = format_map.get(file_ext, None)

    if file_ext == ".jpeg":
        final_image = final_image.convert("L")
        save_kwargs.update(
            {
                "quality": settings.get("quality", 100),
                "subsampling": settings.get("subsampling", 0),
            }
        )
        if is_buffer:
            final_image.save(filepath, format=file_format, **save_kwargs)
        else:
            final_image.save(filepath, "JPEG", **save_kwargs)

    elif file_ext in [".heic", ".heif"]:
        if is_high_bit_depth:
            has_alpha = False
        save_image = final_image.convert("LA" if has_alpha else "L")
        save_kwargs.update({"quality": settings.get("quality", 100)})
        if settings["bit_depth"] == 10:
            save_kwargs["bit_depth"] = 10
        save_kwargs["chroma"] = settings.get("subsampling", 0)
        if "dpi" in save_kwargs:
            del save_kwargs["dpi"]
        if is_buffer:
            save_image.save(filepath, format=file_format, **save_kwargs)
        else:
            save_image.save(filepath, "HEIF", **save_kwargs)

    elif file_ext == ".tiff":
        if is_high_bit_depth and has_alpha:
            alpha_arr = (
                np.array(alpha_image.convert("L"), dtype=np.uint32) * 257
            ).astype(np.uint16)
            stacked = np.stack([gray_array, alpha_arr], axis=-1)
            if is_buffer:
                tifffile.imwrite(
                    filepath,
                    stacked,
                    photometric="minisblack",
                    extratasamples=["unassalpha"],
                )
            else:
                tifffile.imwrite(
                    filepath,
                    stacked,
                    photometric="minisblack",
                    extratasamples=["unassalpha"],
                )
        else:
            if has_alpha:
                final_image = Image.merge(
                    "LA", (final_image.convert("L"), alpha_image.convert("L"))
                )
            if is_buffer:
                final_image.save(filepath, format=file_format, **save_kwargs)
            else:
                final_image.save(filepath, "TIFF", **save_kwargs)

    else:
        if has_alpha and file_ext in [".png", ".webp"]:
            if final_image.mode != "LA":
                final_image = Image.merge(
                    "LA", (final_image.convert("L"), alpha_image.convert("L"))
                )
        else:
            if final_image.mode != "L" and final_image.mode != "I;16":
                final_image = final_image.convert(
                    "L" if not is_high_bit_depth else "I;16"
                )
        if is_buffer:
            final_image.save(filepath, format=file_format, **save_kwargs)
        else:
            final_image.save(
                filepath, file_format if file_format else None, **save_kwargs
            )


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/convert")
async def handle_conversion(
    request: Request,
    file: UploadFile = File(...),
    conversion_mode: str = Form(...),
    output_format: str = Form(...),
    bit_depth: int = Form(...),
    quality: int = Form(100),
    subsampling: int = Form(0),
    width: int = Form(0),
    height: int = Form(0),
    dpi: int = Form(0),
    preserve_alpha: bool = Form(False),
    strip_metadata: bool = Form(False),
):
    try:
        contents = await file.read()
        original_image = Image.open(io.BytesIO(contents))
        original_image.load()
        original_info = analyze_image_properties(original_image)

        settings = locals()
        del settings["request"], settings["file"], settings["contents"]
        settings["size"] = (
            (width, height) if width > 0 and height > 0 else original_info["size"]
        )

        gray_array, alpha_channel = convert_to_enhanced_grayscale(
            original_image, settings["conversion_mode"], settings["bit_depth"]
        )

        output_filename = f"{uuid.uuid4()}{settings['output_format']}"
        output_path = TEMP_DIR / output_filename

        perform_save(gray_array, alpha_channel, output_path, settings, original_info)

        return JSONResponse(
            content={
                "success": True,
                "download_url": f"/temp/{output_filename}",
                "original_info": original_info["display_text"],
            }
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


@app.post("/api/batch-convert")
async def handle_batch_conversion(
    files: list[UploadFile] = File(...),
    conversion_mode: str = Form(...),
    output_format: str = Form(...),
    bit_depth: int = Form(...),
    quality: int = Form(100),
    subsampling: int = Form(0),
    width: int = Form(0),
    height: int = Form(0),
    dpi: int = Form(0),
    preserve_alpha: bool = Form(False),
    strip_metadata: bool = Form(False),
):
    settings = locals()
    del settings["files"]

    def image_generator():
        for file in files:
            try:
                contents = file.file.read()
                original_image = Image.open(io.BytesIO(contents))
                original_image.load()
                original_info = analyze_image_properties(original_image)

                current_settings = settings.copy()
                current_settings["size"] = (
                    (settings["width"], settings["height"])
                    if settings.get("width") and settings.get("height")
                    else original_info["size"]
                )

                gray_array, alpha_channel = convert_to_enhanced_grayscale(
                    original_image,
                    current_settings["conversion_mode"],
                    current_settings["bit_depth"],
                )
                output_buffer = io.BytesIO()
                # Pass format explicitly for BytesIO
                perform_save(
                    gray_array,
                    alpha_channel,
                    output_buffer,
                    current_settings,
                    original_info,
                )
                output_buffer.seek(0)
                new_filename = f"{Path(file.filename).stem}_grayscale{current_settings['output_format']}"
                yield new_filename, output_buffer.read()
            except Exception as e:
                print(f"Batch convert error for {file.filename}: {e}")
                import traceback

                traceback.print_exc()
                continue

    # Use zipstream-ng ZipStream
    zip_stream = zipstream.ZipStream()
    for filename, data in image_generator():
        zip_stream.add(io.BytesIO(data), filename)

    response = StreamingResponse(zip_stream, media_type="application/x-zip-compressed")
    response.headers["Content-Disposition"] = "attachment; filename=grayscale_batch.zip"
    return response


@app.on_event("startup")
async def startup_event():
    for filename in os.listdir(TEMP_DIR):
        if filename != ".gitkeep":
            try:
                os.remove(TEMP_DIR / filename)
            except OSError:
                pass
