import io
import os
import uuid
import traceback
from pathlib import Path
from contextlib import asynccontextmanager

import zipstream
import numpy as np
import cv2
from PIL import Image

try:
    import tifffile
except ImportError:
    pass
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# --- Helper functions ---
def to_linear(c: np.ndarray) -> np.ndarray:
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

def to_srgb(c: np.ndarray) -> np.ndarray:
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * (c ** (1 / 2.4)) - 0.055)

# --- FastAPI App Setup ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Application startup: Cleaning temporary directory...")
    for filename in os.listdir(TEMP_DIR):
        if filename != ".gitkeep":
            try: os.remove(TEMP_DIR / filename)
            except OSError as e: print(f"Could not remove temporary file {filename}: {e}")
    yield
    print("Application shutdown.")

app = FastAPI(title="Enhanced Grayscale Converter API", lifespan=lifespan)
TEMP_DIR = Path("temp_output")
TEMP_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/temp", StaticFiles(directory=TEMP_DIR), name="temp")
templates = Jinja2Templates(directory="templates")


# --- Core Application Logic ---
def analyze_image_properties(image: Image.Image):
    info = {"filepath": getattr(image, "filename", "clipboard"), "size": image.size, "mode": image.mode}
    info["exif"] = image.info.get("exif")
    info["icc_profile"] = image.info.get("icc_profile")
    info["dpi"] = image.info.get("dpi")
    try:
        np_array = np.array(image)
        if np_array.dtype == np.uint16: info["bit_depth"] = 16
        elif np_array.dtype in [np.uint32, np.float32]: info["bit_depth"] = 32
        else: info["bit_depth"] = 8
    except Exception:
        if image.mode in ("I;16", "I;16B", "I;16L"): info["bit_depth"] = 16
        else: info["bit_depth"] = 8
    info["display_text"] = f"{image.size[0]}x{image.size[1]} | {image.mode} | {info['bit_depth']}-bit"
    return info

def convert_to_enhanced_grayscale(image: Image.Image, mode: str, target_bit_depth: int):
    if image.mode == 'RGBA': cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGBA2BGRA)
    elif image.mode == 'RGB': cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    elif image.mode == 'LA':
        L, A_pil = image.split()
        cv_image = cv2.cvtColor(np.array(L), cv2.COLOR_GRAY2BGRA)
        cv_image[:, :, 3] = np.array(A_pil)
    elif image.mode == 'L': cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_GRAY2BGR)
    else:
        rgba_image = image.convert("RGBA")
        cv_image = cv2.cvtColor(np.array(rgba_image), cv2.COLOR_RGBA2BGRA)
    has_alpha = cv_image.shape[2] == 4
    alpha_channel_pil = Image.fromarray(cv_image[:, :, 3]) if has_alpha else None
    if cv_image.dtype == np.uint8: cv_image = cv_image.astype(np.uint16) * 257
    elif cv_image.dtype != np.uint16: raise ValueError(f"Unsupported image dtype {cv_image.dtype}")
    B, G, R = cv2.split(cv_image)[:3]
    Rf, Gf, Bf = R.astype(np.float64)/65535.0, G.astype(np.float64)/65535.0, B.astype(np.float64)/65535.0
    mode_map = {"Rec. 601": '601', "Rec. 709": '709', "Rec. 2100": '2100', "Gamma": 'gamma'}
    script_mode = mode_map.get(mode, '709')
    if script_mode == 'gamma':
        Rl, Gl, Bl = to_linear(Rf), to_linear(Gf), to_linear(Bf)
        Yl = 0.2126 * Rl + 0.7152 * Gl + 0.0722 * Bl
        gray_float = to_srgb(Yl)
    else:
        weights = {'601':(0.299,0.587,0.114),'709':(0.2126,0.7152,0.0722),'2100':(0.2627,0.6780,0.0593)}
        wR, wG, wB = weights[script_mode]
        gray_float = wR * Rf + wG * Gf + wB * Bf
    gray_float = np.clip(gray_float, 0, 1)
    if target_bit_depth == 16: multiplier, dtype = 65535, np.uint16
    else: multiplier, dtype = 255, np.uint8
    final_array = np.round(gray_float * multiplier).astype(dtype)
    return final_array, alpha_channel_pil

def perform_save(gray_array: np.ndarray, alpha_image: Image.Image, filepath, settings: dict, original_info: dict):
    file_ext = Path(str(filepath)).suffix.lower() if isinstance(filepath, (str, Path)) else settings["output_format"]
    is_high_bit_depth = settings["bit_depth"] > 8
    has_alpha = alpha_image and settings["preserve_alpha"]
    
    # Case 1: 16-bit TIFF with Alpha (Specialist: tifffile)
    if file_ext == ".tiff" and is_high_bit_depth and has_alpha:
        alpha_8bit_np = np.array(alpha_image.convert("L"))
        A16 = (alpha_8bit_np.astype(np.uint16)) * 257
        stacked = np.stack([gray_array, A16], axis=-1)
        tifffile.imwrite(filepath, stacked, photometric="minisblack", extrasamples=["unassalpha"])
        return

    # Case 2: 16-bit PNG with Alpha (Specialist: OpenCV)
    if file_ext == ".png" and is_high_bit_depth and has_alpha:
        Y16 = gray_array
        alpha_8bit_np = np.array(alpha_image.convert("L"))
        A16 = (alpha_8bit_np.astype(np.uint16)) * 257
        out_cv = cv2.merge([Y16, Y16, Y16, A16])
        success, buffer = cv2.imencode(file_ext, out_cv)
        if not success: raise IOError("Failed to encode 16-bit PNG with alpha.")
        if isinstance(filepath, io.BytesIO): filepath.write(buffer)
        else:
            with open(filepath, 'wb') as f: f.write(buffer)
        return

    # Case 3: All other formats (Generalist: Pillow)
    target_mode = "I;16" if is_high_bit_depth else "L"
    final_image = Image.fromarray(gray_array, mode=target_mode)
    if settings.get("size") and settings["size"] != final_image.size:
        final_image = final_image.resize(settings["size"], Image.Resampling.LANCZOS)
    
    if has_alpha:
        final_image = Image.merge("LA", (final_image.convert("L"), alpha_image.convert("L")))
    
    save_kwargs = {}
    if not settings.get("strip_metadata", False):
        if original_info.get("icc_profile"): save_kwargs["icc_profile"] = original_info["icc_profile"]
        if settings.get("dpi"): save_kwargs["dpi"] = (settings["dpi"], settings["dpi"])
    
    format_map = {".jpeg": "JPEG", ".jpg": "JPEG", ".png": "PNG", ".tiff": "TIFF", ".webp": "WEBP", ".bmp": "BMP", ".heic": "HEIF", ".heif": "HEIF"}
    file_format = format_map.get(file_ext, "PNG")

    if file_ext in [".jpg", ".jpeg"]:
        final_image = final_image.convert("L")
        save_kwargs.update({"quality": settings.get("quality", 100), "subsampling": settings.get("subsampling", 0)})
    elif file_ext in [".heic", ".heif"]:
        save_kwargs.update({"quality": settings.get("quality", 100)})

    final_image.save(filepath, format=file_format, **save_kwargs)


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/convert")
async def handle_conversion(
    request: Request, file: UploadFile = File(...), conversion_mode: str = Form(...),
    output_format: str = Form(...), bit_depth: int = Form(...), quality: int = Form(100),
    subsampling: int = Form(0), width: int = Form(0), height: int = Form(0),
    dpi: int = Form(0), preserve_alpha: bool = Form(False), strip_metadata: bool = Form(False),
):
    try:
        contents = await file.read()
        original_image = Image.open(io.BytesIO(contents))
        original_image.load()
        original_info = analyze_image_properties(original_image)
        settings = locals()
        del settings["request"], settings["file"], settings["contents"]
        settings["size"] = (width, height) if width > 0 and height > 0 else original_info["size"]
        gray_array, alpha_channel = convert_to_enhanced_grayscale(original_image, settings["conversion_mode"], settings["bit_depth"])
        output_filename = f"{uuid.uuid4()}{settings['output_format']}"
        output_path = TEMP_DIR / output_filename
        perform_save(gray_array, alpha_channel, output_path, settings, original_info)
        return JSONResponse(content={"success": True, "download_url": f"/temp/{output_filename}", "original_info": original_info["display_text"]})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.post("/api/batch-convert")
async def handle_batch_conversion(
    files: list[UploadFile] = File(...), conversion_mode: str = Form(...),
    output_format: str = Form(...), bit_depth: int = Form(...), quality: int = Form(100),
    subsampling: int = Form(0), width: int = Form(0), height: int = Form(0),
    dpi: int = Form(0), preserve_alpha: bool = Form(False), strip_metadata: bool = Form(False),
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
                current_settings["size"] = (settings["width"], settings["height"]) if settings.get("width") and settings.get("height") else original_info["size"]
                gray_array, alpha_channel = convert_to_enhanced_grayscale(original_image, current_settings["conversion_mode"], current_settings["bit_depth"])
                output_buffer = io.BytesIO()
                perform_save(gray_array, alpha_channel, output_buffer, current_settings, original_info)
                output_buffer.seek(0)
                new_filename = f"{Path(file.filename).stem}_grayscale{current_settings['output_format']}"
                yield new_filename, output_buffer.read()
            except Exception as e:
                print(f"Batch convert error for {file.filename}: {e}")
                traceback.print_exc()
                continue
    zip_stream = zipstream.ZipStream()
    for filename, data in image_generator():
        zip_stream.add(io.BytesIO(data), filename)
    response = StreamingResponse(zip_stream, media_type="application/x-zip-compressed")
    response.headers["Content-Disposition"] = "attachment; filename=grayscale_batch.zip"
    return response