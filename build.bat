@echo off
cd /d "%~dp0"

rem Resolve uv's full path with "where"; running "uv" directly can fail when PATH contains a stray quote.
set "UV="
for /f "delims=" %%i in ('where uv.exe 2^>nul') do if not defined UV set "UV=%%i"
if not defined UV (
    echo [ERROR] uv not found. Install it first: https://docs.astral.sh/uv/
    pause
    exit /b 1
)
echo Using uv: %UV%

echo Closing any running WebService-Tool.exe process...
taskkill /f /im WebService-Tool.exe >nul 2>&1
echo Waiting for process to terminate...
"%SystemRoot%\System32\timeout.exe" /t 2 /nobreak >nul 2>&1

echo.
echo Cleaning up previous build directories...
if exist "build" (
    echo Removing build directory...
    rmdir /s /q build
)
echo.

echo Syncing Python environment (uv sync)...
"%UV%" sync
if errorlevel 1 (
    echo [ERROR] uv sync failed.
    pause
    exit /b 1
)
echo.

echo Building WebService-Tool...

"%UV%" run pyinstaller --clean --noconfirm --log-level=WARN --icon=assets/app_icon.ico --add-data "assets;assets" --version-file src\config\file_version_info.txt -F -w -n WebService-Tool src\ws_tool.py
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo Build process finished: dist\WebService-Tool.exe
pause
