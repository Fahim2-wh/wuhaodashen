#!/bin/bash
cd "$(dirname "$0")"

clear
echo "=========================================="
echo "      云筑天瞳｜比赛展示一键启动"
echo "=========================================="
echo ""
echo "正在检查 8000 端口..."

PID=$(lsof -ti :8000)
if [ ! -z "$PID" ]; then
  echo "发现旧服务，占用端口 PID: $PID"
  echo "正在关闭旧服务..."
  kill -9 $PID
  sleep 1
fi

echo "正在启用运行环境..."
source v9_env/bin/activate

echo "正在启动云筑天瞳平台..."
echo ""
echo "浏览器即将打开：http://127.0.0.1:8000"
echo "账号：admin"
echo "密码：admin123456"
echo ""

sleep 2
open http://127.0.0.1:8000

python3 run.py

echo ""
echo "网站已停止，按回车关闭窗口..."
read
