# RMBG-2.0 ONNX local web runner

这个目录是可复制到 Windows 机器运行的 RMBG-2.0 ONNX 本地抠图服务代码。

界面提供两种处理模式：

- `智能抠图`：使用 RMBG-2.0 模型识别主体并移除背景。
- `线稿模式`：跳过 ONNX 推理，从图片四边自动估算背景色，按像素与背景的灰度差生成透明度，并输出透明底线稿。

## 文件

- `rmbg_onnx.py`: 核心预处理、推理、mask 后处理逻辑。
- `web_app.py`: 本地 HTTP 服务入口，加载模型并提供 Web UI/API。
- `web/`: 浏览器端页面、样式和交互代码。
- `run_rmbg_onnx.py`: 命令行抠图入口，用于单图验证或排障。
- `check_env.py`: 检查 Python、ONNX Runtime、CUDA Provider、NVIDIA 显卡和模型输入输出。
- `install_windows.ps1`: Windows 一键建虚拟环境并使用清华 PyPI 镜像安装依赖。
- `requirements-win-gpu.txt`: GPU 推理依赖。
- `tests/`: 核心预处理、后处理和 provider 选择的轻量单测。

## 远程 Windows 运行

把这个目录复制到 Windows 机器，例如：

```text
E:\koutu\rmbg_onnx_runner
```

确保模型文件在你启动命令指定的位置。下面示例使用：

```powershell
E:\koutu\rmbg_onnx_runner\model.onnx
```

然后在那个终端里执行：

```powershell
Set-Location -Path E:\koutu\rmbg_onnx_runner
powershell -ExecutionPolicy Bypass -File .\install_windows.ps1
.\.venv\Scripts\python.exe .\check_env.py --model .\model.onnx --provider cuda
.\.venv\Scripts\python.exe .\web_app.py --model .\model.onnx --output-dir .\outputs --provider cuda --open
```

启动成功后浏览器访问：

```text
http://127.0.0.1:8765/
```

如果你的目录结构是模型放在 runner 父目录，例如 `E:\koutu\model.onnx`，把命令里的模型参数换成：

```powershell
--model ..\model.onnx
```

## 命令行验证

如果需要不启动 Web 服务，只验证单张图片：

```powershell
.\.venv\Scripts\python.exe .\run_rmbg_onnx.py --model .\model.onnx --input .\sample_input.png --provider cuda
```

如果 `sample_input.png` 不存在，脚本会自动生成一张测试图，并输出 `sample_output_rgba.png` 和 `sample_mask.png`。

如果 CUDA Provider 有问题，可以先用 CPU 验证推理链路：

```powershell
.\.venv\Scripts\python.exe .\run_rmbg_onnx.py --model .\model.onnx --input .\input.jpg --output .\output_cpu.png --provider cpu
```

## 清理策略

仓库只保留服务运行和验证需要的文件。历史诊断脚本、一次性补丁脚本、调试输出图片、测试输入图片和本地抠图结果不纳入代码目录；这些文件需要时可由命令重新生成。

## 结果目录

Web 批量任务会写入独立目录：

```text
outputs/<任务ID>/
  manifest.json
  _uploads/
  results/
```

界面里的“打开本次结果文件夹”会打开当前任务的 `results` 目录。`manifest.json` 用于刷新页面后恢复最近一次任务列表和预览，不需要额外数据库。

## 实现依据

RMBG-2.0 官方模型卡的参考用法使用 `1024x1024` 输入、ImageNet mean/std 归一化，并将模型输出转换为单通道 alpha matte 后作为透明度通道。ONNX 目录中的 `model.onnx` 是 FP32 模型。

线稿模式只使用现有的 Pillow 和 NumPy 依赖。它会保留原始线条颜色，对抗锯齿像素做背景色反混合，并根据图片边缘的灰度波动自动过滤接近背景色的噪点；该模式始终输出透明背景，结果文件名使用 `_lineart` 后缀。
