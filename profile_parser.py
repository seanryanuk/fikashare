import os
import json
import time
from datetime import datetime
from typing import Dict, Optional, Any

class ProfileInfo:
    def __init__(self, profile_id: str, nickname: str, level: int, side: str, 
                 mtime: float, file_size: int, file_path: str, raw_data: Optional[dict] = None):
        self.profile_id = profile_id
        self.nickname = nickname
        self.level = level
        self.side = side  # "Usec", "Bear", etc.
        self.mtime = mtime
        self.file_size = file_size
        self.file_path = file_path
        self.raw_data = raw_data or {}

    @property
    def mtime_formatted(self) -> str:
        if not self.mtime:
            return "N/A"
        return datetime.fromtimestamp(self.mtime).strftime('%Y-%m-%d %H:%M:%S')

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "nickname": self.nickname,
            "level": self.level,
            "side": self.side,
            "mtime": self.mtime,
            "mtime_formatted": self.mtime_formatted,
            "file_size": self.file_size
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ProfileInfo':
        return cls(
            profile_id=data.get("profile_id", "unknown"),
            nickname=data.get("nickname", "Unknown"),
            level=data.get("level", 1),
            side=data.get("side", "Unknown"),
            mtime=data.get("mtime", 0.0),
            file_size=data.get("file_size", 0),
            file_path=data.get("file_path", "")
        )

def resolve_profiles_dir(path: Optional[str]) -> str:
    """
    Resolves the actual folder containing .json profile files from any user-provided path.
    Handles:
    - Direct profiles directory (containing .json files)
    - SPT Root directory (containing user/profiles)
    - SPT user directory (containing profiles)
    """
    if not path or not os.path.exists(path):
        return ""

    path = os.path.abspath(path)

    # 1. Direct check: Does the given path itself contain .json files?
    if os.path.isdir(path):
        try:
            items = os.listdir(path)
            json_files = [f for f in items if f.endswith('.json') and not f.startswith('.')]
            if json_files:
                return path
        except Exception:
            pass

    # 2. Check path/user/profiles
    sub1 = os.path.join(path, "user", "profiles")
    if os.path.exists(sub1) and os.path.isdir(sub1):
        return sub1

    # 3. Check path/profiles
    sub2 = os.path.join(path, "profiles")
    if os.path.exists(sub2) and os.path.isdir(sub2):
        return sub2

    # 4. Fallback to path if it exists as a directory
    if os.path.isdir(path):
        return path

    return ""


def parse_profile_file(file_path: str) -> Optional[ProfileInfo]:
    """Parses a Tarkov SPT profile JSON file and extracts PMC character metadata."""
    if not os.path.exists(file_path) or not file_path.endswith('.json'):
        return None

    try:
        stat = os.stat(file_path)
        mtime = stat.st_mtime
        file_size = stat.st_size
        profile_id = os.path.splitext(os.path.basename(file_path))[0]

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        nickname = "Unknown PMC"
        level = 1
        side = "Unknown"

        # Check standard & extended SPT profile structures
        info = {}
        if isinstance(data, dict):
            # Structure 1: characters.pmc.Info / info
            characters = data.get("characters", {})
            if isinstance(characters, dict):
                pmc = characters.get("pmc", {})
                if isinstance(pmc, dict):
                    info = pmc.get("Info") or pmc.get("info") or {}

            if not info and isinstance(data.get("info"), dict):
                info = data.get("info", {})
            if not info and isinstance(data.get("Info"), dict):
                info = data.get("Info", {})
            if not info and isinstance(data.get("pmc"), dict):
                info = data.get("pmc", {}).get("Info") or data.get("pmc", {}).get("info") or {}

        if info:
            nickname = info.get("Nickname") or info.get("nickname") or nickname
            level = info.get("Level") or info.get("level") or level
            side = info.get("Side") or info.get("side") or side

        # Fallback nickname to Profile ID snippet if still unknown
        if nickname == "Unknown PMC":
            nickname = f"PMC ({profile_id[:8]})"

        # Format side cleanly (e.g. "Usec" -> "USEC", "Bear" -> "BEAR")
        if isinstance(side, str):
            side = side.upper()

        return ProfileInfo(
            profile_id=profile_id,
            nickname=nickname,
            level=int(level) if str(level).isdigit() else 1,
            side=side,
            mtime=mtime,
            file_size=file_size,
            file_path=file_path,
            raw_data=data
        )
    except Exception as e:
        print(f"[ProfileParser] Error parsing {file_path}: {e}")
        return ProfileInfo(
            profile_id=os.path.splitext(os.path.basename(file_path))[0],
            nickname=f"Profile {os.path.splitext(os.path.basename(file_path))[0][:8]}",
            level=1,
            side="UNKNOWN",
            mtime=os.path.getmtime(file_path) if os.path.exists(file_path) else 0.0,
            file_size=os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            file_path=file_path
        )

def find_spt_directory(custom_path: Optional[str] = None) -> Optional[str]:
    """Auto-detects SPT Tarkov installation directory."""
    if custom_path:
        resolved = resolve_profiles_dir(custom_path)
        if resolved:
            return custom_path

    # Candidate locations to check
    cwd = os.getcwd()
    candidates = [
        cwd,
        os.path.abspath(os.path.join(cwd, "..")),
        os.path.expanduser("~/SPT"),
        os.path.expanduser("~/Games/SPT"),
        "/opt/SPT",
        "C:\\SPT",
        "D:\\SPT",
        "E:\\SPT",
        "C:\\Games\\SPT",
        "D:\\Games\\SPT",
    ]

    for candidate in candidates:
        if os.path.isdir(candidate):
            resolved = resolve_profiles_dir(candidate)
            if resolved and len(os.listdir(resolved)) > 0:
                return os.path.abspath(candidate)

    return None

def scan_local_profiles(spt_dir: str) -> Dict[str, ProfileInfo]:
    """Scans profiles folder from any configured path and returns a mapping of profile_id -> ProfileInfo."""
    if not spt_dir:
        return {}
    
    profiles_dir = resolve_profiles_dir(spt_dir)
    if not profiles_dir or not os.path.exists(profiles_dir):
        return {}

    result = {}
    for filename in os.listdir(profiles_dir):
        if filename.endswith(".json") and not filename.startswith("."):
            full_path = os.path.join(profiles_dir, filename)
            pinfo = parse_profile_file(full_path)
            if pinfo:
                result[pinfo.profile_id] = pinfo
    return result
