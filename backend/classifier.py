"""Conservative, explainable file classification. No category authorizes deletion."""
from __future__ import annotations
from pathlib import PureWindowsPath

SYSTEM_ROOTS = (
    "C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)",
    "C:\\ProgramData", "C:\\$Recycle.Bin", "C:\\System Volume Information",
)
DATA_EXTENSIONS = {
    ".pt", ".pth", ".onnx", ".safetensors", ".ckpt", ".h5", ".keras",
    ".pkl", ".pickle", ".parquet", ".feather", ".tfrecord", ".bin",
}
SOURCE_EXTENSIONS = {
    ".py", ".c", ".h", ".cpp", ".hpp", ".dart", ".js", ".ts", ".jsx",
    ".tsx", ".sql", ".html", ".css", ".java", ".ipynb", ".md", ".toml",
    ".yaml", ".yml", ".json", ".xml", ".sh", ".ps1",
}
ARCHIVE_EXTENSIONS = {".zip", ".7z", ".rar", ".iso", ".tar", ".gz", ".bak", ".old", ".log", ".exe", ".msi"}
CACHE_DIRS = {
    "node_modules", ".venv", "venv", "env", "__pycache__", ".gradle", ".npm",
    ".cache", "pip-cache", "temp", "tmp", "build", "dist",
}
DATA_DIR_HINTS = {
    "dataset", "datasets", "checkpoint", "checkpoints", "weights", "models",
    "model", "ff++", "ffpp", "dfdc", "celeb-df", "celebdv2", "asvspoof",
    "wavefake", "fakeavceleb", "deeperforensics",
}


def classify_path(path: str, is_directory: bool = False) -> tuple[str, str]:
    """Return (classification, explanation); this is advisory, never an action."""
    p = PureWindowsPath(path)
    normalized = str(p).replace("/", "\\").casefold()
    parts = {part.casefold() for part in p.parts}
    drive = p.drive.casefold()

    # Protect common system/application directory roots on any drive letter.
    parts_list = [part.casefold().rstrip("\\/") for part in p.parts]
    protected_first_level = {"windows", "program files", "program files (x86)", "programdata", "$recycle.bin", "system volume information"}
    if any(normalized == root.casefold() or normalized.startswith(root.casefold() + "\\")
           for root in SYSTEM_ROOTS) or (len(parts_list) >= 2 and parts_list[1] in protected_first_level):
        return "PROTECTED - SYSTEM / APPLICATION", "Located in a Windows or application system directory; do not manually remove."

    if parts & DATA_DIR_HINTS or p.suffix.casefold() in DATA_EXTENSIONS:
        return "PROTECT - DATA / MODEL CANDIDATE", "Path or file type resembles a dataset, model, checkpoint, or serialized data; verify purpose and backups."

    # Check cache-like directory components before source-file extensions: for example,
    # index.js inside node_modules is still a dependency candidate, not project source.
    cache_parts = CACHE_DIRS - {"tmp", "temp"}
    if parts & cache_parts or (bool(p.drive) and parts & {"tmp", "temp"}):
        return "REVIEW - POSSIBLE CACHE / REBUILD OUTPUT", "May be regenerable, but can contain active dependencies or build artifacts. Verify the owning project first."

    if parts & {".git", "src", "source", "documents", "desktop", "downloads"} or p.suffix.casefold() in SOURCE_EXTENSIONS:
        return "PROTECT - SOURCE / USER DATA", "Likely source code, project metadata, or user data; preserve unless you have verified another copy."

    if p.suffix.casefold() in ARCHIVE_EXTENSIONS:
        return "REVIEW - ARCHIVE / INSTALLER / BACKUP / LOG", "May be redundant or re-downloadable, but verify contents and backup value before any future cleanup."

    return "REVIEW - PURPOSE UNKNOWN", "DietDisk cannot safely infer whether this item is disposable from its path alone."
