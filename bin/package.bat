@echo off
echo.
echo [info] 打包Python專案，產生exe執行檔。
echo.

%~d0
cd %~dp0
call pyinstaller --add-data="../img;img" --version-file ../conf/app_version_info.txt -F -w -n WebService測試工具V1 -i ../img/favicon.ico  ../ws-tool.py

echo.
echo [info] 打包完成。
echo.

pause