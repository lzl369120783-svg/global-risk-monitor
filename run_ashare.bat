@echo off
chcp 65001 >nul
cd /d %~dp0

echo ------------------------------------------
echo 正在启动 A股风控雷达...
echo ------------------------------------------

E:\MacroGodEye\venv\Scripts\python.exe monitor_ashare.py

echo.
echo ==========================================
pause
