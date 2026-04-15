@echo off
chcp 65001 >nul
cd /d %~dp0

echo ------------------------------------------
echo 正在启动 飞书推送引擎...
echo ------------------------------------------

E:\MacroGodEye\venv\Scripts\python.exe monitor_feishu.py

echo.
echo ==========================================
timeout /t 5
