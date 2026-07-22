from __future__ import annotations

import socket
import subprocess
import sys
import webbrowser
from pathlib import Path

LOOPBACK_HOSTS = {"127.0.0.1", "localhost"}


def require_loopback(host: str) -> str:
    if host not in LOOPBACK_HOSTS:
        raise ValueError("host must be a loopback address: 127.0.0.1 or localhost")
    return host


def find_available_port(host: str, preferred: int, attempts: int = 20) -> int:
    require_loopback(host)
    for port in range(preferred, preferred + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    end = preferred + attempts - 1
    raise RuntimeError(f"no available local port in {preferred}-{end}")


def open_in_file_manager(path: Path) -> None:
    target = path.resolve()
    if sys.platform == "win32":
        args = (
            ["explorer", f"/select,{target}"]
            if target.is_file()
            else ["explorer", str(target)]
        )
    elif sys.platform == "darwin":
        args = ["open", "-R", str(target)] if target.is_file() else ["open", str(target)]
    else:
        folder = target.parent if target.is_file() else target
        args = ["xdg-open", str(folder)]
    subprocess.Popen(args)


def open_web_page(url: str) -> None:
    webbrowser.open(url)
