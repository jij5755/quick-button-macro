@echo off
chcp 949 >nul
cd /d "%~dp0"
echo ============================================
echo  ����ư ��ũ�� - ���� ����
echo ============================================
echo.
tasklist /FI "IMAGENAME eq QuickButtonMacro.exe" | find /I "QuickButtonMacro.exe" >nul
if not errorlevel 1 (
    echo [�ߴ�] ����ư ��ũ�ΰ� ���� ���Դϴ�. ��ũ�� â(�׸��� "�̹� ���� ��" â)�� ��� �ݰ� �ٽ� �����ϼ���.
    pause
    exit /b 1
)
set STAMP=%date:~0,4%%date:~5,2%%date:~8,2%-%time:~0,2%%time:~3,2%
set STAMP=%STAMP: =0%
set BK=�����¹��\%STAMP%-������
echo [1/3] ������ ��� -^> %BK%
mkdir "%BK%" 2>nul
xcopy /E /I /Y "dist\QuickButtonMacro\presets" "%BK%\presets" >nul
if errorlevel 1 (
    echo [�ߴ�] ������ ��� ����. �������� �ʽ��ϴ�.
    pause
    exit /b 1
)
copy /Y "dist\QuickButtonMacro\preset_meta.json" "%BK%\" >nul
if exist "dist\QuickButtonMacro\jyor_link.json" copy /Y "dist\QuickButtonMacro\jyor_link.json" "%BK%\" >nul
if exist "dist\QuickButtonMacro\images" xcopy /E /I /Y "dist\QuickButtonMacro\images" "%BK%\images" >nul
echo [2/3] PyInstaller ���� (build\dist_new - ���ົ ������ �ǵ帮�� ����)
python -m PyInstaller QuickButtonMacro.spec --noconfirm --distpath build\dist_new
if errorlevel 1 (
    echo [�ߴ�] ���� ����. ���ົ�� �״���Դϴ�.
    pause
    exit /b 1
)
echo [3/3] ���ົ�� exe + _internal �� ����� (������ ����)
rmdir /S /Q "dist\QuickButtonMacro\_internal"
xcopy /E /I /Y "build\dist_new\QuickButtonMacro\_internal" "dist\QuickButtonMacro\_internal" >nul
copy /Y "build\dist_new\QuickButtonMacro\QuickButtonMacro.exe" "dist\QuickButtonMacro\QuickButtonMacro.exe" >nul
echo.
echo [�Ϸ�] dist\QuickButtonMacro\QuickButtonMacro.exe ����. ������ ���: %BK%
pause
