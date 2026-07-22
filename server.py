import os
import json
import time
import socket
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from typing import Optional, Callable, Dict, Any

from profile_parser import scan_local_profiles, parse_profile_file, ProfileInfo, resolve_profiles_dir
from sync_engine import BackupManager
from upnp_tunnel import UPnPManager, get_local_ip, get_public_ip, ConnectionCode

class FikaServerHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for FikaShare profile sync REST API."""

    def log_message(self, format, *args):
        # Override to send log messages to server callback instead of stderr
        msg = f"{self.address_string()} - {format % args}"
        if hasattr(self.server, 'log_callback') and self.server.log_callback:
            self.server.log_callback(msg)

    def _send_json(self, status_code: int, data: dict):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status_code: int, message: str):
        self._send_json(status_code, {"error": message})

    def _check_auth(self) -> bool:
        passphrase = getattr(self.server, 'passphrase', "")
        if not passphrase:
            return True
        
        # Check header or query param
        header_pass = self.headers.get('X-Passphrase', '')
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)
        query_pass = params.get('passphrase', [''])[0]

        return (header_pass == passphrase) or (query_pass == passphrase)

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == '/api/health':
            self._send_json(200, {"status": "ok", "app": "FikaShare", "version": "1.0.0"})
            return

        if not self._check_auth():
            self._send_error(401, "Invalid passphrase")
            return

        spt_dir = getattr(self.server, 'spt_dir', '')
        profiles_dir = resolve_profiles_dir(spt_dir)
        if not profiles_dir or not os.path.exists(profiles_dir):
            self._send_error(500, f"Server profile directory not found for path: {spt_dir}")
            return

        if path == '/api/profiles':
            profiles = scan_local_profiles(spt_dir)
            result = {pid: pinfo.to_dict() for pid, pinfo in profiles.items()}
            self._send_json(200, result)
            return

        if path.startswith('/api/profiles/'):
            profile_id = path[len('/api/profiles/'):]
            profile_file = os.path.join(profiles_dir, f"{profile_id}.json")
            if not os.path.exists(profile_file):
                self._send_error(404, f"Profile {profile_id} not found on server")
                return

            try:
                with open(profile_file, 'rb') as f:
                    content = f.read()
                
                # Fetch modification timestamp
                mtime = os.path.getmtime(profile_file)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(content)))
                self.send_header('X-Profile-MTime', str(mtime))
                self.end_headers()
                self.wfile.write(content)
                self.log_message(f"Profile downloaded: {profile_id}")
            except Exception as e:
                self._send_error(500, f"Error reading profile file: {e}")
            return

        self._send_error(404, "Endpoint not found")

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if not self._check_auth():
            self._send_error(401, "Invalid passphrase")
            return

        spt_dir = getattr(self.server, 'spt_dir', '')
        profiles_dir = resolve_profiles_dir(spt_dir)
        if not profiles_dir:
            profiles_dir = spt_dir
        os.makedirs(profiles_dir, exist_ok=True)

        if path.startswith('/api/profiles/'):
            profile_id = path[len('/api/profiles/'):]
            target_filepath = os.path.join(profiles_dir, f"{profile_id}.json")

            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_error(400, "Empty payload")
                return

            body = self.rfile.read(content_length)

            # Safety validation: Ensure payload is valid JSON before overwriting!
            try:
                parsed_json = json.loads(body.decode('utf-8'))
            except Exception as e:
                self._send_error(400, f"Invalid JSON payload: {e}")
                return

            # CRITICAL RULE: Create server backup before overwriting!
            backup_mgr = getattr(self.server, 'backup_mgr', None)
            if backup_mgr and os.path.exists(target_filepath):
                backup_mgr.create_backup(target_filepath, profile_id, action_label="server_pre_overwrite")

            try:
                with open(target_filepath, 'wb') as f:
                    f.write(body)

                # Set client mtime if provided in header
                client_mtime = self.headers.get('X-Profile-MTime')
                if client_mtime:
                    try:
                        mtime_val = float(client_mtime)
                        os.utime(target_filepath, (mtime_val, mtime_val))
                    except ValueError:
                        pass

                self.log_message(f"Profile uploaded and updated: {profile_id}")
                self._send_json(200, {
                    "status": "success",
                    "profile_id": profile_id,
                    "mtime": os.path.getmtime(target_filepath)
                })
            except Exception as e:
                self._send_error(500, f"Error saving profile: {e}")
            return

        self._send_error(404, "Endpoint not found")


class FikaShareServer:
    """Server manager running HTTP server in a background thread with UPnP integration."""

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        self.spt_dir = ""
        self.port = 8585
        self.passphrase = ""
        self.httpd: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.upnp_mgr: Optional[UPnPManager] = None
        self.backup_mgr = BackupManager()
        self.is_running = False
        self.log_callback = log_callback
        self.public_ip = ""
        self.local_ip = ""

    def log(self, msg: str):
        print(f"[Server] {msg}")
        if self.log_callback:
            self.log_callback(msg)

    def start(self, spt_dir: str, port: int = 8585, passphrase: str = "", enable_upnp: bool = True) -> bool:
        if self.is_running:
            return True

        self.spt_dir = spt_dir
        self.port = port
        self.passphrase = passphrase
        self.local_ip = get_local_ip()

        try:
            self.httpd = HTTPServer(('0.0.0.0', self.port), FikaServerHandler)
            # Attach properties to server instance for handler access
            self.httpd.spt_dir = self.spt_dir
            self.httpd.passphrase = self.passphrase
            self.httpd.backup_mgr = self.backup_mgr
            self.httpd.log_callback = self.log

            self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.thread.start()
            self.is_running = True
            self.log(f"FikaShare Server started on port {self.port}")

            # Attempt UPnP in background thread if requested
            if enable_upnp:
                upnp_thread = threading.Thread(target=self._init_upnp, daemon=True)
                upnp_thread.start()
            else:
                self.public_ip = get_public_ip()

            return True
        except Exception as e:
            self.log(f"Failed to start server: {e}")
            self.is_running = False
            return False

    def _init_upnp(self):
        self.upnp_mgr = UPnPManager(self.port)
        success = self.upnp_mgr.setup_upnp()
        if success:
            self.public_ip = self.upnp_mgr.external_ip
            self.log(f"UPnP mapped successfully! WAN IP: {self.public_ip}:{self.port}")
        else:
            self.public_ip = get_public_ip()
            self.log(f"UPnP info: {self.upnp_mgr.error_msg}")

    def get_connection_code(self) -> str:
        """Returns shareable FIKA-XXXX connection code for clients."""
        host = self.public_ip if self.public_ip else self.local_ip
        return ConnectionCode.encode(host, self.port, self.passphrase)

    def stop(self):
        if not self.is_running:
            return

        self.log("Stopping server...")
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None

        if self.upnp_mgr:
            self.upnp_mgr.remove_upnp()
            self.upnp_mgr = None

        self.is_running = False
        self.log("Server stopped.")
