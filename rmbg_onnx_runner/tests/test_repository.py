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


def test_start_scripts_use_models_directory_without_fixed_model_name():
    for name in ["start_windows.ps1", "start_macos.sh", "start_linux.sh"]:
        text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "models" in text
        assert "model.onnx" not in text


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


def test_public_docs_cover_install_security_and_model_license():
    readme = (ROOT / "README_ZH.md").read_text(encoding="utf-8")
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")

    for required_text in ["Windows", "macOS", "Linux", "127.0.0.1", "models/"]:
        assert required_text in readme
    assert "浏览器" in readme and "模型" in readme and "自动恢复" in readme
    assert "输入支持 JPG、PNG、WebP、静态 AVIF、BMP、单页 TIFF、ICO 和 TGA" in readme
    assert "https://huggingface.co/briaai/RMBG-2.0" in readme
    assert "https://huggingface.co/briaai/RMBG-2.0/tree/main/onnx" in readme
    assert "独立推理进程" in readme
    assert "Apple CoreML" in readme
    assert "--disable-mem-pattern" in readme
    assert "故障时可用内存" in readme
    assert "https://www.modelscope.cn/models/AI-ModelScope/RMBG-2.0" in readme
    assert "CC BY-NC 4.0" in notices
    assert "commercial" in notices.lower()
    assert "localhost" in security.lower()
    assert "MIT License" in license_text


def test_root_readme_is_english_and_covers_the_same_public_setup_and_security_basics():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for required_text in ["Windows", "macOS", "Linux", "127.0.0.1", "models/"]:
        assert required_text in readme
    assert "English" in readme
    assert "Chinese" in readme
    assert "README_ZH.md" in readme
    assert "https://huggingface.co/briaai/RMBG-2.0" in readme
    assert "THIRD_PARTY_NOTICES.md" in readme


def test_ci_covers_supported_platforms_and_python_versions():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    for runner in ["ubuntu-latest", "windows-latest", "macos-latest"]:
        assert runner in workflow
    for version in ["3.11", "3.12", "3.13"]:
        assert version in workflow
    assert "pytest" in workflow
    assert "ruff check" in workflow
    assert "web_app.py --help" in workflow
    assert "Parser]::ParseFile" in workflow


def test_release_workflow_verifies_source_before_publishing():
    workflow = (ROOT / ".github" / "workflows" / "release-source.yml").read_text(encoding="utf-8")

    assert '"v*"' in workflow
    assert "contents: write" in workflow
    assert "pytest" in workflow
    assert "ruff check" in workflow
    assert "gh release create" in workflow
    assert "--verify-tag" in workflow
