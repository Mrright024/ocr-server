#!/bin/bash
set -euo pipefail

DEPLOY_DIR="${1:-$(pwd)}"
SERVICE_NAME="ocr-server"
SERVICE_USER="$(whoami)"
SERVICE_GROUP="$(id -gn)"

echo "=== OCR Server 部署 ==="
echo "部署目录: $DEPLOY_DIR"

# 1. venv + 依赖
echo "[1/3] 安装依赖..."
if [ ! -f "$DEPLOY_DIR/.venv/bin/python3" ]; then
    python3 -m venv "$DEPLOY_DIR/.venv"
fi
"$DEPLOY_DIR/.venv/bin/pip" install --upgrade pip
"$DEPLOY_DIR/.venv/bin/pip" install -r "$DEPLOY_DIR/requirements.txt"

# 2. systemd
echo "[2/3] 注册 systemd..."
sed -e "s|{{DEPLOY_DIR}}|$DEPLOY_DIR|g" \
    -e "s|{{SERVICE_USER}}|$SERVICE_USER|g" \
    -e "s|{{SERVICE_GROUP}}|$SERVICE_GROUP|g" \
    "$DEPLOY_DIR/ocr-server.service" | sudo tee /etc/systemd/system/ocr-server.service > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable ocr-server
sudo systemctl restart ocr-server

# 3. 验证
echo "[3/3] 验证..."
sleep 5
echo ""
echo "健康检查: $(curl -s http://127.0.0.1:1224/health || echo '未响应')"
echo "服务信息: $(curl -s http://127.0.0.1:1224/info || echo '未响应')"
echo ""
echo "=== 部署完成 ==="
echo "  systemctl status ocr-server"
echo "  journalctl -u ocr-server -f"
