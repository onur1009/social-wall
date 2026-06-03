@echo off
chcp 65001 >nul
title Social Wall v2 -- Baslatiliyor
set PYTHONUTF8=1

echo.
echo  ============================================
echo       Social Wall v2 - 7 Platform Canli Duvar
echo       Twitter  Instagram  Reddit  TikTok
echo       Facebook LinkedIn   Haberler
echo  ============================================
echo.

:: Python ve venv kontrol et
set VENV_DIR=%~dp0backend\.venv
set PYTHON_EXE=%VENV_DIR%\Scripts\python.exe

if not exist "%PYTHON_EXE%" (
    echo  [1/3] Python ortami kuruluyor...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo  HATA: Python bulunamadi! Python 3.10+ yukleyin.
        pause
        exit /b 1
    )
)

:: Bagimlilikları yukle
echo  [2/3] Bagimliliklar kontrol ediliyor...
"%VENV_DIR%\Scripts\pip.exe" install -q -r "%~dp0backend\requirements.txt"
if errorlevel 1 (
    echo  HATA: Bagimliliklar yuklenemedi!
    pause
    exit /b 1
)

:: xpoz kurulu mu kontrol et
"%PYTHON_EXE%" -c "import xpoz" 2>nul
if errorlevel 1 (
    echo  [+] xpoz SDK kuruluyor...
    "%VENV_DIR%\Scripts\pip.exe" install -q xpoz
)

:: Backend'i baslat (arka planda)
echo  [3/3] API sunucusu baslatiliyor (port 8765)...
start "Social Wall API v2" /min "%PYTHON_EXE%" "%~dp0backend\main.py"

:: 2 saniye bekle
timeout /t 2 /nobreak >nul

:: Frontend'i varsayilan tarayicide ac
echo.
echo  ✅ Social Wall v2 hazir!
echo  🌐 API:      http://127.0.0.1:8765
echo  📺 Frontend: %~dp0frontend\index.html
echo  📋 Platformlar: Twitter, Instagram, Reddit, TikTok, News, Facebook, LinkedIn
echo.
start "" "%~dp0frontend\index.html"

echo  Kapatmak icin bu pencereyi kapatin.
echo  (API sunucusu arka planda calismaya devam eder)
echo.
pause
