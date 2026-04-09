# ────────────────────────────────────────────
# Stage 1: 빌드 스테이지 (fonttools 컴파일 등)
# ────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# 빌드에 필요한 패키지
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# requirements 먼저 복사해서 레이어 캐시 활용
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ────────────────────────────────────────────
# Stage 2: 런타임 스테이지 (최소 이미지)
# ────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Pillow 이미지 처리에 필요한 시스템 라이브러리
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfreetype6 \
    libfontconfig1 \
    libjpeg62-turbo \
    libpng16-16 \
    libtiff6 \
    libwebp7 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 빌드 스테이지에서 설치된 Python 패키지 복사
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 앱 소스 복사 (output 제외)
COPY fastapi_server.py .
COPY main.py .
COPY index.html .
COPY fonts/ ./fonts/

# output 디렉토리 생성 (볼륨으로 마운트되므로 빈 폴더만)
RUN mkdir -p /app/output

# 포트 노출
EXPOSE 8866

# 환경변수
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Seoul

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8866/health || exit 1

# 비루트 유저 생성 (보안)
RUN groupadd -r appuser && useradd -r -g appuser appuser && \
    chown -R appuser:appuser /app
USER appuser

# 프로덕션 서버 실행 (--reload 제거, workers 설정)
CMD ["uvicorn", "fastapi_server:app", \
     "--host", "0.0.0.0", \
     "--port", "8866", \
     "--workers", "2", \
     "--timeout-keep-alive", "120", \
     "--access-log", \
     "--log-level", "info"]
