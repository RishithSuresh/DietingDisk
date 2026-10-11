# DietingDisk — Windows Storage Auditor

DietingDisk is a local desktop storage inventory and analysis tool built with Python, FastAPI, SQLite, and a web UI embedded using pywebview.

## Features in this build

- Read-only drive inventory with scan issue reporting.
- Storage analytics: file-extension breakdown, largest folders, and inventory totals.
- Explainable conservative file classification with reasons and confidence wording.
- Optional classification refresh that updates only DietingDisk's SQLite metadata, never files on scanned drives. It checks available disk space before starting because a large SQLite write-ahead log may temporarily need extra space.
- Interactive one-level-at-a-time storage treemap with folder drill-down and file details.
- Searchable file inventory and CSV export.

## Important safety notes

- No feature deletes, moves, or renames files on scanned drives.
- Classification is advisory. `REVIEW` does not mean safe to delete.
- Game assets, application data, databases, user documents, and model/dataset files are classified conservatively.
- Parent folder sizes include descendants. Do not add nested folder totals together.
- The treemap requests only one folder level at a time so the entire inventory is not loaded into the UI.
- The app-data folder name in `backend/config.py` intentionally remains `DietDisk` to preserve the existing database location used by this installation. Do not rename that setting unless you deliberately migrate the existing database.

## Run on Windows

Use the project's existing Python virtual environment if already configured. From the project folder:

```powershell
python -m pip install -r requirements.txt
python main.py
```

Run tests:

```powershell
python -m pytest -q
```

## Database location

By default, the application uses `%LOCALAPPDATA%\DietDisk\DietDisk.sqlite3`. An environment variable named `DietDisk_DATA_DIR` can override the data directory. Keep the database and its SQLite `-wal` / `-shm` companion files together while the app is running.
