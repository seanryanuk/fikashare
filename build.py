import os
import sys
import subprocess

def build_executable():
    print("=== Building FikaShare Standalone Executable ===")
    
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name=FikaShare",
        "--add-data=profile_parser.py:.",
        "--add-data=sync_engine.py:.",
        "--add-data=upnp_tunnel.py:.",
        "--add-data=server.py:.",
        "--add-data=client.py:.",
        "--add-data=gui.py:.",
        "main.py"
    ]

    # Convert path separator for Windows if needed
    if sys.platform == "win32":
        cmd = [c.replace(":", ";") if ":" in c and "--add-data" in c else c for c in cmd]

    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("\n[Build Success] Executable created in dist/FikaShare/")
    else:
        print(f"\n[Build Failed] Exit code: {result.returncode}")

if __name__ == "__main__":
    build_executable()
