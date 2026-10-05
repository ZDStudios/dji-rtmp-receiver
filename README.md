# DJI RTMP Stream Receiver

Two ways to receive your DJI controller's live feed over home wifi (RTMP in, low-latency WebRTC out, via MediaMTX).

## In the DJI app (both versions)
Live Streaming -> **RTMP** (custom) and enter:
- RTMP address: `rtmp://<PC-IP>:1935/live`  (shown in the app)
- Stream key: `drone` (or whatever you set)

Some DJI apps want one combined URL - use `rtmp://<PC-IP>:1935/live/drone`.
The PC and controller must be on the same wifi.

## Version 1 - desktop_app (.exe)
- Run `dist\DJIStreamReceiver.exe` (MediaMTX is bundled inside).
- First launch asks for admin once to add the firewall rule (TCP 1935, 8889; UDP 8189).
- Click **View Stream** to open `http://localhost:8889/live/<key>` in your browser.
- Rebuild: double-click `build.bat`, or run:
  `python -m PyInstaller --noconfirm --onefile --windowed --name DJIStreamReceiver --collect-data customtkinter --add-binary "mediamtx.exe;." --add-data "mediamtx.yml;." dji_stream.py`

## Version 2 - web_dashboard
- Double-click `run.bat` (installs Flask, adds firewall rules once, opens http://localhost:8080).
- Other devices on your wifi: open the "network URL" shown on the dashboard.

## Test without the drone (needs ffmpeg)
`ffmpeg -re -f lavfi -i testsrc2=size=1280x720:rate=30 -c:v libx264 -preset ultrafast -tune zerolatency -g 30 -pix_fmt yuv420p -f flv rtmp://127.0.0.1:1935/live/drone`

## DJI RC 2 notes
- DJI Fly 1.16+ won't start a livestream on the RC 2 without a microphone - connect any Bluetooth/USB-C mic or earbuds first.
- DJI Fly may join address + key without a `/` (stream arrives as `/livedrone`); both apps detect the stream on any path.
