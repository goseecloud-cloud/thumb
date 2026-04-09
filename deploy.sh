#!/bin/bash
# ─────────────────────────────────────────────────────────────
# thumb.goseecloud.com 콘타보 서버 배포 스크립트
# 사용법: bash deploy.sh
# ─────────────────────────────────────────────────────────────

set -e  # 에러 발생 시 즉시 종료

DOMAIN="thumb.goseecloud.com"
EMAIL="your@email.com"  # ← 실제 이메일로 변경

echo "======================================"
echo "  썸네일 생성기 배포 시작"
echo "  도메인: $DOMAIN"
echo "======================================"

# ── 1단계: Docker & Docker Compose 설치 확인 ──
echo ""
echo "[1/5] Docker 설치 확인..."
if ! command -v docker &> /dev/null; then
    echo "Docker 설치 중..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

if ! command -v docker compose &> /dev/null; then
    echo "Docker Compose 설치 중..."
    apt-get update && apt-get install -y docker-compose-plugin
fi

echo "  ✅ Docker 준비 완료"

# ── 2단계: 필요한 디렉토리 생성 ──
echo ""
echo "[2/5] 디렉토리 준비..."
mkdir -p nginx/conf.d nginx/ssl output
echo "  ✅ 디렉토리 준비 완료"

# ── 3단계: SSL 인증서 발급 전 임시 설정으로 앱 시작 ──
echo ""
echo "[3/5] 앱 시작 (HTTP 모드)..."

# HTTPS 설정 파일 임시 비활성화
if [ -f nginx/conf.d/thumbnail.conf ]; then
    mv nginx/conf.d/thumbnail.conf nginx/conf.d/thumbnail.conf.disabled
fi

# 임시 HTTP 설정으로 시작
docker compose up -d thumbnail-app nginx
sleep 5

echo "  ✅ 앱 시작 완료"

# ── 4단계: Let's Encrypt SSL 인증서 발급 ──
echo ""
echo "[4/5] SSL 인증서 발급..."

docker compose run --rm certbot certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN"

echo "  ✅ SSL 인증서 발급 완료"

# ── 5단계: HTTPS 설정으로 교체 후 재시작 ──
echo ""
echo "[5/5] HTTPS 모드로 전환..."

# 임시 설정 제거, HTTPS 설정 활성화
rm -f nginx/conf.d/thumbnail-init.conf
if [ -f nginx/conf.d/thumbnail.conf.disabled ]; then
    mv nginx/conf.d/thumbnail.conf.disabled nginx/conf.d/thumbnail.conf
fi

# 전체 재시작
docker compose up -d

echo ""
echo "======================================"
echo "  ✅ 배포 완료!"
echo "  URL: https://$DOMAIN"
echo "======================================"

# 상태 확인
echo ""
echo "컨테이너 상태:"
docker compose ps
