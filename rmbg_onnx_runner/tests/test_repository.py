from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_platform_scripts_exist_and_use_local_venv():
    expected = [
        "install_windows.ps1",
        "start_windows.ps1",
        "install_macos.sh",
        "start_macos.sh",
        "install_linux.sh",
        "start_linux.sh",
    ]
    for name in expected:
        path = ROOT / "scripts" / name
        assert path.is_file(), f"missing script: {name}"
        text = path.read_text(encoding="utf-8")
        assert ".venv" in text
        assert "web_app.py" in text or name.startswith("install_")


def test_platform_install_scripts_reference_matching_requirements():
    windows = (ROOT / "scripts" / "install_windows.ps1").read_text(encoding="utf-8")
    macos = (ROOT / "scripts" / "install_macos.sh").read_text(encoding="utf-8")
    linux = (ROOT / "scripts" / "install_linux.sh").read_text(encoding="utf-8")

    assert "requirements\\windows-cuda.txt" in windows
    assert "requirements\\cpu.txt" in windows
    assert "requirements/macos.txt" in macos
    assert "requirements/linux-cuda.txt" in linux
    assert "requirements/cpu.txt" in linux


def test_source_distribution_does_not_reference_legacy_cgi():
    for path in (ROOT / "rmbg_onnx_runner").glob("*.py"):
        assert "import cgi" not in path.read_text(encoding="utf-8")


def test_legacy_windows_bootstrap_files_are_removed():
    assert not (ROOT / "rmbg_onnx_runner" / "install_windows.ps1").exists()
    assert not (ROOT / "rmbg_onnx_runner" / "requirements-win-gpu.txt").exists()
