#!/bin/bash
cd "$(dirname "$0")"
clear
echo "云筑天瞳 V9：安装真实YOLO识别环境"
echo "说明：这一步会安装 ultralytics、torch 等依赖，可能需要较长时间。"
if [ ! -d "v9_env" ]; then
  python3 -m venv v9_env
fi
source v9_env/bin/activate
python -m pip install --upgrade pip
python -m pip install ultralytics==8.4.62 || python -m pip install ultralytics==8.4.62 -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
echo "安装完成。把模型文件放到 models/site_safety.pt 后，重新启动网站即可。"
read -p "按回车退出..."
