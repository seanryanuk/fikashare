# FikaShare - Tarkov SPT Fika Profile Sync Application

FikaShare is a portable Python desktop application built with PySide6 (Qt) designed to synchronize Single Player Tarkov (SPT) Fika player profiles between a server host and client friends.

## Features

- **Unified Client & Server GUI**: Run as a client to sync your profile or host a server for your friends with a simple toggle switch.
- **Visual Profile Dashboard**: Display profile cards with PMC Nickname, Level, Faction (USEC/BEAR), Profile ID, Location Badges (`Local Only`, `Server Only`, `Local & Server`), and Sync Badges (`In Sync`, `Local Newer`, `Server Newer`).
- **Smart Button Guardrails**:
  - **Upload to Server**: Enabled only if the profile exists locally.
  - **Download from Server**: Enabled only if the profile exists on the server host (with a dropdown for **Download Custom Location**).
- **Zero Port Forwarding**: Automatic UPnP router port mapping + friendly connection codes (`FIKA-XXXX`).
- **Safety Backups Outside SPT**: All safety backups are created in `FikaShare_Backups/` outside the SPT folder to guarantee Fika / SPT Server never breaks from extra non-profile files.
- **Process Safety Inspection**: Warns if SPT Server (`Aki.Server.exe` / `SPT.Server.exe`) or Tarkov is currently running before performing a profile sync.

---

## Quick Start & Usage

### 1. Client Mode (Syncing your profile)
1. Get the **Connection Code** (`FIKA-XXXX`) from your Fika server host.
2. Paste the code into the **Server Connection** box on the **Client Profile Sync** tab.
3. Click **Connect**. Your profiles and remote profiles will load.
4. Click **Upload** or **Download** (or click the arrow next to Download for **Download Custom Location**).

### 2. Hosting Mode (Serving your friends)
1. Go to the **Host Server** tab.
2. Enter your SPT installation path (or auto-detect it in Settings).
3. Click **START HOSTING SERVER**.
4. Click **Copy Code** and send the `FIKA-XXXX` Connection Code to your friends!

---

## Developer Guide: Local Setup & Building Executables

FikaShare is 100% cross-platform and runs natively on both **Windows** and **Linux**.

### Running from Python Source
Requires Python 3.10+.

```bash
# Install dependencies
pip install -r requirements.txt

# Run application GUI
python main.py
```

### Building Standalone Executables locally

PyInstaller compiles native executables for the host OS where it is executed:

- **On Windows**: Run `python build.py` to create `dist/FikaShare/FikaShare.exe`.
- **On Linux**: Run `python build.py` to create `dist/FikaShare/FikaShare`.

---

## GitHub Setup & Automated Releases Guide

FikaShare includes an automated GitHub Actions CI/CD workflow ([.github/workflows/build.yml](file:///.github/workflows/build.yml)) that compiles Windows & Linux binaries and publishes GitHub Releases automatically.

### Initial GitHub Repository Setup

1. **Create Repository on GitHub**:
   - Go to [github.com/new](https://github.com/new).
   - Enter repository name: `fikashare`.
   - Select **Public** (for unlimited free GitHub Actions build minutes).
   - Leave "Add a README file" **UNCHECKED**.
   - Click **Create repository**.

2. **Push Local Code to GitHub**:
   ```bash
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/fikashare.git
   git push -u origin main
   ```

---

### How to Publish a New Release for Users

Whenever you want to publish a new version for your users with pre-compiled Windows & Linux download files attached:

1. **Tag a new version and push it to GitHub**:
   ```bash
   # Push any new code changes first
   git push

   # Create and push a version tag
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **What Happens Automatically**:
   - GitHub Actions will trigger, spinning up Linux and Windows runners.
   - It compiles `FikaShare-Windows.zip` and `FikaShare-Linux.tar.gz`.
   - It automatically creates a new GitHub Release under `https://github.com/YOUR_USERNAME/fikashare/releases` and attaches both zip files under **Assets**.

3. **How Users Download**:
   Direct your friends to `https://github.com/YOUR_USERNAME/fikashare/releases/latest` to download the executable for their OS!

---

### Versioning & Safety Tips

- **Duplicate Tag Protection**: Git prevents you from accidentally reusing an existing tag locally (`fatal: tag 'v1.0.0' already exists`).
- **Bumping Versions**: For future updates, simply increment the tag number (e.g. `v1.0.1`, `v1.1.0`, `v2.0.0`).
- **Overwriting a Tag**: If you ever force-push an updated tag (`git tag -f v1.0.0`), the workflow will safely update the existing release and replace the attached binaries without crashing.
