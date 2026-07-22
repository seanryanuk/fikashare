# FikaShare - Tarkov SPT Fika Profile Sync Application

FikaShare is a portable Python application built with PySide6 (Qt) designed to synchronize Single Player Tarkov (SPT) Fika player profiles between a server host and client friends.

## Features

- **Unified Client & Server GUI**: Run as a client to sync your profile or host a server for your friends with a simple toggle switch.
- **Visual Profile Dashboard**: Display profile cards with PMC Nickname, Level, Faction (USEC/BEAR), Profile ID, Location Badges ("Local Only", "Server Only", "Local & Server"), and Sync Badges ("In Sync", "Local Newer", "Server Newer").
- **Smart Button Guardrails**:
  - **Upload to Server**: Enabled only if the profile exists locally.
  - **Download from Server**: Enabled only if the profile exists on the server host.
- **Zero Port Forwarding**: Automatic UPnP router port mapping + friendly connection codes (`FIKA-XXXX`).
- **Safety Backups Outside SPT**: All safety backups are created in `FikaShare_Backups/` outside the SPT folder to guarantee Fika / SPT Server never breaks from extra non-profile files.
- **Process Safety Inspection**: Warns if SPT Server (`Aki.Server.exe` / `SPT.Server.exe`) or Tarkov is currently running before performing a profile sync.

## Quick Start & Cross-Platform Usage

FikaShare is 100% cross-platform and runs natively on both **Windows** and **Linux**.

### Option A: Run from Python Source (Linux & Windows)
Make sure you have Python 3.10+ installed.

```bash
# Install dependencies
pip install -r requirements.txt

# Run FikaShare GUI
python main.py
```

---

### Option B: Build Portable Standalone Executables

PyInstaller compiles OS-native executables on the host platform where it is executed:

1. **On Windows**:
   Run `python build.py` on a Windows PC to generate `dist/FikaShare/FikaShare.exe`.
2. **On Linux**:
   Run `python build.py` on a Linux PC to generate `dist/FikaShare/FikaShare`.

#### Automatic Multi-OS Builds via GitHub Actions
A included workflow [build.yml](file:///home/tech1337/Development/fikashare/.github/workflows/build.yml) automatically compiles both `FikaShare-Windows.zip` and `FikaShare-Linux.tar.gz` every time you push code or create a tag on GitHub!

---

### 3. Client Mode (Syncing your profile)
1. Get the **Connection Code** (`FIKA-XXXX`) from your Fika server host.
2. Paste the code into the **Server Connection** box on the **Client Profile Sync** tab.
3. Click **Connect**. Your profiles and remote profiles will load.
4. Click **Upload** or **Download** (or use the dropdown menu for **Download (Custom Location)**).

### 4. Hosting Mode (Serving your friends)
1. Go to the **Host Server** tab.
2. Enter your SPT installation path (or auto-detect it in Settings).
3. Click **START HOSTING SERVER**.
4. Click **Copy Code** and send the `FIKA-XXXX` Connection Code to your friends!
