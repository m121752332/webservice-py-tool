@echo off
echo.
echo [��Ϣ] ���Python��Ŀ������exe�ļ���
echo.

%~d0
cd %~dp0
call pyinstaller --add-data="../img;img" --version-file ../conf/app_version_info.txt -F -w -n WebService���Թ���V1 -i ../img/favicon.ico  ../ws-tool.py

echo.
echo [��Ϣ] �����ɡ�
echo.

pause