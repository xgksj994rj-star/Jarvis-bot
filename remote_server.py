import json
import os
import socket
import subprocess
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Optional

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
DEFAULT_HOST = "0.0.0.0"  # Listen on all interfaces
DEFAULT_PORT = 5000


def _add_firewall_exception(port: int) -> bool:
    """Add Windows Firewall exception for the port."""
    if os.name != "nt":
        return True
    
    try:
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            print(f"[RemoteServer] ℹ️  Run as Administrator to enable firewall rule (optional)")
            return False
    except Exception:
        pass
    
    try:
        cmd = f'netsh advfirewall firewall add rule name="JARVIS Remote Control" dir=in action=allow protocol=tcp localport={port} > nul 2>&1'
        result = subprocess.run(cmd, shell=True, capture_output=False)
        print(f"[RemoteServer] ✅ Firewall rule added for port {port}")
        return True
    except Exception as exc:
        print(f"[RemoteServer] ℹ️  Firewall setup skipped: {exc}")
        return False


def _get_local_ip() -> str:
    """Get the local machine IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _load_ngrok_token() -> Optional[str]:
    env_token = os.environ.get("NGROK_AUTHTOKEN") or os.environ.get("NGROK_AUTH_TOKEN")
    if env_token:
        return env_token.strip()

    if not CONFIG_PATH.exists():
        return None
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return data.get("ngrok_auth_token")
    except Exception:
        return None


class RemoteControllerHandler(BaseHTTPRequestHandler):
    def _page_html(self, command: str = "", message: str = "") -> str:
        escaped_command = urllib.parse.quote(command, safe="')")
        message_block = f"<p style='color:#8ffcff; font-size:0.95rem;'>{message}</p>" if message else ""
        return f"""
        <html>
          <head>
            <title>JARVIS Remote Control</title>
            <style>
              body {{ background: #02070d; color: #d8f8ff; font-family: Arial, sans-serif; margin: 0; padding: 24px; }}
              h1 {{ color: #00d4ff; margin-bottom: 12px; }}
              .card {{ background: #06141f; border: 1px solid #07324b; border-radius: 12px; padding: 18px; max-width: 640px; }}
              input, textarea {{ width: 100%; margin-top: 8px; padding: 10px 12px; border: 1px solid #184a63; border-radius: 8px; background: #01121d; color: #d8f8ff; }}
              button {{ margin-top: 12px; padding: 10px 16px; border: none; border-radius: 8px; background: #00d4ff; color: #000; font-weight: bold; cursor: pointer; }}
              .footer {{ margin-top: 18px; color: #5ab8cc; font-size: 0.9rem; }}
              a {{ color: #ffcc00; }}
            </style>
          </head>
          <body>
            <div class="card">
              <h1>JARVIS Remote Control</h1>
              <p>Send a command to your local JARVIS assistant from another device on this machine.</p>
              <form method="post" action="/command">
                <textarea name="command" rows="4" placeholder="Type a command for JARVIS..."></textarea>
                <button type="submit">Send Command</button>
              </form>
              {message_block}
              <div class="footer">You can also use the JARVIS UI to access this page while the app is running.</div>
            </div>
          </body>
        </html>
        """

    def _send_html(self, html: str, status: int = 200) -> None:
        encoded = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send_html(self._page_html())
            return
        self.send_error(404, "Not Found")

    def do_POST(self):
        if self.path != "/command":
            self.send_error(404, "Not Found")
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        params = urllib.parse.parse_qs(body)
        command = params.get("command", [""])[0].strip()

        if not command:
            self._send_html(self._page_html(command, "Please enter a command before sending."), status=400)
            return

        if getattr(self.server, "command_callback", None):
            try:
                self.server.command_callback(command)
                self._send_html(self._page_html("", "Command sent successfully."))
            except Exception as exc:
                self._send_html(self._page_html(command, f"Failed to send command: {exc}"), status=500)
        else:
            self._send_html(self._page_html(command, "JARVIS command handler is unavailable."), status=500)

    def log_message(self, format: str, *args) -> None:
        return


class JarvisRemoteServer(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, command_callback: Optional[Callable[[str], None]] = None):
        super().__init__(server_address, RequestHandlerClass)
        self.command_callback = command_callback
        self.daemon_threads = True
        self.allow_reuse_address = True


def _create_server(command_callback: Optional[Callable[[str], None]], host: str, port: int) -> JarvisRemoteServer:
    try:
        return JarvisRemoteServer((host, port), RemoteControllerHandler, command_callback=command_callback)
    except OSError:
        return JarvisRemoteServer((host, 0), RemoteControllerHandler, command_callback=command_callback)


def _start_ngrok_tunnel(port: int) -> Optional[str]:
    token = _load_ngrok_token()
    if not token:
        print(f"[RemoteServer] ngrok token not configured. Local network access only.")
        return None
    try:
        from pyngrok import ngrok
        ngrok.set_auth_token(token)
        tunnel = ngrok.connect(port, "http", bind_tls=True)
        public_url = tunnel.public_url
        if public_url:
            print(f"[RemoteServer] ✅ ngrok tunnel established: {public_url}")
            return public_url
        print(f"[RemoteServer] ⚠️ ngrok tunnel started, but public URL was not returned.")
        return None
    except ImportError:
        print(f"[RemoteServer] ⚠️ pyngrok not installed. Install with: pip install pyngrok")
        return None
    except Exception as exc:
        print(f"[RemoteServer] ⚠️ ngrok tunnel failed: {exc}")
        print("[RemoteServer] ℹ️  Check your ngrok authtoken and make sure it is valid.")
        return None


def start_remote_server(command_callback: Optional[Callable[[str], None]] = None, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> tuple[str, Optional[str]]:
    # Add Windows Firewall exception
    _add_firewall_exception(port)
    
    server = _create_server(command_callback, host, port)
    actual_port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="JarvisRemoteServer")
    thread.start()
    
    # Get the local IP address for the local URL
    local_ip = _get_local_ip()
    local_url = f"http://{local_ip}:{actual_port}"
    
    print(f"[RemoteServer] 🚀 Server started at {local_url}")
    print(f"[RemoteServer] 📱 Access from phone on same WiFi: {local_url}")
    
    # Try to start ngrok for internet access
    public_url = _start_ngrok_tunnel(actual_port)
    
    return local_url, public_url
