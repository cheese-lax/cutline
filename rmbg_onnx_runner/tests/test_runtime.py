from pathlib import Path
from unittest import mock

import pytest
import runtime


def test_require_loopback_accepts_supported_hosts():
    assert runtime.require_loopback("127.0.0.1") == "127.0.0.1"
    assert runtime.require_loopback("localhost") == "localhost"


def test_require_loopback_rejects_remote_bind():
    with pytest.raises(ValueError, match="loopback"):
        runtime.require_loopback("0.0.0.0")


def test_find_available_port_skips_bound_port(monkeypatch):
    attempts = []

    class FakeSocket:
        def __init__(self, *_args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def bind(self, address):
            attempts.append(address)
            if address[1] == 8765:
                raise OSError("occupied")

    monkeypatch.setattr(runtime.socket, "socket", FakeSocket)

    selected = runtime.find_available_port("127.0.0.1", 8765, attempts=2)

    assert selected == 8766
    assert attempts == [("127.0.0.1", 8765), ("127.0.0.1", 8766)]


def test_find_available_port_rejects_exhausted_range(monkeypatch):
    class OccupiedSocket:
        def __init__(self, *_args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def bind(self, _address):
            raise OSError("occupied")

    monkeypatch.setattr(runtime.socket, "socket", OccupiedSocket)

    with pytest.raises(RuntimeError, match="no available local port"):
        runtime.find_available_port("127.0.0.1", 8765, attempts=1)


def test_open_in_file_manager_uses_macos_reveal_for_file(monkeypatch, tmp_path):
    file_path = tmp_path / "result.png"
    file_path.write_bytes(b"image")
    popen = mock.Mock()
    monkeypatch.setattr(runtime.sys, "platform", "darwin")
    monkeypatch.setattr(runtime.subprocess, "Popen", popen)

    runtime.open_in_file_manager(file_path)

    popen.assert_called_once_with(["open", "-R", str(file_path.resolve())])


def test_open_in_file_manager_uses_xdg_open_for_linux_folder(monkeypatch, tmp_path):
    folder = Path(tmp_path)
    popen = mock.Mock()
    monkeypatch.setattr(runtime.sys, "platform", "linux")
    monkeypatch.setattr(runtime.subprocess, "Popen", popen)

    runtime.open_in_file_manager(folder)

    popen.assert_called_once_with(["xdg-open", str(folder.resolve())])
