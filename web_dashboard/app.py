"""DJI Stream Receiver - web dashboard.

Starts MediaMTX and serves a dashboard at http://localhost:8080 (also on
your LAN) with the RTMP address, stream key, status and a live player.
"""
import atexit
import json
import os
import socket
import subprocess
import urllib.request

from flask import Flask, jsonify, request, send_from_directory

HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(HERE, "settings.json")
DASHBOARD_PORT = 8080
RTMP_PORT = 1935
WEBRTC_PORT = 8889
API = "http://127.0.0.1:9997"

app = Flask(__name__)
mediamtx = None


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def load_key():
    try:
        with open(SETTINGS_FILE) as f:
            return json.load(f).get("stream_key", "drone")
    except (OSError, ValueError):
        return "drone"


def api_get(path):
    try:
        with urllib.request.urlopen(API + path, timeout=1) as r:
            return json.load(r)
    except Exception:
        return None


def start_mediamtx():
    global mediamtx
    # A MediaMTX left over from a previous run would hold the ports and make ours exit.
    subprocess.run(["taskkill", "/F", "/IM", "mediamtx.exe"], capture_output=True)
    mediamtx = subprocess.Popen(
        [os.path.join(HERE, "mediamtx.exe"), os.path.join(HERE, "mediamtx.yml")],
        cwd=HERE, creationflags=0x08000000,  # CREATE_NO_WINDOW
    )


@atexit.register
def stop_mediamtx():
    if mediamtx and mediamtx.poll() is None:
        mediamtx.terminate()


@app.get("/api/status")
def status():
    key = load_key()
    paths = api_get("/v3/paths/list") if mediamtx is not None and mediamtx.poll() is None else None
    running = paths is not None
    ready = [p["name"] for p in paths["items"] if p.get("ready")] if running else []
    # DJI Fly sometimes joins address + key without a "/" (e.g. "livedrone"),
    # so fall back to any incoming stream if the expected path isn't live.
    expected = f"live/{key}"
    live_path = expected if expected in ready else (ready[0] if ready else None)
    ip = local_ip()
    return jsonify(
        ip=ip,
        rtmp=f"rtmp://{ip}:{RTMP_PORT}/live",
        key=key,
        server=running,
        live=live_path is not None,
        live_path=live_path,
        network_url=f"http://{ip}:{DASHBOARD_PORT}",
        webrtc_port=WEBRTC_PORT,
    )


@app.post("/api/key")
def set_key():
    key = "".join(c for c in request.json.get("key", "") if c.isalnum() or c in "-_") or "drone"
    with open(SETTINGS_FILE, "w") as f:
        json.dump({"stream_key": key}, f)
    return jsonify(key=key)


@app.get("/")
def index():
    return PAGE


@app.get("/icon.png")
def icon():
    return send_from_directory(HERE, "icon.png")


PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DJI Stream</title>
<link rel="icon" href="/icon.png">
<style>
  :root { --bg:#0f1215; --card:#181d23; --muted:#8a939e; --accent:#4fd1ff; --ok:#3ddc84; --bad:#e5534b; }
  * { box-sizing:border-box; }
  [hidden] { display:none !important; }
  body { margin:0; background:var(--bg); color:#e8ecf0; font:15px/1.4 system-ui,Segoe UI,sans-serif; }
  main { max-width:1100px; margin:0 auto; padding:24px 16px; display:grid; gap:16px;
         grid-template-columns: 360px 1fr; }
  @media (max-width:860px) { main { grid-template-columns:1fr; } }
  h1 { grid-column:1/-1; margin:0; font-size:24px; }
  .card { background:var(--card); border-radius:12px; padding:16px; }
  .label { color:var(--muted); font-size:13px; margin-bottom:4px; }
  .row { display:flex; gap:8px; margin-bottom:14px; }
  .val { flex:1; min-width:0; background:#0b0e11; color:var(--accent); border:0; border-radius:8px;
         padding:12px; font:bold 17px Consolas,monospace; overflow-x:auto; white-space:nowrap; }
  button { background:#2b6cb0; color:#fff; border:0; border-radius:8px; padding:0 14px; cursor:pointer; font-weight:600; }
  button:hover { background:#3182ce; }
  .status { display:flex; align-items:center; gap:10px; margin:8px 0; font-size:16px; }
  .dot { width:14px; height:14px; border-radius:50%; background:#555; }
  .dot.ok { background:var(--ok); box-shadow:0 0 10px var(--ok); } .dot.bad { background:var(--bad); }
  .player { aspect-ratio:16/9; background:#000; border-radius:12px; overflow:hidden; position:relative; }
  .player iframe { width:100%; height:100%; border:0; }
  .player .msg { position:absolute; inset:0; display:grid; place-items:center; color:var(--muted); }
  a { color:var(--accent); }
</style></head>
<body><main>
  <h1>DJI Stream Receiver</h1>
  <section class="card">
    <div class="label">RTMP Address</div>
    <div class="row"><input class="val" id="rtmp" readonly><button onclick="copy('rtmp',this)">Copy</button></div>
    <div class="label">Stream Key (edit + Enter to change)</div>
    <div class="row"><input class="val" id="key"><button onclick="copy('key',this)">Copy</button></div>
    <div class="status"><span class="dot" id="srvDot"></span><span id="srvTxt">Server…</span></div>
    <div class="status"><span class="dot" id="liveDot"></span><span id="liveTxt">Stream…</span></div>
    <p class="label" style="margin-top:16px">Open from another device on your wifi:</p>
    <a id="net" href="#"></a>
  </section>
  <section class="player">
    <div class="msg" id="msg">Waiting for controller…</div>
    <iframe id="frame" allow="autoplay; fullscreen" allowfullscreen hidden></iframe>
  </section>
</main>
<script>
const $ = id => document.getElementById(id);
let wasLive = false, currentKey = null;

function copy(id, btn) {
  navigator.clipboard?.writeText($(id).value).catch(() => {});
  $(id).select(); document.execCommand('copy');
  btn.textContent = '✓'; setTimeout(() => btn.textContent = 'Copy', 1200);
}

$('key').addEventListener('keydown', async e => {
  if (e.key !== 'Enter') return;
  const r = await fetch('/api/key', {method:'POST', headers:{'Content-Type':'application/json'},
                                     body: JSON.stringify({key: $('key').value})});
  $('key').value = (await r.json()).key; $('key').blur(); wasLive = false; refresh();
});

async function refresh() {
  let s;
  try { s = await (await fetch('/api/status')).json(); } catch { s = {server:false, live:false}; }
  if (s.rtmp) $('rtmp').value = s.rtmp;
  if (s.key && document.activeElement !== $('key')) $('key').value = s.key;
  if (s.network_url) { $('net').textContent = s.network_url; $('net').href = s.network_url; }
  $('srvDot').className = 'dot ' + (s.server ? 'ok' : 'bad');
  $('srvTxt').textContent = s.server ? 'Server running' : 'Server not running';
  $('liveDot').className = 'dot ' + (s.live ? 'ok' : '');
  $('liveTxt').textContent = s.live ? `Stream LIVE (/${s.live_path})` : 'Waiting for controller';

  // (Re)load the player when the stream goes live or its path changes.
  if (s.live && (!wasLive || s.live_path !== currentKey)) {
    const host = location.hostname;  // works from localhost and from other devices
    $('frame').src = `http://${host}:${s.webrtc_port}/${s.live_path}?controls=true&muted=true&autoplay=true`;
    $('frame').hidden = false; $('msg').hidden = true; currentKey = s.live_path;
  } else if (!s.live && wasLive) {
    $('frame').src = 'about:blank'; $('frame').hidden = true; $('msg').hidden = false;
  }
  wasLive = s.live;
}
refresh(); setInterval(refresh, 1500);
</script>
</body></html>"""


if __name__ == "__main__":
    start_mediamtx()
    print(f"\n  Dashboard:   http://localhost:{DASHBOARD_PORT}")
    print(f"  On network:  http://{local_ip()}:{DASHBOARD_PORT}")
    print(f"  RTMP:        rtmp://{local_ip()}:{RTMP_PORT}/live   key: {load_key()}\n")
    app.run(host="0.0.0.0", port=DASHBOARD_PORT, threaded=True)
