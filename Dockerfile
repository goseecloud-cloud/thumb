# ════════════════════════════════════════════════════
# Stage 1 – 의존성 빌드
# ════════════════════════════════════════════════════
FROM python:3.12-slim AS builder

WORKDIR /build

# 빌드 도구 (C 확장 컴파일용)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ════════════════════════════════════════════════════
# Stage 2 – 런타임 (최소 이미지)
# ════════════════════════════════════════════════════
FROM python:3.12-slim

WORKDIR /app

# Pillow 런타임 의존 라이브러리 + curl (헬스체크용)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfreetype6 \
    libfontconfig1 \
    libjpeg62-turbo \
    libpng16-16 \
    libtiff6 \
    libwebp7 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Stage 1에서 설치된 패키지 복사
COPY --from=builder /install /usr/local

# ── 소스 복사 (불필요 파일 제외는 .dockerignore 참고) ──
COPY fastapi_server.py main.py index.html ./

# 폰트 (bak 파일 제외)
COPY fonts/Paperlogy-7Bold.ttf    fonts/
COPY fonts/GmarketSansBold.ttf    fonts/
COPY fonts/NanumGothicBold.ttf    fonts/
COPY fonts/NotoSansKR.ttf         fonts/

# output 디렉토리 (컨테이너 볼륨 마운트 포인트)
RUN mkdir -p /app/output

# 환경 변수
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Seoul

# 비루트 유저 (보안)
RUN groupadd -r app && useradd -r -g app app \
    && chown -R app:app /app
USER app

EXPOSE 8866

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8866/health || exit 1

# 프로덕션 실행 (--reload 제거, workers=2)
CMD ["uvicorn", "fastapi_server:app", \
     "--host", "0.0.0.0", \
     "--port", "8866", \
     "--workers", "2", \
     "--timeout-keep-alive", "120"]
