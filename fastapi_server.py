from pathlib import Path
import io
import os
import time
import asyncio
import logging
from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image

from main import ThumbnailGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── 자동 파일 정리 설정 ──
FILE_MAX_AGE_SECONDS = 60 * 60      # 1시간 지난 파일 삭제
CLEANUP_INTERVAL_SECONDS = 60 * 10  # 10분마다 정리 실행


def cleanup_old_files():
    """output 디렉토리에서 1시간 이상 된 파일 삭제"""
    now = time.time()
    deleted = 0
    total_freed = 0
    for f in OUTPUT_DIR.glob("output_thumbnail_*.png"):
        age = now - f.stat().st_mtime
        if age > FILE_MAX_AGE_SECONDS:
            size = f.stat().st_size
            f.unlink()
            deleted += 1
            total_freed += size
    if deleted > 0:
        logger.info(f"[정리] {deleted}개 파일 삭제, {total_freed / 1024 / 1024:.1f}MB 확보")


async def scheduled_cleanup():
    """백그라운드에서 주기적으로 파일 정리"""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        try:
            cleanup_old_files()
        except Exception as e:
            logger.error(f"[정리] 오류 발생: {e}")


@asynccontextmanager
async def lifespan(app):
    """서버 시작/종료 시 실행"""
    # 시작: 오래된 파일 즉시 정리 + 주기적 정리 태스크 시작
    cleanup_old_files()
    task = asyncio.create_task(scheduled_cleanup())
    logger.info("[시작] 자동 파일 정리 스케줄러 시작 (1시간 보관, 10분 간격 정리)")
    yield
    # 종료: 태스크 취소
    task.cancel()


app = FastAPI(
    title="썸네일 생성기 서비스",
    description="이미지 URL 또는 업로드 파일로 썸네일을 생성하는 서비스",
    version="3.0.0",
    lifespan=lifespan
)

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


# 폰트 파일 매핑
FONT_MAP = {
    "paperlogy": "fonts/Paperlogy-7Bold.ttf",
    "nanum":     "fonts/NanumGothicBold.ttf",
    "blackhan":  "fonts/GmarketSansBold.ttf",
    "noto":      "fonts/NotoSansKR.ttf",
}


def normalize_text(text: str) -> str:
    """
    텍스트 정규화: 특수 공백/제어문자 제거
    - 특수 공백(U+00A0, U+3000 등) → 일반 공백
    - 제어문자 제거 (줄바꿈 제외)
    - Windows/Mac 줄바꿈 정규화
    """
    import re
    # 특수 공백 정규화
    text = re.sub(r'[\u00A0\u1680\u2000-\u200B\u202F\u205F\u3000\uFEFF]', ' ', text)
    # 줄바꿈 정규화
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # 제어문자 제거 (줄바꿈 제외)
    text = ''.join(ch if ch == '\n' or ord(ch) >= 0x20 else '' for ch in text)
    return text.strip()


def _create_thumbnail_image(
    generator: ThumbnailGenerator,
    source_image: Image.Image,
    title: str,
    shape: str = "square",
    font_size: int | None = None,
    font_size_ratio: float = 1.0,
    text_position: str = "middle-center",
    border: bool = True,
    text_color: str = "white",
    overlay_opacity: float = 0.5,
    font_key: str = "paperlogy",
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
        # 원본 이미지 참고: margin 30px, border 6px
        generator.border_margin = 30
        generator.border_width = 6
        image = generator.add_border(image, generator.border_margin, generator.border_width)
    else:
        generator.border_margin = 0
        generator.border_width = 0

    # 폰트 크기는 항상 특대형(220) 고정
    generator.default_font_size = 220

    # 폰트 경로 설정
    font_rel = FONT_MAP.get(font_key, FONT_MAP["paperlogy"])
    font_abs = str(BASE_DIR / font_rel)
    generator.font_paths = [font_abs] + generator.font_paths

    image = generator.add_text_overlay_custom(
        image, title, text_color,
        font_size_ratio=font_size_ratio,
        text_position=text_position,
    )
    return image


def _save_local_image(image: Image.Image, filename: str) -> str:
    local_path = OUTPUT_DIR / filename
    image.save(local_path, format="PNG", optimize=True)
    return str(local_path)


def _build_local_url(request: Request, filename: str) -> str:
    # 상대 경로만 반환 (HTTPS Mixed Content 에러 방지)
    return f"/output/{quote(filename)}"


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
    
    # 텍스트 정규화
    payload.title = normalize_text(payload.title)
    
    try:
        generator = ThumbnailGenerator()
        source_image = generator.download_image(payload.url)
        image = _create_thumbnail_image(generator, source_image, payload.title)
        return _finalize_response(request, generator, image)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"썸네일 생성 중 오류가 발생했습니다: {e}")


@app.get("/fonts/{font_key}")
async def serve_font(font_key: str):
    """프론트엔드 캔버스 미리보기용 폰트 파일 서빙"""
    font_rel = FONT_MAP.get(font_key)
    if not font_rel:
        raise HTTPException(status_code=404, detail="폰트를 찾을 수 없습니다.")
    font_path = BASE_DIR / font_rel
    if not font_path.exists():
        raise HTTPException(status_code=404, detail="폰트 파일이 없습니다.")
    return FileResponse(str(font_path), media_type="font/ttf")


@app.get("/download/{filename}")
async def download_file(filename: str):
    """강제 다운로드 엔드포인트 - Content-Disposition 헤더 추가"""
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(
        str(file_path),
        media_type="image/png",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.post("/generate-file", response_model=ThumbnailResponse)
async def generate_thumbnail_by_file(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    shape: str = Form("square"),
    font_size: int = Form(0),
    font_size_ratio: float = Form(1.0),
    text_position: str = Form("middle-center"),
    border: str = Form("true"),
    text_color: str = Form("white"),
    overlay_opacity: float = Form(0.5),
    font_key: str = Form("paperlogy"),
):
    if not title.strip():
        raise HTTPException(status_code=400, detail="title은 필수입니다.")
    
    # 텍스트 정규화
    title = normalize_text(title)
    
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드할 수 있습니다.")

    try:
        file_bytes = await file.read()
        
        # 파일 크기 체크 (최대 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if len(file_bytes) > max_size:
            raise HTTPException(status_code=400, detail="파일 크기는 10MB 이하여야 합니다.")
        
        source_image = Image.open(io.BytesIO(file_bytes)).convert("RGB")

        generator = ThumbnailGenerator()
        image = _create_thumbnail_image(
            generator,
            source_image,
            title,
            shape=shape,
            font_size=font_size if font_size > 0 else None,
            font_size_ratio=max(0.4, min(1.0, font_size_ratio)),
            text_position=text_position,
            border=(border.lower() == "true"),
            text_color=text_color,
            overlay_opacity=overlay_opacity,
            font_key=font_key,
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
        import traceback
        error_detail = f"파일 썸네일 생성 중 오류: {type(e).__name__}: {str(e)}"
        print(f"ERROR: {error_detail}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=error_detail)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8866,
        timeout_keep_alive=120,  # Keep-alive 타임아웃 2분
        limit_max_requests=10000  # 최대 요청 수
    )
