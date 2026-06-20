#!/bin/bash
# 서버에서 실행: sudo bash deploy/setup.sh
set -e

DEPLOY_DIR="/data/www/stock.mulsaem.net/data/v1"
NGINX_CONF="/etc/nginx/sites-available/stock.mulsaem.net"

echo "=== 1. 디렉토리 생성 ==="
mkdir -p "$DEPLOY_DIR/api"
mkdir -p "$DEPLOY_DIR/db"

echo "=== 2. pip 패키지 설치 (SQLite 변환용) ==="
pip3 install pandas numpy --quiet

echo "=== 3. CSV → SQLite 변환 (시간 소요) ==="
cd "$DEPLOY_DIR"
python3 convert_to_sqlite.py

echo "=== 4. 권한 설정 ==="
chown -R www-data:www-data "$DEPLOY_DIR"
chmod 644 "$DEPLOY_DIR/db/stocks.db"

echo "=== 5. PHP 설치 확인 ==="
php -v | head -1
# PHP-FPM 소켓 경로 자동 감지
FPM_SOCK=$(find /var/run/php -name "*.sock" 2>/dev/null | head -1)
echo "PHP-FPM 소켓: $FPM_SOCK"
if [ -n "$FPM_SOCK" ]; then
    sed -i "s|php8.1-fpm.sock|$(basename $FPM_SOCK)|g" "$DEPLOY_DIR/deploy/nginx.conf"
fi

echo "=== 6. nginx 설정 등록 ==="
cp "$DEPLOY_DIR/deploy/nginx.conf" "$NGINX_CONF"
ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/stock.mulsaem.net
nginx -t && systemctl reload nginx

echo ""
echo "✓ 완료 → https://stock.mulsaem.net/data/v1/"
echo "API 테스트: curl https://stock.mulsaem.net/data/v1/api/tickers | head -c 100"
