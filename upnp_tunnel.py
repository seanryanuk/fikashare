import socket
import base64
import json
import urllib.request
from typing import Optional, Tuple, Dict, Any

def get_local_ip() -> str:
    """Gets the local LAN IP address of this machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't have to be reachable, just triggers local interface selection
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def get_public_ip() -> str:
    """Gets the public WAN IP address using a public service with quick timeout."""
    try:
        req = urllib.request.Request("https://api.ipify.org?format=json", headers={'User-Agent': 'FikaShare/1.0'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get("ip", get_local_ip())
    except Exception:
        return get_local_ip()

class ConnectionCode:
    """Encodes and decodes host connection details into a friendly FIKA-XXXX code."""
    
    PREFIX = "FIKA-"

    @classmethod
    def encode(cls, host: str, port: int, passphrase: str = "") -> str:
        payload = {
            "h": host,
            "p": port,
            "s": passphrase
        }
        json_str = json.dumps(payload, separators=(',', ':'))
        b64 = base64.urlsafe_b64encode(json_str.encode('utf-8')).decode('utf-8').rstrip('=')
        return f"{cls.PREFIX}{b64}"

    @classmethod
    def decode(cls, code: str) -> Optional[Tuple[str, int, str]]:
        code = code.strip()
        if code.startswith(cls.PREFIX):
            code = code[len(cls.PREFIX):]

        # Re-add base64 padding if needed
        padding = 4 - (len(code) % 4)
        if padding != 4:
            code += "=" * padding

        try:
            json_bytes = base64.urlsafe_b64decode(code.encode('utf-8'))
            payload = json.loads(json_bytes.decode('utf-8'))
            host = payload.get("h", "")
            port = int(payload.get("p", 8585))
            passphrase = payload.get("s", "")
            return host, port, passphrase
        except Exception as e:
            print(f"[ConnectionCode] Decode error: {e}")
            return None


class UPnPManager:
    """Manages UPnP automatic router port forwarding using miniupnpc."""

    def __init__(self, port: int = 8585):
        self.port = port
        self.mapped = False
        self.external_ip = ""
        self.error_msg = ""

    def setup_upnp(self) -> bool:
        """Attempts UPnP discovery and TCP port mapping."""
        try:
            import miniupnpc
            u = miniupnpc.UPnP()
            u.discoverdelay = 200
            devices = u.discover()
            if devices == 0:
                self.error_msg = "No UPnP gateway device found on network."
                return False

            u.selectigd()
            self.external_ip = u.externalipaddress()
            local_ip = get_local_ip()

            # Map external port -> local port
            res = u.addportmapping(
                self.port,
                'TCP',
                local_ip,
                self.port,
                'FikaShare Server',
                ''
            )

            if res:
                self.mapped = True
                self.error_msg = f"UPnP Success! Port {self.port} mapped to {local_ip}:{self.port}"
                print(f"[UPnPManager] {self.error_msg}")
                return True
            else:
                self.error_msg = f"Router rejected UPnP port mapping for port {self.port}."
                return False

        except ImportError:
            self.error_msg = "miniupnpc library not installed."
            return False
        except Exception as e:
            self.error_msg = f"UPnP Error: {str(e)}"
            print(f"[UPnPManager] {self.error_msg}")
            return False

    def remove_upnp(self):
        """Removes the UPnP port mapping when server stops."""
        if not self.mapped:
            return
        try:
            import miniupnpc
            u = miniupnpc.UPnP()
            u.discoverdelay = 100
            u.discover()
            u.selectigd()
            u.deleteportmapping(self.port, 'TCP')
            self.mapped = False
            print(f"[UPnPManager] Port {self.port} mapping removed.")
        except Exception as e:
            print(f"[UPnPManager] Remove UPnP error: {e}")
