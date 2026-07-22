# RMBG ONNX 本地抠图

这是一个在本机运行的抠图工具：Flask 提供仅绑定 `127.0.0.1` 的本地服务，浏览器负责交互，图片和结果无需上传到云端。项目以源码形式发布，不制作 EXE、DMG 或系统安装包，通过跨平台脚本创建隔离的 Python 环境并启动服务。

## 功能

- 智能抠图：使用兼容的 ONNX 背景移除模型生成透明 PNG。
- 线稿模式：无需模型推理，提取透明背景线稿。
- 批量处理、结果预览、任务恢复和本地结果目录打开。
- ONNX Runtime `CPU`、`CUDA` 和 macOS `CoreML` Provider 自动选择与手动切换。
- Windows、macOS、Linux 安装和启动脚本。

## 使用前准备

1. 安装 Python 3.11、3.12 或 3.13。
2. 下载你有权使用的兼容 ONNX 模型，并在项目根目录命名为 `model.onnx`。
3. 查看 [第三方与模型授权说明](THIRD_PARTY_NOTICES.md)。本仓库不包含模型权重。

## Windows

在 PowerShell 中执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start_windows.ps1
```

安装脚本检测到 NVIDIA 环境时默认安装 CUDA 运行时；也可明确选择：

```powershell
.\scripts\install_windows.ps1 -Runtime cpu
.\scripts\install_windows.ps1 -Runtime cuda
```

## macOS

```bash
./scripts/install_macos.sh
./scripts/start_macos.sh
```

Apple Silicon 或 Intel Mac 都使用 ONNX Runtime。自动模式会在可用时优先选择 CoreML，否则回退到 CPU。

## Linux

CPU 环境：

```bash
./scripts/install_linux.sh
./scripts/start_linux.sh
```

NVIDIA CUDA 环境：

```bash
./scripts/install_linux.sh --cuda
./scripts/start_linux.sh
```

安装完成后，启动脚本会自动打开带临时访问令牌的浏览器地址。服务默认使用动态可用端口；若指定端口，示例地址为 `http://127.0.0.1:8765/`。

## 启动参数

可以把服务参数附加到 macOS/Linux 启动脚本后：

```bash
./scripts/start_macos.sh --port 8765 --provider cpu
```

Windows 使用命名参数：

```powershell
.\scripts\start_windows.ps1 -Model .\model.onnx -OutputDir .\outputs -Provider cuda
```

可用 Provider 为 `auto`、`cpu`、`cuda`、`coreml`。启动前可检查环境：

```bash
.venv/bin/python rmbg_onnx_runner/check_env.py --model model.onnx --provider auto
```

## 输出与恢复

任务结果保存在：

```text
outputs/<任务ID>/
  manifest.json
  _uploads/
  results/
```

浏览器刷新后会从 `manifest.json` 恢复最近任务。`outputs/`、`.venv/` 和 `*.onnx` 均被 Git 忽略。

## 安全边界

服务仅为单用户本地工具设计，仅监听回环地址，不应暴露到局域网或互联网。浏览器会使用启动时生成的临时令牌访问 API，并校验来源和 Host。请不要关闭这些保护，也不要通过反向代理公开服务。漏洞报告方式见 [SECURITY.md](SECURITY.md)。

## 常见问题

- 找不到 `model.onnx`：确认模型位于项目根目录，或通过启动参数指定正确路径。
- CUDA 初始化失败：先用 `--provider cpu` 验证流程，再检查 NVIDIA 驱动和 CUDA 依赖。
- macOS 提示脚本不可执行：运行 `chmod +x scripts/*.sh` 后重试。
- PowerShell 阻止脚本：使用上面的 `-ExecutionPolicy Bypass` 单次启动方式，无需修改系统全局策略。
- 浏览器没有自动打开：复制终端显示的完整本地 URL，保留其中的访问令牌。

## 开发与测试

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements/dev.txt
.venv/bin/pytest
.venv/bin/ruff check .
```

命令行单图验证入口为 `rmbg_onnx_runner/run_rmbg_onnx.py`，服务入口为 `rmbg_onnx_runner/web_app.py`。

## 发布

代码采用 [MIT License](LICENSE)。GitHub Release 只发布通过测试的源码标签，不附带模型、运行环境或用户输出。

维护者先确认默认分支 CI 通过，再创建并推送语义化版本标签：

```bash
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
```

`v*` 标签会触发源码发布工作流；工作流再次运行测试和 Ruff，并在两项都通过后创建带自动发布说明的 GitHub Release。发布前请确认标签指向预期提交，且仓库中没有模型权重、输出图片或本地环境文件。
