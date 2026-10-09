"""Launch the DiskSense embedded web UI and local API on Windows."""
from __future__ import annotations
import socket
import threading
import time
import urllib.request

import uvicorn
import webview

from backend.api import app


def available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> None:
    port = available_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=0.3) as response:
                if response.status == 200:
                    break
        except Exception:
            time.sleep(0.1)
    else:
        raise RuntimeError("DiskSense local API did not start. Check your Python environment.")
    try:
        webview.create_window("DiskSense | Windows Storage Auditor", url, width=1360, height=900,
                              min_size=(980, 680), background_color="#f4f7f2")
        webview.start(debug=False)
    finally:
        server.should_exit = True
        thread.join(timeout=3)


if __name__ == "__main__":
    main()
