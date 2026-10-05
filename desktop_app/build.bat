@echo off
cd /d "%~dp0"
if not exist mediamtx.exe (
  echo Downloading MediaMTX...
  curl -L -o mediamtx.zip https://github.com/bluenviron/mediamtx/releases/download/v1.21.1/mediamtx_v1.21.1_windows_amd64.zip
  tar -xf mediamtx.zip mediamtx.exe
  del mediamtx.zip
)
python -m pip install customtkinter pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name DJIStreamReceiver ^
  --collect-data customtkinter ^
  --add-binary "mediamtx.exe;." ^
  --add-data "mediamtx.yml;." ^
  --add-data "icon.ico;." --icon icon.ico ^
  dji_stream.py
echo.
echo Done: dist\DJIStreamReceiver.exe
pause
