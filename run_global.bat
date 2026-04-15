@echo off
chcp 65001 >nul
cd /d %~dp0

echo ------------------------------------------
echo 正在启动 全球周期罗盘...
echo ------------------------------------------

E:\MacroGodEye\venv\Scripts\python.exe monitor_global.py

echo.
echo ==========================================
pause
