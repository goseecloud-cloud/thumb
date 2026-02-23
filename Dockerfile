# Python 3.12 베이스 이미지 사용
FROM python:3.12-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 설치 (pip 업그레이드 포함)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 애플리케이션 파일 복사
COPY . .

# fonts 디렉토리가 없으면 생성
RUN mkdir -p /app/fonts

# output 디렉토리 생성
RUN mkdir -p /app/output

# 포트 노출
EXPOSE 8866

# 헬스체크 추가
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8866/health || exit 1

# FastAPI 서버 실행
CMD ["uvicorn", "fastapi_server:app", "--host", "0.0.0.0", "--port", "8866", "--reload"]