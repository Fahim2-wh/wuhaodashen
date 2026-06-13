#!/bin/bash
cd "$(dirname "$0")"
clear
echo "=========================================="
echo "   云筑天瞳 V9 一键启动正式软件包"
echo "=========================================="
echo ""
if ! command -v python3 >/dev/null 2>&1; then
  echo "未检测到 Python3，请先安装 Python 3.9+"
  read -p "按回车退出..."
  exit 1
fi
if [ ! -d "v9_env" ]; then
  echo "首次启动：正在创建本地运行环境 v9_env ..."
  python3 -m venv v9_env
fi
source v9_env/bin/activate
python - <<'CHECK_DEPS'
mods = ['fastapi','uvicorn','multipart','PIL','reportlab','requests','cv2','numpy']
missing=[]
for m in mods:
    try:
        __import__(m)
    except Exception:
        missing.append(m)
if missing:
    raise SystemExit(1)
CHECK_DEPS
if [ $? -ne 0 ]; then
  echo "正在安装运行依赖，首次启动需要几分钟..."
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt || python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
fi
echo ""
echo "启动成功后，请在浏览器打开："
echo "http://127.0.0.1:8000"
echo ""
echo "默认账号：admin"
echo "默认密码：admin123456"
echo ""
echo "手机访问：Mac和手机在同一热点/Wi-Fi下，用 http://Mac局域网IP:8000"
echo "关闭网站：回到本窗口按 Control + C"
echo ""
python run.py
read -p "网站已停止，按回车关闭窗口..."
