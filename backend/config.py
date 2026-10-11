"""Configuration and application-data paths for DietDisk."""
from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "DietDisk"
APP_DATA_DIR = Path(os.environ.get("DietDisk_DATA_DIR", str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_NAME)))
# DietDisk_DATA_DIR is the full data directory override, useful when the system drive is low on space.
DATABASE_PATH = APP_DATA_DIR / "DietDisk.sqlite3"
REPORTS_DIR = APP_DATA_DIR / "reports"

# Metadata/system locations that are deliberately not traversed. They are recorded
# as exclusions in the scan summary. Directory junctions and symlinks are also skipped.
EXCLUDED_DIRECTORY_NAMES = {
    "$Recycle.Bin",
    "System Volume Information",
}
DEFAULT_DRIVES = ["C:\\", "D:\\"]

# No scanning path is ever treated as permission to delete anything.
