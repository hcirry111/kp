@echo off
setlocal
cd /d "%~dp0"
echo Installing build dependencies...
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed.
  pause
  exit /b 1
)
echo Building SwiftMacro Pro.exe...
py -m PyInstaller --noconfirm --clean --onefile --windowed --name SwiftMacroPro swiftmacro_pro.py
if errorlevel 1 (
  echo Build failed. See the messages above.
  pause
  exit /b 1
)
echo.
echo Finished: dist\SwiftMacroPro.exe
pause
