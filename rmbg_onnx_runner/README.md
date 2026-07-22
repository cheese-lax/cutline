# RMBG ONNX Runner 模块

这里包含本地抠图服务的 Python 实现。完整安装、启动、安全边界和模型授权说明请从[项目根目录 README](../README.md)开始阅读。

主要模块：

- `web_app.py`：Flask 本地服务入口与命令行参数。
- `task_service.py`：上传、任务处理、清单、结果恢复和安全的历史清理。
- `runtime.py`：回环地址、动态端口、浏览器及文件管理器适配。
- `rmbg_onnx.py`：ONNX 预处理、推理和 mask 后处理。
- `run_rmbg_onnx.py`：命令行单图验证。
- `check_env.py`：Python、ONNX Runtime、Provider 和模型检查。
- `model_manager.py`：独立推理进程的生命周期、租约与无重叠切换。
- `model_worker.py`：spawn 安全的 ONNX 推理子进程协议。
- `resource_diagnostics.py`：故障时的系统/CUDA 内存快照与证据置信度。
- `web/`：浏览器 UI。
- `tests/`：单元和仓库契约测试。

请在项目根目录运行跨平台脚本：

- Windows：`scripts/install_windows.ps1`、`scripts/start_windows.ps1`
- macOS：`scripts/install_macos.sh`、`scripts/start_macos.sh`
- Linux：`scripts/install_linux.sh`、`scripts/start_linux.sh`

Web 批量任务写入 `outputs/<任务ID>/`，其中包含 `manifest.json`、上传副本和处理结果。任务 ID 带毫秒和随机短码以避免目录冲突；历史清理只处理具有合法清单的直属任务目录。本源码目录不应存放模型权重、虚拟环境或用户输出。
