#!/bin/bash
# 맥에서 실행: bash deploy/upload.sh
SERVER="220.95.232.15"
USER="${SERVER_USER:-optimsit}"
REMOTE="/data/www/stock.mulsaem.net/data/v1"
LOCAL="/Users/choids/Documents/Projects/Stock/Virtual StockMarket"

echo "→ $USER@$SERVER:$REMOTE"

ssh "$USER@$SERVER" "mkdir -p $REMOTE/api $REMOTE/db $REMOTE/deploy"

# 핵심 파일
scp "$LOCAL/dashboard.html"          "$USER@$SERVER:$REMOTE/"
scp "$LOCAL/api/index.php"           "$USER@$SERVER:$REMOTE/api/"
scp "$LOCAL/convert_to_sqlite.py"    "$USER@$SERVER:$REMOTE/"

# CSV (대용량 — 먼저 DB 있으면 생략 가능)
scp "$LOCAL/db/snp500_2018_2017_stock.csv" "$USER@$SERVER:$REMOTE/db/"

# 배포 스크립트
scp "$LOCAL/deploy/nginx.conf"        "$USER@$SERVER:$REMOTE/deploy/"
scp "$LOCAL/deploy/setup.sh"          "$USER@$SERVER:$REMOTE/deploy/"

echo ""
echo "=== 서버에서 실행 ==="
echo "  ssh $USER@$SERVER"
echo "  cd $REMOTE && sudo bash deploy/setup.sh"
