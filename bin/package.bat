@echo off
echo.
echo [信息] 打包Python项目，生成exe文件。
echo.

%~d0
cd %~dp0
call pyinstaller --add-data="../img;img" --version-file ../conf/app_version_info.txt -F -w -n WebService测试工具V1 -i ../img/favicon.ico  ../ws-tool.py

echo.
echo [信息] 打包完成。
echo.

pause