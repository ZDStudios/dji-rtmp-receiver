"""DJI Stream Receiver - desktop app.

Starts a bundled MediaMTX server, shows the RTMP address + stream key to
type into the DJI controller, and lights up when video is arriving.
"""
import json
import os
import socket
import subprocess
import sys
import threading
import urllib.request
import webbrowser

import customtkinter as ctk

# Own taskbar identity, so Windows shows our icon instead of Python's.
try:
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DJIStreamReceiver")
except Exception:
    pass

RTMP_PORT = 1935
WEBRTC_PORT = 8889
WEBRTC_UDP_PORT = 8189
API = "http://127.0.0.1:9997"
FIREWALL_RULE = "DJI Stream Receiver"

# Bundled files live in sys._MEIPASS when frozen by PyInstaller.
BUNDLE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
# Settings sit next to the .exe (or the script) so they survive restarts.
APP_DIR = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")

CREATE_NO_WINDOW = 0x08000000


def local_ip():
    """IP of the adapter used for outbound traffic (i.e. your wifi)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # no packets are sent for UDP connect
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


def save_key(key):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump({"stream_key": key}, f)
    except OSError:
        pass


def api_get(path):
    try:
        with urllib.request.urlopen(API + path, timeout=1) as r:
            return json.load(r)
    except Exception:
        return None


def firewall_rule_exists():
    r = subprocess.run(["netsh", "advfirewall", "firewall", "show", "rule", f"name={FIREWALL_RULE}"],
                       capture_output=True, creationflags=CREATE_NO_WINDOW)
    return r.returncode == 0


def add_firewall_rules():
    """Open RTMP (TCP 1935) + WebRTC (TCP 8889, UDP 8189). Prompts UAC once."""
    cmds = [
        f'netsh advfirewall firewall add rule name="{FIREWALL_RULE}" dir=in action=allow protocol=TCP localport={RTMP_PORT},{WEBRTC_PORT}',
        f'netsh advfirewall firewall add rule name="{FIREWALL_RULE}" dir=in action=allow protocol=UDP localport={WEBRTC_UDP_PORT}',
    ]
    args = "/c " + " & ".join(cmds)
    # ShellExecute with "runas" shows the UAC prompt; returns > 32 on success.
    import ctypes
    return ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", args, None, 0) > 32


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("DJI Stream Receiver")
        self.geometry("620x560")
        self.minsize(560, 520)
        self.configure(fg_color="#111418")
        # customtkinter sets its own icon shortly after startup, so apply ours after it.
        self.after(250, lambda: self.iconbitmap(os.path.join(BUNDLE_DIR, "icon.ico")))

        self.proc = None
        self.live_path = None
        self.ip = local_ip()

        big = ctk.CTkFont(family="Consolas", size=22, weight="bold")
        label = ctk.CTkFont(size=13)

        ctk.CTkLabel(self, text="DJI Stream Receiver", font=ctk.CTkFont(size=26, weight="bold")).pack(pady=(24, 4))
        ctk.CTkLabel(self, text="Enter these in the DJI app: Live Streaming → RTMP", font=label,
                     text_color="#8a939e").pack(pady=(0, 16))

        # RTMP address
        self.addr_var = ctk.StringVar(value=f"rtmp://{self.ip}:{RTMP_PORT}/live")
        self._copy_row("RTMP Address", self.addr_var, big, editable=False)

        # Stream key
        self.key_var = ctk.StringVar(value=load_key())
        self.key_var.trace_add("write", lambda *_: save_key(self.key_var.get().strip() or "drone"))
        self._copy_row("Stream Key (editable)", self.key_var, big, editable=True)

        # Status lights
        status = ctk.CTkFrame(self, fg_color="#1a1f25", corner_radius=12)
        status.pack(fill="x", padx=28, pady=(18, 10))
        self.server_dot, self.server_lbl = self._status_row(status, "Server: starting…")
        self.live_dot, self.live_lbl = self._status_row(status, "Stream: waiting for controller")

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(pady=12)
        ctk.CTkButton(btns, text="▶  View Stream", width=180, height=44, font=ctk.CTkFont(size=15, weight="bold"),
                      command=self.view_stream).pack(side="left", padx=8)
        ctk.CTkButton(btns, text="Restart Server", width=140, height=44, fg_color="#2b323b",
                      hover_color="#3a434e", command=self.restart_server).pack(side="left", padx=8)

        self.fw_lbl = ctk.CTkLabel(self, text="", font=label, text_color="#8a939e")
        self.fw_lbl.pack(pady=(4, 0))

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.start_server()
        if "--no-firewall" not in sys.argv:
            threading.Thread(target=self.check_firewall, daemon=True).start()
        self.after(1000, self.poll)

    # ---------- UI helpers ----------
    def _copy_row(self, title, var, font, editable):
        frame = ctk.CTkFrame(self, fg_color="#1a1f25", corner_radius=12)
        frame.pack(fill="x", padx=28, pady=6)
        ctk.CTkLabel(frame, text=title, text_color="#8a939e").pack(anchor="w", padx=16, pady=(10, 0))
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=(2, 12))
        entry = ctk.CTkEntry(row, textvariable=var, font=font, height=46, border_width=0,
                             fg_color="#0d1014", text_color="#4fd1ff")
        if not editable:
            entry.configure(state="readonly")
        entry.pack(side="left", fill="x", expand=True, padx=(4, 8))
        btn = ctk.CTkButton(row, text="Copy", width=72, height=46)
        btn.configure(command=lambda: self.copy(var.get(), btn))
        btn.pack(side="right")

    def _status_row(self, parent, text):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=8)
        dot = ctk.CTkLabel(row, text="●", font=ctk.CTkFont(size=22), text_color="#555")
        dot.pack(side="left")
        lbl = ctk.CTkLabel(row, text=text, font=ctk.CTkFont(size=15))
        lbl.pack(side="left", padx=10)
        return dot, lbl

    def copy(self, text, btn):
        self.clipboard_clear()
        self.clipboard_append(text)
        btn.configure(text="✓")
        self.after(1200, lambda: btn.configure(text="Copy"))

    # ---------- server ----------
    def start_server(self):
        # A MediaMTX left over from a previous run would hold the ports and make ours exit.
        subprocess.run(["taskkill", "/F", "/IM", "mediamtx.exe"], capture_output=True,
                       creationflags=CREATE_NO_WINDOW)
        exe = os.path.join(BUNDLE_DIR, "mediamtx.exe")
        cfg = os.path.join(BUNDLE_DIR, "mediamtx.yml")
        try:
            self.proc = subprocess.Popen([exe, cfg], cwd=APP_DIR, stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        except OSError as e:
            self.proc = None
            self.server_lbl.configure(text=f"Server failed: {e}")

    def stop_server(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def restart_server(self):
        self.stop_server()
        self.ip = local_ip()
        self.addr_var.set(f"rtmp://{self.ip}:{RTMP_PORT}/live")
        self.start_server()

    def poll(self):
        """Runs every second: update server + stream lights."""
        threading.Thread(target=self._poll_worker, daemon=True).start()
        self.after(1000, self.poll)

    def _poll_worker(self):
        paths = api_get("/v3/paths/list") if self.proc is not None and self.proc.poll() is None else None
        running = paths is not None
        ready = [p["name"] for p in paths["items"] if p.get("ready")] if running else []
        # DJI Fly sometimes joins address + key without a "/" (e.g. "livedrone"),
        # so fall back to any incoming stream if the expected path isn't live.
        expected = f"live/{self.key_var.get().strip() or 'drone'}"
        self.live_path = expected if expected in ready else (ready[0] if ready else None)
        self.after(0, self._set_status, running, self.live_path is not None)

    def _set_status(self, running, live):
        if running:
            self.server_dot.configure(text_color="#3ddc84")
            self.server_lbl.configure(text=f"Server running  (RTMP :{RTMP_PORT})")
        else:
            self.server_dot.configure(text_color="#e5534b")
            self.server_lbl.configure(text="Server not running – click Restart Server")
        if live:
            self.live_dot.configure(text_color="#3ddc84")
            self.live_lbl.configure(text=f"Stream LIVE  (/{self.live_path})")
        else:
            self.live_dot.configure(text_color="#555")
            self.live_lbl.configure(text="Stream: waiting for controller")

    def view_stream(self):
        path = self.live_path or f"live/{self.key_var.get().strip() or 'drone'}"
        webbrowser.open(f"http://localhost:{WEBRTC_PORT}/{path}")

    def check_firewall(self):
        if firewall_rule_exists():
            msg = "Firewall: ports open ✓"
        elif add_firewall_rules():
            msg = "Firewall: rule added ✓ (approved admin prompt)"
        else:
            msg = "Firewall: not configured – allow mediamtx.exe if Windows asks"
        self.after(0, lambda: self.fw_lbl.configure(text=msg))

    def on_close(self):
        self.stop_server()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
