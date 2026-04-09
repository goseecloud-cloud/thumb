#!/bin/bash
# ═══════════════════════════════════════════════════
#  thumb.goseecloud.com 콘타보 서버 배포 스크립트
#  (기존 nginx 사용 버전)
#  사용법: sudo bash deploy.sh
# ═══════════════════════════════════════════════════
set -e

DOMAIN="thumb.goseecloud.com"
EMAIL="your@email.com"   # ← 실제 이메일로 변경 필수!

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  썸네일 생성기 배포  |  $DOMAIN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── STEP 1: Docker 설치 확인 ─────────────────────
echo ""
echo "[1/5] Docker 확인..."
if ! command -v docker &>/dev/null; then
    echo "  → Docker 설치 중..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
fi
echo "  ✅ Docker $(docker --version | cut -d' ' -f3 | tr -d ',')"

# ── STEP 2: nginx 설정 복사 ──────────────────────
echo ""
echo "[2/5] nginx 설정 적용..."
cp nginx/thumb.goseecloud.com.conf /etc/nginx/sites-available/thumb.goseecloud.com

# 심볼릭 링크 (없으면 생성)
if [ ! -f /etc/nginx/sites-enabled/thumb.goseecloud.com ]; then
    ln -s /etc/nginx/sites-available/thumb.goseecloud.com \
          /etc/nginx/sites-enabled/thumb.goseecloud.com
fi

# SSL 설정 블록 임시 제거 (인증서 없으면 nginx -t 실패하므로)
sed '/listen 443/,/^}/d' /etc/nginx/sites-available/thumb.goseecloud.com \
    > /tmp/thumb_http_only.conf
cp /tmp/thumb_http_only.conf /etc/nginx/sites-available/thumb.goseecloud.com

nginx -t && systemctl reload nginx
echo "  ✅ nginx 설정 적용 완료 (HTTP)"

# ── STEP 3: SSL 인증서 발급 ──────────────────────
echo ""
echo "[3/5] Let's Encrypt SSL 발급..."
if ! command -v certbot &>/dev/null; then
    apt-get install -y certbot python3-certbot-nginx
fi

certbot certonly --nginx \
    -d "$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos --no-eff-email --non-interactive
echo "  ✅ SSL 인증서 발급 완료"

# ── STEP 4: HTTPS nginx 설정으로 교체 ────────────
echo ""
echo "[4/5] HTTPS 설정 적용..."
cp nginx/thumb.goseecloud.com.conf /etc/nginx/sites-available/thumb.goseecloud.com
nginx -t && systemctl reload nginx
echo "  ✅ HTTPS 설정 적용 완료"

# ── STEP 5: Docker 앱 시작 ───────────────────────
echo ""
echo "[5/5] Docker 앱 시작..."
docker compose up -d --build
echo "  ✅ 앱 시작 완료"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ 배포 완료!"
echo "  🌐 https://$DOMAIN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
docker compose ps
