import os
import json
import requests
from typing import Dict, Optional, Tuple

from profile_parser import ProfileInfo, parse_profile_file, resolve_profiles_dir
from sync_engine import BackupManager
from upnp_tunnel import ConnectionCode

class FikaClient:
    """HTTP Client for connecting to a FikaShare server host and performing profile sync."""

    def __init__(self):
        self.host = ""
        self.port = 8585
        self.passphrase = ""
        self.is_connected = False
        self.backup_mgr = BackupManager()

    def set_connection(self, connection_input: str, passphrase: str = "") -> bool:
        """Sets connection parameters from a Connection Code (FIKA-XXXX) or host:port string."""
        connection_input = connection_input.strip()
        if not connection_input:
            return False

        if connection_input.startswith("FIKA-"):
            decoded = ConnectionCode.decode(connection_input)
            if decoded:
                self.host, self.port, code_pass = decoded
                self.passphrase = passphrase or code_pass
                return True
            else:
                return False

        # Try host:port parsing
        if ":" in connection_input:
            parts = connection_input.split(":")
            self.host = parts[0].strip()
            try:
                self.port = int(parts[1].strip())
            except ValueError:
                self.port = 8585
        else:
            self.host = connection_input
            self.port = 8585

        self.passphrase = passphrase
        return True

    @property
    def base_url(self) -> str:
        h = self.host if self.host else "127.0.0.1"
        return f"http://{h}:{self.port}"

    def _get_headers(self) -> dict:
        headers = {}
        if self.passphrase:
            headers['X-Passphrase'] = self.passphrase
        return headers

    def test_connection(self) -> Tuple[bool, str]:
        """Tests health endpoint on the target server."""
        try:
            url = f"{self.base_url}/api/health"
            resp = requests.get(url, timeout=4)
            if resp.status_code == 200:
                self.is_connected = True
                return True, "Connected successfully"
            else:
                self.is_connected = False
                return False, f"Server error: {resp.status_code}"
        except Exception as e:
            self.is_connected = False
            return False, f"Connection failed: {str(e)}"

    def fetch_remote_profiles(self) -> Tuple[bool, Dict[str, ProfileInfo], str]:
        """Fetches profile metadata list from the remote server."""
        try:
            url = f"{self.base_url}/api/profiles"
            resp = requests.get(url, headers=self._get_headers(), timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                result = {}
                for pid, pdata in data.items():
                    result[pid] = ProfileInfo.from_dict(pdata)
                self.is_connected = True
                return True, result, "OK"
            elif resp.status_code == 401:
                self.is_connected = False
                return False, {}, "Invalid passphrase"
            else:
                return False, {}, f"Server returned {resp.status_code}"
        except Exception as e:
            self.is_connected = False
            return False, {}, f"Network error: {str(e)}"

    def download_profile(self, profile_id: str, local_spt_dir: str) -> Tuple[bool, str]:
        """Downloads profile JSON from server and writes to local SPT profiles directory."""
        if not local_spt_dir:
            return False, "Local SPT directory not set"

        profiles_dir = resolve_profiles_dir(local_spt_dir)
        if not profiles_dir:
            profiles_dir = local_spt_dir
        os.makedirs(profiles_dir, exist_ok=True)
        local_filepath = os.path.join(profiles_dir, f"{profile_id}.json")
        return self.download_profile_to_path(profile_id, local_filepath)

    def download_profile_to_path(self, profile_id: str, target_filepath: str) -> Tuple[bool, str]:
        """Downloads profile JSON from server and writes to a target custom filepath."""
        try:
            target_dir = os.path.dirname(os.path.abspath(target_filepath))
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)

            url = f"{self.base_url}/api/profiles/{profile_id}"
            resp = requests.get(url, headers=self._get_headers(), timeout=10)

            if resp.status_code != 200:
                return False, f"Download failed with status {resp.status_code}"

            # Safety check: ensure response is valid JSON
            json_bytes = resp.content
            json.loads(json_bytes.decode('utf-8'))

            # CRITICAL RULE: Create safety backup if file already exists at target
            if os.path.exists(target_filepath):
                self.backup_mgr.create_backup(target_filepath, profile_id, action_label="client_pre_download")

            with open(target_filepath, 'wb') as f:
                f.write(json_bytes)

            # Preserve remote modification time if provided by server
            remote_mtime_hdr = resp.headers.get('X-Profile-MTime')
            if remote_mtime_hdr:
                try:
                    mtime_val = float(remote_mtime_hdr)
                    os.utime(target_filepath, (mtime_val, mtime_val))
                except ValueError:
                    pass

            return True, f"Profile {profile_id} downloaded successfully to {target_filepath}"
        except Exception as e:
            return False, f"Download error: {str(e)}"

    def upload_profile(self, profile_id: str, local_spt_dir: str) -> Tuple[bool, str]:
        """Uploads local profile JSON to the remote server host."""
        if not local_spt_dir:
            return False, "Local SPT directory not set"

        profiles_dir = resolve_profiles_dir(local_spt_dir)
        local_filepath = os.path.join(profiles_dir, f"{profile_id}.json")
        if not os.path.exists(local_filepath):
            return False, f"Local profile file {profile_id}.json not found at {local_filepath}"

        try:
            with open(local_filepath, 'rb') as f:
                content = f.read()

            # Ensure valid JSON content
            json.loads(content.decode('utf-8'))

            local_mtime = os.path.getmtime(local_filepath)
            headers = self._get_headers()
            headers['Content-Type'] = 'application/json'
            headers['X-Profile-MTime'] = str(local_mtime)

            url = f"{self.base_url}/api/profiles/{profile_id}"
            resp = requests.post(url, data=content, headers=headers, timeout=10)

            if resp.status_code == 200:
                return True, f"Profile {profile_id} uploaded successfully"
            elif resp.status_code == 401:
                return False, "Invalid server passphrase"
            else:
                return False, f"Upload rejected by server: {resp.status_code}"
        except Exception as e:
            return False, f"Upload error: {str(e)}"
