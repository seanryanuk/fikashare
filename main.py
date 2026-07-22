import sys
import os
import argparse
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from gui import FikaShareGUI

def main():
    parser = argparse.ArgumentParser(description="FikaShare - Tarkov SPT Fika Profile Sync")
    parser.add_argument("--spt-dir", help="Path to SPT installation directory")
    args = parser.parse_args()

    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("FikaShare")
    app.setOrganizationName("FikaShareTeam")

    window = FikaShareGUI()
    if args.spt_dir and os.path.exists(args.spt_dir):
        window.spt_dir = args.spt_dir
        window.path_edit.setText(args.spt_dir)
        window.save_config()
        window.refresh_profiles_list()

    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
