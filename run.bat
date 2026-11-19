@echo off
rem CalcEclipses 一键启动（Windows）
rem   1. 检查本地 Cesium，缺失则调用 tools\fetch_cesium.ps1 获取（约 20MB，一次性）
rem   2. 起本地静态服务（端口 8123）
rem   3. 自动打开浏览器
rem 停止：关闭本窗口或 Ctrl+C
setlocal
cd /d "%~dp0"

rem ── Python ──
set PY=
where python >nul 2>nul && set PY=python
if not defined PY (
    where py >nul 2>nul && set PY=py
)
if not defined PY (
    echo [run.bat] 未找到 Python，请先安装：https://www.python.org/downloads/
    pause
    exit /b 1
)

rem ── Cesium ──
if not exist lib\cesium\Cesium.js (
    echo [run.bat] 首次运行：获取本地 Cesium（约 20MB）...
    where npm >nul 2>nul
    if errorlevel 1 (
        echo [run.bat] 需要 npm（Node.js）来获取 Cesium：https://nodejs.org/
        pause
        exit /b 1
    )
    powershell -NoProfile -ExecutionPolicy Bypass -File tools\fetch_cesium.ps1
    if errorlevel 1 (
        echo [run.bat] Cesium 获取失败，请检查网络后重试
        pause
        exit /b 1
    )
)

rem ── 延迟开浏览器（等服务就绪），服务前台运行 ──
start "" /min cmd /c "timeout /t 2 /nobreak >nul & start "" http://127.0.0.1:8123/"

echo [run.bat] 服务已启动：http://127.0.0.1:8123/ （关闭本窗口即停止）
%PY% -m http.server 8123 --bind 127.0.0.1
