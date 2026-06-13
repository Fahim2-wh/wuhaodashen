#!/bin/bash
cd "$(dirname "$0")"

clear
echo "=========================================="
echo "        云筑天瞳 V9 正式展示启动"
echo "=========================================="
echo ""
echo "正在关闭旧的 8000 端口服务..."

PID=$(lsof -ti :8000)
if [ ! -z "$PID" ]; then
  kill -9 $PID
  sleep 1
fi

echo "正在检查运行环境..."

# 如果环境不存在，重新创建
if [ ! -d "v9_env" ]; then
  echo "未发现 v9_env，正在创建..."
  python3 -m venv v9_env
fi

# 修复 pip
./v9_env/bin/python -m ensurepip --upgrade
./v9_env/bin/python -m pip install --upgrade pip

echo "正在安装/检查依赖..."
./v9_env/bin/python -m pip install -r "02_系统源码/requirements.txt"

# 可选安装 ultralytics，保证真实 YOLO 可用
./v9_env/bin/python -m pip install ultralytics

# 修复整理后路径：让源码目录能找到模型、数据和.env
cd "02_系统源码"

if [ ! -e "models" ]; then
  ln -s "../03_AI模型/models" "models"
fi

if [ ! -e "data" ]; then
  ln -s "../04_运行数据/data" "data"
fi

if [ ! -e ".env" ] && [ -e "../.env" ]; then
  ln -s "../.env" ".env"
fi

echo ""
echo "启动成功后，请在浏览器打开："
echo "http://127.0.0.1:8000"
echo ""
echo "账号：admin"
echo "密码：admin123456"
echo ""
echo "正在启动网站..."

sleep 2
open http://127.0.0.1:8000

../v9_env/bin/python run.py

echo ""
echo "网站已停止，按回车关闭窗口..."
read
