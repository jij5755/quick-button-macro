@echo off
chcp 949 >nul
cd /d "%~dp0"
echo ============================================
echo  퀵버튼 매크로 - 안전 빌드
echo ============================================
echo.
tasklist /FI "IMAGENAME eq QuickButtonMacro.exe" | find /I "QuickButtonMacro.exe" >nul
if not errorlevel 1 (
    echo [중단] 퀵버튼 매크로가 실행 중입니다. 매크로 창(그리고 "이미 실행 중" 창)을 모두 닫고 다시 실행하세요.
    pause
    exit /b 1
)
set STAMP=%date:~0,4%%date:~5,2%%date:~8,2%-%time:~0,2%%time:~3,2%
set STAMP=%STAMP: =0%
set BK=프리셋백업\%STAMP%-빌드전
echo [1/3] 프리셋 백업 -^> %BK%
mkdir "%BK%" 2>nul
xcopy /E /I /Y "dist\QuickButtonMacro\presets" "%BK%\presets" >nul
if errorlevel 1 (
    echo [중단] 프리셋 백업 실패. 빌드하지 않습니다.
    pause
    exit /b 1
)
copy /Y "dist\QuickButtonMacro\preset_meta.json" "%BK%\" >nul
if exist "dist\QuickButtonMacro\jyor_link.json" copy /Y "dist\QuickButtonMacro\jyor_link.json" "%BK%\" >nul
echo [2/3] PyInstaller 빌드 (build\dist_new - 실행본 폴더는 건드리지 않음)
python -m PyInstaller QuickButtonMacro.spec --noconfirm --distpath build\dist_new
if errorlevel 1 (
    echo [중단] 빌드 실패. 실행본은 그대로입니다.
    pause
    exit /b 1
)
echo [3/3] 실행본에 exe + _internal 만 덮어쓰기 (프리셋 보존)
rmdir /S /Q "dist\QuickButtonMacro\_internal"
xcopy /E /I /Y "build\dist_new\QuickButtonMacro\_internal" "dist\QuickButtonMacro\_internal" >nul
copy /Y "build\dist_new\QuickButtonMacro\QuickButtonMacro.exe" "dist\QuickButtonMacro\QuickButtonMacro.exe" >nul
echo.
echo [완료] dist\QuickButtonMacro\QuickButtonMacro.exe 갱신. 프리셋 백업: %BK%
pause
