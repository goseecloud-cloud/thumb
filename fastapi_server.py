from pathlib import Path
import io
import os
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image

from main import ThumbnailGenerator

app = FastAPI(
    title="썸네일 생성기 서비스",
    description="이미지 URL 또는 업로드 파일로 썸네일을 생성하는 서비스",
    version="3.0.0"
)

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")


class ThumbnailRequest(BaseModel):
    url: str
    title: str
    output_type: str = "local"


class ThumbnailResponse(BaseModel):
    success: bool
    message: str
    thumbnail_url: str | None = None
    local_path: str | None = None
    filename: str | None = None
    error: str | None = None


def _create_thumbnail_image(
    generator: ThumbnailGenerator,
    source_image: Image.Image,
    title: str,
    shape: str = "square",
    font_size: int | None = None,
    border: bool = True,
    text_color: str = "white",
    overlay_opacity: float = 0.5,
) -> Image.Image:
    image = source_image
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Shape-based resize
    if shape == "landscape":
        target = (1280, 720)
    elif shape == "portrait":
        target = (720, 1280)
    else:
        target = (1080, 1080)
        image = generator.crop_to_square(image)

    image = generator.resize_image(image, target)
    image = generator.apply_dark_overlay(image, overlay_opacity)

    if border:
        generator.border_margin = 40
        generator.border_width = 6
        image = generator.add_border(image, generator.border_margin, generator.border_width)
    else:
        generator.border_margin = 0
        generator.border_width = 0

    if font_size:
        generator.default_font_size = font_size

    image = generator.add_text_overlay_custom(image, title, text_color)
    return image


def _save_local_image(image: Image.Image, filename: str) -> str:
    local_path = OUTPUT_DIR / filename
    image.save(local_path, format="PNG", optimize=True)
    return str(local_path)


def _build_local_url(request: Request, filename: str) -> str:
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}/output/{quote(filename)}"


def _finalize_response(
    request: Request,
    generator: ThumbnailGenerator,
    image: Image.Image,
    message_prefix: str = "썸네일이 성공적으로 생성되었습니다."
) -> ThumbnailResponse:
    filename = generator.generate_filename()
    local_path = _save_local_image(image, filename)
    local_url = _build_local_url(request, filename)

    return ThumbnailResponse(
        success=True,
        message=f"{message_prefix}",
        thumbnail_url=local_url,
        local_path=local_path,
        filename=filename
    )


@app.get("/", response_class=HTMLResponse)
async def main_page():
    html_path = BASE_DIR / "index.html"
    if html_path.exists():
        return FileResponse(str(html_path))
    return HTMLResponse("<h1>index.html not found</h1>", status_code=404)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "thumbnail-generator"}


@app.post("/generate", response_model=ThumbnailResponse)
async def generate_thumbnail_by_url(payload: ThumbnailRequest, request: Request):
    if not payload.url.strip():
        raise HTTPException(status_code=400, detail="url은 필수입니다.")
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="title은 필수입니다.")
    try:
        generator = ThumbnailGenerator()
        source_image = generator.download_image(payload.url)
        image = _create_thumbnail_image(generator, source_image, payload.title)
        return _finalize_response(request, generator, image)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"썸네일 생성 중 오류가 발생했습니다: {e}")


@app.post("/generate-file", response_model=ThumbnailResponse)
async def generate_thumbnail_by_file(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    shape: str = Form("square"),
    font_size: int = Form(0),
    border: str = Form("true"),
    text_color: str = Form("white"),
    overlay_opacity: float = Form(0.5),
):
    if not title.strip():
        raise HTTPException(status_code=400, detail="title은 필수입니다.")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드할 수 있습니다.")

    try:
        file_bytes = await file.read()
        source_image = Image.open(io.BytesIO(file_bytes)).convert("RGB")

        generator = ThumbnailGenerator()
        image = _create_thumbnail_image(
            generator,
            source_image,
            title,
            shape=shape,
            font_size=font_size if font_size > 0 else None,
            border=(border.lower() == "true"),
            text_color=text_color,
            overlay_opacity=overlay_opacity,
        )
        return _finalize_response(
            request,
            generator,
            image,
            message_prefix="썸네일이 성공적으로 생성되었습니다."
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 썸네일 생성 중 오류가 발생했습니다: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8866)
