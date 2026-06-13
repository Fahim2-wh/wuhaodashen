@echo off
chcp 65001 >nul
cd /d %~dp0
echo ==========================================
echo    云筑天瞳 V9 一键启动正式软件包
echo ==========================================
echo.
where python >nul 2>nul
if errorlevel 1 (
  echo 未检测到 Python，请先安装 Python 3.9+
  pause
  exit /b 1
)
if not exist v9_env (
  echo 首次启动：正在创建本地运行环境 v9_env ...
  python -m venv v9_env
)
call v9_env\Scripts\activate.bat
python -c "import fastapi,uvicorn,multipart,PIL,reportlab,requests,cv2,numpy" >nul 2>nul
if errorlevel 1 (
  echo 正在安装运行依赖，首次启动需要几分钟...
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
)
echo.
echo 浏览器打开：http://127.0.0.1:8000
echo 默认账号：admin
echo 默认密码：admin123456
echo.
python run.py
pause
