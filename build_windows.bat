@echo off
REM ============================================================
REM Windows 一键打包脚本 — 出 dist\SubtitleTranslator\SubtitleTranslator.exe
REM 然后压缩成 SubtitleTranslator-<version>-Windows-x64.zip
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM 读取版本
set /p VERSION=<VERSION
if "%VERSION%"=="" set VERSION=0.1.0

echo.
echo ==^> 字幕生成翻译器 v%VERSION% Windows 打包
echo.

REM 检查 Python
where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 Python,请先安装 Python 3.10+
    exit /b 1
)

REM 创建/激活 venv
if not exist .venv (
    echo ==^> 首次运行,创建虚拟环境...
    python -m venv .venv
)
call .venv\Scripts\activate.bat

echo ==^> 升级 pip 与依赖
python -m pip install --upgrade pip wheel setuptools
python -m pip install -r requirements.txt

echo ==^> 装 PyInstaller
python -m pip install --upgrade "pyinstaller>=6.0"

echo ==^> 生成图标
python assets\generate_icon.py 2>nul

echo ==^> 清理旧构建
if exist build rd /s /q build
if exist dist rd /s /q dist

echo ==^> PyInstaller 开始打包
pyinstaller SubtitleTranslator.spec --clean --noconfirm
if errorlevel 1 (
    echo [失败] PyInstaller 出错
    exit /b 1
)

REM 重命名输出并压缩
set DIST_DIR=dist\SubtitleTranslator
if not exist "%DIST_DIR%" (
    echo [失败] 未找到 %DIST_DIR%
    exit /b 1
)

set ZIP_NAME=SubtitleTranslator-%VERSION%-Windows-x64.zip
echo ==^> 压缩为 %ZIP_NAME%
powershell -Command "Compress-Archive -Path '%DIST_DIR%' -DestinationPath 'dist\%ZIP_NAME%' -Force"

echo.
echo ============================================================
echo  ^✅  打包完成!
echo.
echo  产物:
echo    dist\SubtitleTranslator\SubtitleTranslator.exe   (直接运行)
echo    dist\%ZIP_NAME%   (分发给其他用户)
echo.
echo  提示: 终端用户仍需自己装 FFmpeg 到 PATH
echo  下载: https://www.gyan.dev/ffmpeg/builds/
echo ============================================================
echo.
pause
