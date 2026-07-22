import os
import shutil
import time
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple
from profile_parser import ProfileInfo

class SyncStatus(Enum):
    LOCAL_ONLY = "LOCAL_ONLY"
    REMOTE_ONLY = "REMOTE_ONLY"
    IN_SYNC = "IN_SYNC"
    LOCAL_NEWER = "LOCAL_NEWER"
    REMOTE_NEWER = "REMOTE_NEWER"

class SyncItem:
    def __init__(self, profile_id: str, local_info: Optional[ProfileInfo], remote_info: Optional[ProfileInfo]):
        self.profile_id = profile_id
        self.local_info = local_info
        self.remote_info = remote_info
        self.status = self._calculate_status()

    def _calculate_status(self) -> SyncStatus:
        if self.local_info and not self.remote_info:
            return SyncStatus.LOCAL_ONLY
        if self.remote_info and not self.local_info:
            return SyncStatus.REMOTE_ONLY
        
        # Both exist, compare mtime (allow 2s clock drift margin)
        l_time = self.local_info.mtime if self.local_info else 0
        r_time = self.remote_info.mtime if self.remote_info else 0
        
        diff = l_time - r_time
        if abs(diff) <= 2.0:
            return SyncStatus.IN_SYNC
        elif diff > 2.0:
            return SyncStatus.LOCAL_NEWER
        else:
            return SyncStatus.REMOTE_NEWER

    @property
    def display_name(self) -> str:
        if self.local_info and self.local_info.nickname and self.local_info.nickname != "Unknown PMC":
            return self.local_info.nickname
        if self.remote_info and self.remote_info.nickname:
            return self.remote_info.nickname
        return f"Profile {self.profile_id[:8]}"

    @property
    def display_level(self) -> int:
        if self.local_info and self.local_info.level > 1:
            return self.local_info.level
        if self.remote_info:
            return self.remote_info.level
        return 1

    @property
    def display_side(self) -> str:
        if self.local_info and self.local_info.side != "UNKNOWN":
            return self.local_info.side
        if self.remote_info:
            return self.remote_info.side
        return "USEC"

    @property
    def location_badge(self) -> str:
        if self.local_info and self.remote_info:
            return "Local & Server"
        elif self.local_info:
            return "Local Only"
        else:
            return "Server Only"

    @property
    def status_badge(self) -> str:
        if self.status == SyncStatus.IN_SYNC:
            return "In Sync"
        elif self.status == SyncStatus.LOCAL_NEWER:
            return "Local Newer (Upload Available)"
        elif self.status == SyncStatus.REMOTE_NEWER:
            return "Server Newer (Download Available)"
        elif self.status == SyncStatus.LOCAL_ONLY:
            return "Local Only"
        elif self.status == SyncStatus.REMOTE_ONLY:
            return "Server Only"
        return "Unknown"

    @property
    def can_upload(self) -> bool:
        """Upload is allowed if profile exists locally."""
        return self.local_info is not None

    @property
    def can_download(self) -> bool:
        """Download is allowed if profile exists on server."""
        return self.remote_info is not None


class BackupManager:
    """Manages timestamped profile backups in a dedicated directory OUTSIDE user/profiles."""
    
    def __init__(self, backup_dir: Optional[str] = None):
        if not backup_dir:
            backup_dir = os.path.join(os.getcwd(), "FikaShare_Backups")
        self.backup_dir = os.path.abspath(backup_dir)
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self, source_filepath: str, profile_id: str, action_label: str = "backup") -> Optional[str]:
        """Creates a timestamped copy of a profile file in the backup directory."""
        if not os.path.exists(source_filepath):
            return None

        profile_backup_folder = os.path.join(self.backup_dir, profile_id)
        os.makedirs(profile_backup_folder, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{timestamp}_{action_label}_{profile_id}.json"
        dest_filepath = os.path.join(profile_backup_folder, backup_filename)

        try:
            shutil.copy2(source_filepath, dest_filepath)
            self._cleanup_old_backups(profile_backup_folder, max_keep=15)
            print(f"[BackupManager] Backup created: {dest_filepath}")
            return dest_filepath
        except Exception as e:
            print(f"[BackupManager] Error creating backup for {profile_id}: {e}")
            return None

    def _cleanup_old_backups(self, folder: str, max_keep: int = 15):
        """Keeps only the most recent N backups per profile."""
        try:
            files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".json")]
            if len(files) > max_keep:
                # Sort by modification time ascending
                files.sort(key=lambda x: os.path.getmtime(x))
                for f_to_del in files[:-max_keep]:
                    os.remove(f_to_del)
        except Exception as e:
            print(f"[BackupManager] Cleanup error: {e}")


def check_spt_processes() -> Tuple[bool, List[str]]:
    """Checks if SPT / Aki Server or Tarkov game processes are running."""
    running_target_processes = []
    target_names = [
        "aki.server", "spt.server", "escapefromtarkov",
        "aki.launcher", "spt.launcher", "fika"
    ]
    
    try:
        # Cross-platform process check via ps or os tools
        if os.name == 'posix':
            import subprocess
            res = subprocess.run(["ps", "-A", "-o", "comm="], capture_output=True, text=True)
            procs = res.stdout.lower().splitlines()
            for proc in procs:
                for target in target_names:
                    if target in proc:
                        running_target_processes.append(proc.strip())
        elif os.name == 'nt':
            import subprocess
            res = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True)
            lines = res.stdout.lower().splitlines()
            for line in lines:
                for target in target_names:
                    if target in line:
                        proc_name = line.split(",")[0].replace('"', '')
                        running_target_processes.append(proc_name)
    except Exception as e:
        print(f"[ProcessInspector] Check error: {e}")

    is_running = len(running_target_processes) > 0
    return is_running, list(set(running_target_processes))
