@echo off
cd /d "%~dp0"
if not exist mediamtx.exe (
  echo Downloading MediaMTX...
  curl -L -o mediamtx.zip https://github.com/bluenviron/mediamtx/releases/download/v1.21.1/mediamtx_v1.21.1_windows_amd64.zip
  tar -xf mediamtx.zip mediamtx.exe
  del mediamtx.zip
)
python -m pip install -q -r requirements.txt

rem Open firewall ports once (RTMP 1935, dashboard 8080, WebRTC 8889 + UDP 8189). Asks for admin.
netsh advfirewall firewall show rule name="DJI Stream Dashboard" >nul 2>&1
if errorlevel 1 (
  echo Adding Windows firewall rules - approve the admin prompt...
  powershell -NoProfile -Command "Start-Process cmd -Verb RunAs -WindowStyle Hidden -Wait -ArgumentList '/c netsh advfirewall firewall add rule name=\"DJI Stream Dashboard\" dir=in action=allow protocol=TCP localport=1935,8080,8889 & netsh advfirewall firewall add rule name=\"DJI Stream Dashboard\" dir=in action=allow protocol=UDP localport=8189'"
)

start "" http://localhost:8080
python app.py
pause
