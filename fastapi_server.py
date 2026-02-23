from pathlib import Path
import io
import os
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image

from main import ThumbnailGenerator

app = FastAPI(
    title="썸네일 생성기 서비스",
    description="이미지 URL 또는 업로드 파일로 썸네일을 생성하는 서비스",
    version="2.0.0"
)

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")


class ThumbnailRequest(BaseModel):
    url: str
    title: str
    output_type: str = "local"  # 호환용 필드 (현재는 항상 local로 처리)


class ThumbnailResponse(BaseModel):
    success: bool
    message: str
    thumbnail_url: str | None = None
    local_path: str | None = None
    filename: str | None = None
    error: str | None = None


def _create_thumbnail_image(generator: ThumbnailGenerator, source_image: Image.Image, title: str) -> Image.Image:
    image = source_image
    if image.mode != "RGB":
        image = image.convert("RGB")

    image = generator.crop_to_square(image)
    image = generator.resize_image(image, generator.target_size)
    image = generator.apply_dark_overlay(image, generator.overlay_opacity)
    image = generator.add_border(image, generator.border_margin, generator.border_width)
    image = generator.add_text_overlay(image, title)
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
        message=f"{message_prefix} 로컬 파일로 저장되었습니다.",
        thumbnail_url=local_url,
        local_path=local_path,
        filename=filename
    )


@app.get("/service", response_class=HTMLResponse)
async def service_page():
    return """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>썸네일 생성 서비스</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 860px; margin: 40px auto; padding: 0 16px; }
    h1 { margin-bottom: 8px; }
    .card { border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin-top: 16px; }
    label { display: block; margin: 10px 0 6px; font-weight: 600; }
    input, select, textarea, button { width: 100%; padding: 10px; box-sizing: border-box; }
    button { margin-top: 12px; cursor: pointer; }
    #result { margin-top: 20px; }
    img { max-width: 100%; border-radius: 8px; border: 1px solid #ccc; }
    .muted { color: #666; font-size: 14px; }
  </style>
</head>
<body>
  <h1>썸네일 생성 서비스</h1>
  <p class="muted">URL을 붙여넣거나 파일을 업로드해 썸네일을 생성할 수 있습니다.</p>

  <div class="card">
    <h3>1) URL로 생성</h3>
    <label for="url">이미지 URL</label>
    <input id="url" type="url" placeholder="https://example.com/image.jpg" />

    <label for="urlTitle">제목</label>
    <textarea id="urlTitle" rows="2" placeholder="썸네일 제목"></textarea>

    <button onclick="generateFromUrl()">URL로 생성</button>
  </div>

  <div class="card">
    <h3>2) 파일 업로드로 생성</h3>
    <label for="file">이미지 파일</label>
    <input id="file" type="file" accept="image/*" />

    <label for="fileTitle">제목</label>
    <textarea id="fileTitle" rows="2" placeholder="썸네일 제목"></textarea>

    <button onclick="generateFromFile()">파일로 생성</button>
  </div>

  <div id="result" class="card" style="display:none;"></div>

  <script>
    function renderResult(data) {
      const result = document.getElementById('result');
      result.style.display = 'block';
      if (!data.success) {
        result.innerHTML = `<h3>오류</h3><pre>${JSON.stringify(data, null, 2)}</pre>`;
        return;
      }
      result.innerHTML = `
        <h3>생성 완료</h3>
        <p><strong>메시지:</strong> ${data.message}</p>
        <p><strong>파일명:</strong> ${data.filename || '-'}</p>
        <p><strong>URL:</strong> <a href="${data.thumbnail_url}" target="_blank">${data.thumbnail_url}</a></p>
        <img src="${data.thumbnail_url}" alt="thumbnail" />
      `;
    }

    async function generateFromUrl() {
      const url = document.getElementById('url').value.trim();
      const title = document.getElementById('urlTitle').value.trim();
      const res = await fetch('/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, title })
      });
      const data = await res.json();
      renderResult(data);
    }

    async function generateFromFile() {
      const file = document.getElementById('file').files[0];
      const title = document.getElementById('fileTitle').value.trim();
      const form = new FormData();
      form.append('file', file);
      form.append('title', title);

      const res = await fetch('/generate-file', { method: 'POST', body: form });
      const data = await res.json();
      renderResult(data);
    }
  </script>
</body>
</html>
"""


@app.get("/api")
async def api_info():
    return {
        "message": "썸네일 생성기 API",
        "version": "2.0.0",
        "endpoints": {
            "POST /generate": "URL로 썸네일 생성(JSON)",
            "POST /generate-file": "파일 업로드로 썸네일 생성(multipart/form-data)",
            "GET /health": "서버 상태 확인"
        }
    }


@app.get("/")
async def root():
    return {
        "message": "썸네일 생성기 API",
        "version": "2.0.0",
        "endpoints": {
            "POST /generate": "썸네일 생성 (기존 n8n 호환)",
            "POST /generate-file": "파일 업로드 썸네일 생성",
            "POST /generate-external": "(호환) 현재 local 파일 생성으로 처리",
            "GET /service": "고객용 웹 UI",
            "GET /health": "서버 상태 확인"
        }
    }


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
    output_type: str = Form("local")
):
    if not title.strip():
        raise HTTPException(status_code=400, detail="title은 필수입니다.")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드할 수 있습니다.")

    try:
        file_bytes = await file.read()
        source_image = Image.open(io.BytesIO(file_bytes)).convert("RGB")

        generator = ThumbnailGenerator()
        image = _create_thumbnail_image(generator, source_image, title)
        return _finalize_response(
            request,
            generator,
            image,
            message_prefix="업로드 파일로 썸네일이 성공적으로 생성되었습니다."
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 썸네일 생성 중 오류가 발생했습니다: {e}")


@app.post("/generate-external", response_model=ThumbnailResponse)
async def generate_thumbnail_external_only(payload: ThumbnailRequest, request: Request):
    payload.output_type = "local"
    return await generate_thumbnail_by_url(payload, request)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8866)