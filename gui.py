import os
import sys
import json
import subprocess
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize
from PySide6.QtGui import QFont, QIcon, QColor, QPalette, QClipboard, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTabWidget, QFrame, QScrollArea,
    QGridLayout, QMessageBox, QFileDialog, QPlainTextEdit, QCheckBox,
    QProgressBar, QStyle, QGraphicsDropShadowEffect, QToolButton, QMenu
)

from profile_parser import find_spt_directory, scan_local_profiles, ProfileInfo, resolve_profiles_dir
from sync_engine import SyncItem, SyncStatus, BackupManager, check_spt_processes
from server import FikaShareServer
from client import FikaClient
from upnp_tunnel import ConnectionCode

# Theme Stylesheet QSS
DARK_THEME_QSS = """
QMainWindow {
    background-color: #0b0f19;
}
QWidget {
    background-color: #0b0f19;
    color: #e2e8f0;
    font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #1e293b;
    background-color: #0b0f19;
    top: -1px;
}
QTabBar::tab {
    background: #0f172a;
    color: #94a3b8;
    padding: 10px 22px;
    font-weight: bold;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 4px;
    border: 1px solid #1e293b;
}
QTabBar::tab:selected {
    background: #1e293b;
    color: #00e676;
    border-bottom: 2px solid #00e676;
}
QTabBar::tab:hover {
    background: #1e293b;
    color: #f8fafc;
}
QFrame.CardFrame {
    background-color: #161e2e;
    border: 1px solid #232d3f;
    border-radius: 12px;
}
QFrame.CardFrame:hover {
    border: 1px solid #3b82f6;
}
QLineEdit {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 8px 12px;
    color: #f8fafc;
    selection-background-color: #00e676;
    selection-color: #0f172a;
}
QLineEdit:focus {
    border: 1px solid #00e676;
}
QPushButton {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #334155;
    border-color: #475569;
}
QPushButton:pressed {
    background-color: #0f172a;
}
QPushButton.PrimaryBtn {
    background-color: #00c853;
    color: #091b11;
    border: none;
    font-weight: 700;
}
QPushButton.PrimaryBtn:hover {
    background-color: #00e676;
}
QPushButton.PrimaryBtn:disabled {
    background-color: #1e3a2b;
    color: #4a7a60;
}
QPushButton.AccentBtn {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
}
QPushButton.AccentBtn:hover {
    background-color: #3b82f6;
}
QPushButton.AccentBtn:disabled {
    background-color: #1e293b;
    color: #475569;
}
QPushButton.DangerBtn {
    background-color: #dc2626;
    color: #ffffff;
    border: none;
}
QPushButton.DangerBtn:hover {
    background-color: #ef4444;
}
QToolButton {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: bold;
}
QToolButton:hover {
    background-color: #3b82f6;
}
QToolButton:disabled {
    background-color: #1e293b;
    color: #475569;
}
QToolButton::menu-button {
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
    width: 22px;
    background-color: transparent;
    border-left: 1px solid #1d4ed8;
}
QToolButton::menu-button:hover {
    background-color: #1d4ed8;
}
QMenu {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    color: #f8fafc;
    padding: 4px;
}
QMenu::item {
    padding: 8px 16px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}
QPlainTextEdit {
    background-color: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 6px;
    color: #38bdf8;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
}
QScrollArea {
    border: none;
    background-color: transparent;
}
QScrollBar:vertical {
    background: #0f172a;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #334155;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #475569;
}
"""

class ProfileCardWidget(QFrame):
    """Custom Qt Widget representing a single Tarkov profile status card."""

    upload_requested = Signal(str)            # profile_id
    download_requested = Signal(str)          # profile_id
    download_custom_requested = Signal(str)   # profile_id

    def __init__(self, item: SyncItem, parent=None):
        super().__init__(parent)
        self.item = item
        self.setObjectName("ProfileCard")
        self.setProperty("class", "CardFrame")
        self.setStyleSheet("""
            QFrame#ProfileCard {
                background-color: #161e2e;
                border: 1px solid #232d3f;
                border-radius: 10px;
                padding: 14px;
            }
            QFrame#ProfileCard:hover {
                border: 1px solid #00e676;
            }
        """)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header Row: Avatar side badge + Nickname + Level badge
        header_layout = QHBoxLayout()
        
        # Side badge (USEC/BEAR)
        side = self.item.display_side
        side_color = "#3b82f6" if side == "USEC" else "#ef4444" if side == "BEAR" else "#64748b"
        side_label = QLabel(f" {side} ")
        side_label.setStyleSheet(f"""
            background-color: {side_color};
            color: #ffffff;
            font-weight: bold;
            font-size: 10px;
            border-radius: 4px;
            padding: 2px 6px;
        """)
        header_layout.addWidget(side_label)

        # Nickname
        nickname_lbl = QLabel(self.item.display_name)
        nickname_lbl.setFont(QFont("Segoe UI", 14, QFont.Bold))
        nickname_lbl.setStyleSheet("color: #f8fafc;")
        header_layout.addWidget(nickname_lbl)
        header_layout.addStretch()

        # Level badge
        lvl_lbl = QLabel(f"LVL {self.item.display_level}")
        lvl_lbl.setStyleSheet("""
            background-color: #0f172a;
            color: #00e676;
            font-weight: bold;
            font-size: 11px;
            border: 1px solid #00e676;
            border-radius: 4px;
            padding: 2px 8px;
        """)
        header_layout.addWidget(lvl_lbl)
        layout.addLayout(header_layout)

        # Profile ID Subtitle
        pid_lbl = QLabel(f"ID: {self.item.profile_id}")
        pid_lbl.setStyleSheet("color: #64748b; font-size: 11px; font-family: monospace;")
        layout.addWidget(pid_lbl)

        # Status Badges Row
        badge_layout = QHBoxLayout()
        
        # Location badge
        loc_bg = "#1e293b"
        loc_color = "#94a3b8"
        if self.item.location_badge == "Local & Server":
            loc_bg = "#064e3b"
            loc_color = "#34d399"
        elif self.item.location_badge == "Local Only":
            loc_bg = "#1e3a5f"
            loc_color = "#60a5fa"
        elif self.item.location_badge == "Server Only":
            loc_bg = "#4c1d95"
            loc_color = "#c084fc"

        loc_lbl = QLabel(f"Location: {self.item.location_badge}")
        loc_lbl.setStyleSheet(f"""
            background-color: {loc_bg};
            color: {loc_color};
            font-weight: 600;
            font-size: 11px;
            border-radius: 4px;
            padding: 3px 8px;
        """)
        badge_layout.addWidget(loc_lbl)

        # Sync Status badge
        sync_bg = "#1e293b"
        sync_color = "#94a3b8"
        if self.item.status == SyncStatus.IN_SYNC:
            sync_bg = "#065f46"
            sync_color = "#6ee7b7"
        elif self.item.status == SyncStatus.LOCAL_NEWER:
            sync_bg = "#78350f"
            sync_color = "#fde047"
        elif self.item.status == SyncStatus.REMOTE_NEWER:
            sync_bg = "#1e40af"
            sync_color = "#93c5fd"

        sync_lbl = QLabel(self.item.status_badge)
        sync_lbl.setStyleSheet(f"""
            background-color: {sync_bg};
            color: {sync_color};
            font-weight: 600;
            font-size: 11px;
            border-radius: 4px;
            padding: 3px 8px;
        """)
        badge_layout.addWidget(sync_lbl)
        badge_layout.addStretch()
        layout.addLayout(badge_layout)

        # Timestamps info
        local_time_str = self.item.local_info.mtime_formatted if self.item.local_info else "None"
        remote_time_str = self.item.remote_info.mtime_formatted if self.item.remote_info else "None"
        time_info = QLabel(f"Local: {local_time_str}  |  Server: {remote_time_str}")
        time_info.setStyleSheet("color: #64748b; font-size: 10px;")
        layout.addWidget(time_info)

        # Action Buttons Row
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        # Upload Button
        self.upload_btn = QPushButton(" Upload to Server")
        self.upload_btn.setProperty("class", "PrimaryBtn")
        self.upload_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #ffffff;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #10b981; }
            QPushButton:disabled { background-color: #1e293b; color: #475569; }
        """)
        self.upload_btn.setEnabled(self.item.can_upload)
        self.upload_btn.clicked.connect(lambda: self.upload_requested.emit(self.item.profile_id))
        btn_layout.addWidget(self.upload_btn)

        # Download Dropdown ToolButton
        self.download_btn = QToolButton()
        self.download_btn.setText(" Download from Server")
        self.download_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self.download_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)

        dl_menu = QMenu(self.download_btn)
        custom_dl_action = dl_menu.addAction("Download (Custom Location)")
        custom_dl_action.triggered.connect(lambda: self.download_custom_requested.emit(self.item.profile_id))
        self.download_btn.setMenu(dl_menu)

        self.download_btn.setEnabled(self.item.can_download)
        self.download_btn.clicked.connect(lambda: self.download_requested.emit(self.item.profile_id))
        btn_layout.addWidget(self.download_btn)

        layout.addLayout(btn_layout)


class FikaShareGUI(QMainWindow):
    """Main Application Window for FikaShare."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FikaShare - Tarkov SPT Profile Synchronizer")
        self.resize(1000, 720)
        self.setMinimumSize(850, 600)

        # Core State
        self.config_file = os.path.join(os.getcwd(), "fikashare_config.json")
        self.spt_dir = ""
        self.backup_mgr = BackupManager()
        self.server = FikaShareServer(log_callback=self.log_server_activity)
        self.client = FikaClient()
        self.sync_items: Dict[str, SyncItem] = {}

        self.load_config()
        self.init_ui()
        self.setStyleSheet(DARK_THEME_QSS)

        # Auto-detect SPT if not set
        if not self.spt_dir:
            detected = find_spt_directory()
            if detected:
                self.spt_dir = detected
                self.save_config()

        self.path_edit.setText(self.spt_dir)
        self.refresh_profiles_list()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    cfg = json.load(f)
                    self.spt_dir = cfg.get("spt_dir", "")
                    self.last_connection_code = cfg.get("connection_code", "")
                    self.server_port = cfg.get("server_port", 8585)
                    self.server_passphrase = cfg.get("server_passphrase", "")
            except Exception as e:
                print(f"[Config] Load error: {e}")
        else:
            self.last_connection_code = ""
            self.server_port = 8585
            self.server_passphrase = ""

    def save_config(self):
        try:
            cfg = {
                "spt_dir": self.spt_dir,
                "connection_code": getattr(self, 'conn_input', QLineEdit()).text(),
                "server_port": self.server_port,
                "server_passphrase": self.server_passphrase
            }
            with open(self.config_file, 'w') as f:
                json.dump(cfg, f, indent=2)
        except Exception as e:
            print(f"[Config] Save error: {e}")

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # Title Header
        title_box = QHBoxLayout()
        title_lbl = QLabel("FIKASHARE")
        title_lbl.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title_lbl.setStyleSheet("color: #00e676; letter-spacing: 2px;")
        
        subtitle_lbl = QLabel("Tarkov SPT Profile Sync & Host Engine")
        subtitle_lbl.setStyleSheet("color: #64748b; font-size: 13px; margin-left: 10px;")

        title_box.addWidget(title_lbl)
        title_box.addWidget(subtitle_lbl)
        title_box.addStretch()
        main_layout.addLayout(title_box)

        # Tab Widget
        self.tabs = QTabWidget()
        
        # Tab 1: Client Sync
        self.tab_client = QWidget()
        self.init_client_tab()
        self.tabs.addTab(self.tab_client, "Client Profile Sync")

        # Tab 2: Server Host
        self.tab_server = QWidget()
        self.init_server_tab()
        self.tabs.addTab(self.tab_server, "Host Server")

        # Tab 3: Settings
        self.tab_settings = QWidget()
        self.init_settings_tab()
        self.tabs.addTab(self.tab_settings, "Settings & Paths")

        main_layout.addWidget(self.tabs)
        self.setCentralWidget(main_widget)

    def init_client_tab(self):
        layout = QVBoxLayout(self.tab_client)
        layout.setSpacing(12)

        # Connection Bar Frame
        conn_frame = QFrame()
        conn_frame.setProperty("class", "CardFrame")
        conn_layout = QHBoxLayout(conn_frame)

        conn_lbl = QLabel("Server Connection:")
        conn_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))

        self.conn_input = QLineEdit()
        self.conn_input.setPlaceholderText("Enter Connection Code (FIKA-XXXX) or Host IP:Port (e.g. 192.168.1.50:8585)")
        self.conn_input.setText(self.last_connection_code)

        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("Passphrase (Optional)")
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.pass_input.setMaximumWidth(160)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setProperty("class", "PrimaryBtn")
        self.connect_btn.clicked.connect(self.on_connect_clicked)

        conn_layout.addWidget(conn_lbl)
        conn_layout.addWidget(self.conn_input)
        conn_layout.addWidget(self.pass_input)
        conn_layout.addWidget(self.connect_btn)
        layout.addWidget(conn_frame)

        # Status Bar & Quick Actions
        action_layout = QHBoxLayout()
        self.client_status_lbl = QLabel("Status: Disconnected (Local Profiles Only)")
        self.client_status_lbl.setStyleSheet("color: #94a3b8; font-weight: bold;")
        action_layout.addWidget(self.client_status_lbl)
        action_layout.addStretch()

        self.sync_all_btn = QPushButton("Sync All Newer Profiles")
        self.sync_all_btn.setProperty("class", "PrimaryBtn")
        self.sync_all_btn.clicked.connect(self.on_sync_all_clicked)
        self.sync_all_btn.setEnabled(False)

        self.refresh_btn = QPushButton(" Refresh")
        self.refresh_btn.clicked.connect(self.refresh_profiles_list)

        self.open_spt_btn = QPushButton("Open SPT Directory")
        self.open_spt_btn.clicked.connect(self.open_spt_folder)

        self.open_backup_btn = QPushButton("Open Backups Directory")
        self.open_backup_btn.clicked.connect(self.open_backup_folder)

        action_layout.addWidget(self.sync_all_btn)
        action_layout.addWidget(self.refresh_btn)
        action_layout.addWidget(self.open_spt_btn)
        action_layout.addWidget(self.open_backup_btn)
        layout.addLayout(action_layout)

        # Scroll Area for Profile Cards
        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(12)
        self.cards_layout.addStretch()
        
        self.cards_scroll.setWidget(self.cards_container)
        layout.addWidget(self.cards_scroll)

    def init_server_tab(self):
        layout = QVBoxLayout(self.tab_server)
        layout.setSpacing(16)

        # Top Control Frame
        srv_frame = QFrame()
        srv_frame.setProperty("class", "CardFrame")
        srv_layout = QVBoxLayout(srv_frame)

        srv_title = QLabel("Host FikaShare Server")
        srv_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        srv_title.setStyleSheet("color: #00e676;")
        srv_layout.addWidget(srv_title)

        srv_desc = QLabel("Start hosting to let your friends upload/download their player profiles before game sessions.")
        srv_desc.setStyleSheet("color: #94a3b8;")
        srv_layout.addWidget(srv_desc)

        # Form Inputs
        form_layout = QGridLayout()
        
        form_layout.addWidget(QLabel("Server Port:"), 0, 0)
        self.srv_port_input = QLineEdit(str(self.server_port))
        self.srv_port_input.setMaximumWidth(120)
        form_layout.addWidget(self.srv_port_input, 0, 1)

        form_layout.addWidget(QLabel("Security Passphrase:"), 0, 2)
        self.srv_pass_input = QLineEdit(self.server_passphrase)
        self.srv_pass_input.setPlaceholderText("Optional host password")
        form_layout.addWidget(self.srv_pass_input, 0, 3)

        self.upnp_check = QCheckBox("Attempt Automatic UPnP Router Port Forwarding")
        self.upnp_check.setChecked(True)
        form_layout.addWidget(self.upnp_check, 1, 0, 1, 4)

        srv_layout.addLayout(form_layout)

        # Toggle Host Button
        self.host_toggle_btn = QPushButton("START HOSTING SERVER")
        self.host_toggle_btn.setProperty("class", "PrimaryBtn")
        self.host_toggle_btn.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.host_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #00c853;
                color: #05140b;
                padding: 12px 24px;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #00e676; }
        """)
        self.host_toggle_btn.clicked.connect(self.on_toggle_host_clicked)
        srv_layout.addWidget(self.host_toggle_btn)

        layout.addWidget(srv_frame)

        # Shareable Connection Code Display Frame
        self.code_frame = QFrame()
        self.code_frame.setProperty("class", "CardFrame")
        code_layout = QVBoxLayout(self.code_frame)
        
        code_title = QLabel("SHAREABLE CONNECTION CODE")
        code_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        code_title.setStyleSheet("color: #38bdf8;")
        code_layout.addWidget(code_title)

        code_sub = QLabel("Send this code to your friends so they can paste it in their Client tab:")
        code_sub.setStyleSheet("color: #94a3b8; font-size: 11px;")
        code_layout.addWidget(code_sub)

        code_row = QHBoxLayout()
        self.code_display = QLineEdit()
        self.code_display.setReadOnly(True)
        self.code_display.setFont(QFont("Consolas", 14, QFont.Bold))
        self.code_display.setStyleSheet("background-color: #0f172a; color: #00e676; padding: 10px;")

        self.copy_code_btn = QPushButton("Copy Code")
        self.copy_code_btn.setProperty("class", "PrimaryBtn")
        self.copy_code_btn.clicked.connect(self.copy_connection_code)

        code_row.addWidget(self.code_display)
        code_row.addWidget(self.copy_code_btn)
        code_layout.addLayout(code_row)

        self.srv_network_info = QLabel("Server Inactive")
        self.srv_network_info.setStyleSheet("color: #64748b; font-size: 11px;")
        code_layout.addWidget(self.srv_network_info)

        layout.addWidget(self.code_frame)

        # Live Activity Log Frame
        log_lbl = QLabel("Live Server Activity Log:")
        log_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
        layout.addWidget(log_lbl)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

    def init_settings_tab(self):
        layout = QVBoxLayout(self.tab_settings)
        layout.setSpacing(16)

        sett_frame = QFrame()
        sett_frame.setProperty("class", "CardFrame")
        sett_layout = QVBoxLayout(sett_frame)

        sett_title = QLabel("Tarkov SPT Directory Setup")
        sett_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        sett_title.setStyleSheet("color: #00e676;")
        sett_layout.addWidget(sett_title)

        sett_desc = QLabel("Set your local Tarkov SPT installation directory (containing user/profiles).")
        sett_desc.setStyleSheet("color: #94a3b8;")
        sett_layout.addWidget(sett_desc)

        path_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Select SPT Root Folder (e.g. C:\\SPT or /home/user/SPT)")

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_spt_directory)

        self.autodetect_btn = QPushButton("Auto-Detect")
        self.autodetect_btn.clicked.connect(self.auto_detect_spt)

        path_row.addWidget(self.path_edit)
        path_row.addWidget(self.browse_btn)
        path_row.addWidget(self.autodetect_btn)
        sett_layout.addLayout(path_row)

        layout.addWidget(sett_frame)

        # Backup Info Box
        backup_frame = QFrame()
        backup_frame.setProperty("class", "CardFrame")
        b_layout = QVBoxLayout(backup_frame)

        b_title = QLabel("Safety Backup Policy")
        b_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        b_layout.addWidget(b_title)

        b_desc = QLabel(
            "To protect your progress, FikaShare creates automatic timestamped backups BEFORE any upload or download.\n\n"
            f"Backups Directory: {self.backup_mgr.backup_dir}\n"
            "Backups are strictly kept OUTSIDE your SPT folder to prevent breaking Fika or SPT Server."
        )
        b_desc.setStyleSheet("color: #cbd5e1; line-height: 1.4;")
        b_layout.addWidget(b_desc)

        open_b_btn = QPushButton("Open Backups Directory")
        open_b_btn.setMaximumWidth(200)
        open_b_btn.clicked.connect(self.open_backup_folder)
        b_layout.addWidget(open_b_btn)

        layout.addWidget(backup_frame)
        layout.addStretch()

    # Client Actions
    def on_connect_clicked(self):
        conn_str = self.conn_input.text().strip()
        passphrase = self.pass_input.text().strip()

        if not conn_str:
            QMessageBox.warning(self, "Input Required", "Please enter a Connection Code or Server Host IP:Port.")
            return

        if not self.client.set_connection(conn_str, passphrase):
            QMessageBox.critical(self, "Invalid Code", "Failed to parse Connection Code or Host address.")
            return

        success, msg = self.client.test_connection()
        if success:
            self.client_status_lbl.setText(f"Status: Connected to {self.client.host}:{self.client.port}")
            self.client_status_lbl.setStyleSheet("color: #00e676; font-weight: bold;")
            self.sync_all_btn.setEnabled(True)
            self.save_config()
            self.refresh_profiles_list()
        else:
            self.client_status_lbl.setText(f"Status: Connection Failed ({msg})")
            self.client_status_lbl.setStyleSheet("color: #ef4444; font-weight: bold;")
            self.sync_all_btn.setEnabled(False)
            QMessageBox.critical(self, "Connection Error", f"Could not connect to FikaShare Server:\n\n{msg}")

    def refresh_profiles_list(self):
        # Scan local profiles
        local_profiles = scan_local_profiles(self.spt_dir)
        
        # Fetch remote profiles if connected
        remote_profiles = {}
        if self.client.is_connected:
            ok, r_profs, err = self.client.fetch_remote_profiles()
            if ok:
                remote_profiles = r_profs
            else:
                self.client_status_lbl.setText(f"Status: Server Sync Error ({err})")
                self.client_status_lbl.setStyleSheet("color: #ef4444; font-weight: bold;")

        # Combine profile IDs
        all_ids = set(local_profiles.keys()) | set(remote_profiles.keys())
        self.sync_items.clear()

        for pid in all_ids:
            item = SyncItem(pid, local_profiles.get(pid), remote_profiles.get(pid))
            self.sync_items[pid] = item

        # Clear existing cards
        while self.cards_layout.count() > 1:
            child = self.cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Render cards
        if not self.sync_items:
            no_lbl = QLabel("No SPT profiles found locally or on server.\nMake sure your SPT Directory is correctly set in Settings.")
            no_lbl.setAlignment(Qt.AlignCenter)
            no_lbl.setStyleSheet("color: #64748b; font-size: 14px; margin: 40px;")
            self.cards_layout.insertWidget(0, no_lbl)
        else:
            for item in sorted(self.sync_items.values(), key=lambda x: x.display_name):
                card = ProfileCardWidget(item)
                card.upload_requested.connect(self.on_upload_requested)
                card.download_requested.connect(self.on_download_requested)
                card.download_custom_requested.connect(self.on_download_custom_requested)
                self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

    def _warn_if_spt_running(self) -> bool:
        """Returns True if safe to proceed, False if user cancelled due to process running."""
        is_running, procs = check_spt_processes()
        if is_running:
            proc_list = ", ".join(procs)
            res = QMessageBox.warning(
                self,
                "SPT / Tarkov Process Active",
                f"Warning: The following Tarkov/SPT processes are currently running:\n\n{proc_list}\n\n"
                "Syncing while the server or game is running may cause profile corruption or lost progress!\n"
                "Are you sure you want to proceed with sync?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            return res == QMessageBox.Yes
        return True

    def on_upload_requested(self, profile_id: str):
        if not self._warn_if_spt_running():
            return

        if not self.client.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to a FikaShare server first.")
            return

        ok, msg = self.client.upload_profile(profile_id, self.spt_dir)
        if ok:
            QMessageBox.information(self, "Upload Complete", f"Successfully uploaded profile {profile_id} to server.")
            self.refresh_profiles_list()
        else:
            QMessageBox.critical(self, "Upload Failed", msg)

    def on_download_requested(self, profile_id: str):
        if not self._warn_if_spt_running():
            return

        if not self.client.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to a FikaShare server first.")
            return

        ok, msg = self.client.download_profile(profile_id, self.spt_dir)
        if ok:
            QMessageBox.information(self, "Download Complete", f"Successfully downloaded profile {profile_id} from server.")
            self.refresh_profiles_list()
        else:
            QMessageBox.critical(self, "Download Failed", msg)

    def on_download_custom_requested(self, profile_id: str):
        if not self._warn_if_spt_running():
            return

        if not self.client.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to a FikaShare server first.")
            return

        default_name = f"{profile_id}.json"
        target_file, _ = QFileDialog.getSaveFileName(
            self,
            "Download Profile to Custom Location",
            os.path.join(os.getcwd(), default_name),
            "JSON Files (*.json);;All Files (*)"
        )

        if not target_file:
            return  # User cancelled dialog

        ok, msg = self.client.download_profile_to_path(profile_id, target_file)
        if ok:
            QMessageBox.information(
                self,
                "Custom Download Complete",
                f"Successfully downloaded profile {profile_id} to:\n{target_file}"
            )
            self.refresh_profiles_list()
        else:
            QMessageBox.critical(self, "Download Failed", msg)

    def on_sync_all_clicked(self):
        if not self.client.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to a FikaShare server first.")
            return

        if not self._warn_if_spt_running():
            return

        synced_count = 0
        errors = []

        for pid, item in self.sync_items.items():
            if item.status == SyncStatus.LOCAL_NEWER:
                ok, msg = self.client.upload_profile(pid, self.spt_dir)
                if ok:
                    synced_count += 1
                else:
                    errors.append(f"Upload {pid}: {msg}")
            elif item.status == SyncStatus.REMOTE_NEWER:
                ok, msg = self.client.download_profile(pid, self.spt_dir)
                if ok:
                    synced_count += 1
                else:
                    errors.append(f"Download {pid}: {msg}")

        self.refresh_profiles_list()
        if errors:
            QMessageBox.warning(self, "Sync Finished with Warnings", f"Synced {synced_count} profiles.\nErrors:\n" + "\n".join(errors))
        else:
            QMessageBox.information(self, "Sync Complete", f"Successfully synced {synced_count} profiles!")

    # Server Host Actions
    def on_toggle_host_clicked(self):
        if self.server.is_running:
            self.server.stop()
            self.host_toggle_btn.setText("START HOSTING SERVER")
            self.host_toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #00c853;
                    color: #05140b;
                    padding: 12px 24px;
                    border-radius: 8px;
                }
                QPushButton:hover { background-color: #00e676; }
            """)
            self.code_display.setText("")
            self.srv_network_info.setText("Server Inactive")
        else:
            if not self.spt_dir or not os.path.exists(self.spt_dir):
                QMessageBox.critical(self, "SPT Path Required", "Please configure your SPT Directory in Settings before hosting!")
                self.tabs.setCurrentIndex(2)
                return

            try:
                port = int(self.srv_port_input.text().strip())
            except ValueError:
                port = 8585

            passphrase = self.srv_pass_input.text().strip()
            enable_upnp = self.upnp_check.isChecked()

            success = self.server.start(self.spt_dir, port, passphrase, enable_upnp)
            if success:
                self.server_port = port
                self.server_passphrase = passphrase
                self.save_config()

                self.host_toggle_btn.setText("STOP SERVER")
                self.host_toggle_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #dc2626;
                        color: #ffffff;
                        padding: 12px 24px;
                        border-radius: 8px;
                    }
                    QPushButton:hover { background-color: #ef4444; }
                """)

                # Display connection code
                code = self.server.get_connection_code()
                self.code_display.setText(code)
                
                info_text = f"LAN IP: {self.server.local_ip}:{port}"
                if self.server.public_ip:
                    info_text += f"  |  Public IP: {self.server.public_ip}:{port}"
                self.srv_network_info.setText(info_text)

    def copy_connection_code(self):
        code = self.code_display.text().strip()
        if code:
            QApplication.clipboard().setText(code)
            QMessageBox.information(self, "Copied", "Connection Code copied to clipboard!")

    def log_server_activity(self, msg: str):
        QTimer.singleShot(0, lambda: self.log_text.appendPlainText(msg))

    # Path Helpers
    def browse_spt_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Select SPT Root Directory", self.spt_dir or os.getcwd())
        if folder:
            self.spt_dir = folder
            self.path_edit.setText(folder)
            self.save_config()
            self.refresh_profiles_list()

    def auto_detect_spt(self):
        detected = find_spt_directory()
        if detected:
            self.spt_dir = detected
            self.path_edit.setText(detected)
            self.save_config()
            self.refresh_profiles_list()
            QMessageBox.information(self, "SPT Detected", f"Found SPT installation at:\n{detected}")
        else:
            QMessageBox.warning(self, "Auto-Detect Failed", "Could not automatically locate an SPT installation directory.\nPlease use Browse to select it manually.")

    def open_spt_folder(self):
        if self.spt_dir and os.path.exists(self.spt_dir):
            p = resolve_profiles_dir(self.spt_dir)
            if not p:
                p = self.spt_dir
            self._open_in_file_explorer(p)
        else:
            QMessageBox.warning(self, "Invalid Path", "SPT Directory is not set or does not exist.")

    def open_backup_folder(self):
        b_dir = self.backup_mgr.backup_dir
        os.makedirs(b_dir, exist_ok=True)
        self._open_in_file_explorer(b_dir)

    def _open_in_file_explorer(self, path: str):
        try:
            if sys.platform == 'win32':
                os.startfile(path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', path])
            else:
                subprocess.run(['xdg-open', path])
        except Exception as e:
            QMessageBox.information(self, "Path", f"Directory Path:\n{path}")

    def closeEvent(self, event):
        if self.server.is_running:
            self.server.stop()
        event.accept()
