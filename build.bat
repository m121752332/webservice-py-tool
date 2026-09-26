@echo off
cd /d "%~dp0"
setlocal EnableDelayedExpansion

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

echo Collecting hidden imports for the settings editor plugin...
if not exist "plugins\settings_editor\host_imports.txt" (
    echo [ERROR] plugins\settings_editor\host_imports.txt not found. Run: uv run python plugins\settings_editor\gen_host_imports.py
    pause
    exit /b 1
)
set "HIDDEN="
for /f "usebackq eol=# delims=" %%m in ("plugins\settings_editor\host_imports.txt") do set "HIDDEN=!HIDDEN! --hidden-import=%%m"

echo Building WebService-Tool...

"%UV%" run pyinstaller --clean --noconfirm --log-level=WARN --icon=assets/app_icon.ico --add-data "assets;assets" --version-file src\config\file_version_info.txt -F -w -n WebService-Tool !HIDDEN! src\ws_tool.py
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo Building settings editor plugin...
"%UV%" run python plugins\settings_editor\build_plugin.py
if errorlevel 1 (
    echo.
    echo [ERROR] Plugin build failed.
    pause
    exit /b 1
)

echo.
echo Copying app_data\ws_tool.yaml into dist (always overwritten to match repo)...
if not exist "dist\app_data" mkdir "dist\app_data"
copy /y "src\app_data\ws_tool.yaml" "dist\app_data\ws_tool.yaml" >nul
if errorlevel 1 (
    echo [ERROR] Failed to copy ws_tool.yaml.
    pause
    exit /b 1
)

echo.
echo Build process finished: dist\WebService-Tool.exe + dist\plugins\settings_editor + dist\app_data\ws_tool.yaml
pause
