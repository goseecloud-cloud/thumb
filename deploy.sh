#!/bin/bash
# ═══════════════════════════════════════════════════
#  thumb.goseecloud.com 콘타보 서버 배포 스크립트
#  사용법: sudo bash deploy.sh
# ═══════════════════════════════════════════════════
set -e

DOMAIN="thumb.goseecloud.com"
EMAIL="your@email.com"   # ← 실제 이메일로 변경 필수!

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  썸네일 생성기 배포  |  $DOMAIN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── STEP 1: Docker 설치 ──────────────────────────
echo ""
echo "[1/5] Docker 확인..."
if ! command -v docker &>/dev/null; then
    echo "  → Docker 설치 중..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
fi
echo "  ✅ Docker $(docker --version | cut -d' ' -f3 | tr -d ',')"

# ── STEP 2: HTTPS 설정 임시 비활성화 ─────────────
echo ""
echo "[2/5] HTTP 모드로 준비..."
# SSL 인증서 없이 시작하기 위해 thumbnail.conf 잠시 비활성화
[ -f nginx/conf.d/thumbnail.conf ] && \
    mv nginx/conf.d/thumbnail.conf nginx/conf.d/thumbnail.conf.bak

# ── STEP 3: 앱 + Nginx 시작 ─────────────────────
echo ""
echo "[3/5] 컨테이너 시작..."
docker compose up -d --build app nginx
echo "  ✅ 앱 시작 완료"
sleep 5

# ── STEP 4: SSL 인증서 발급 ─────────────────────
echo ""
echo "[4/5] Let's Encrypt SSL 발급..."
docker compose run --rm certbot certonly \
    --webroot -w /var/www/certbot \
    --email "$EMAIL" \
    --agree-tos --no-eff-email \
    -d "$DOMAIN"
echo "  ✅ 인증서 발급 완료"

# ── STEP 5: HTTPS 전환 + 재시작 ─────────────────
echo ""
echo "[5/5] HTTPS 전환..."
rm -f nginx/conf.d/thumbnail-init.conf
[ -f nginx/conf.d/thumbnail.conf.bak ] && \
    mv nginx/conf.d/thumbnail.conf.bak nginx/conf.d/thumbnail.conf
docker compose up -d
echo "  ✅ HTTPS 전환 완료"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ 배포 완료!"
echo "  🌐 https://$DOMAIN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
docker compose ps
