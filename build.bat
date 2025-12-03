@echo off
echo Closing any running WebService-Tool.exe process...
taskkill /f /im WebService-Tool.exe >nul 2>&1
echo Waiting for process to terminate...
timeout /t 2 /nobreak >nul

echo.
echo Cleaning up previous build directories...
if exist "build" (
    echo Removing build directory...
    rmdir /s /q build
)
echo.

echo Building WebService-Tool...

pyinstaller --clean --log-level=DEBUG --icon=assets/app_icon.ico --add-data "assets;assets" --version-file src\config\file_version_info.txt -F -w -n WebService-Tool -i src\img\favicon.ico src\ws_tool.py


echo.
echo Build process finished.
pause
