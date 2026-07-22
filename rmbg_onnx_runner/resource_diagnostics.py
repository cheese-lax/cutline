from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

import psutil

CUDA_OOM_TOKENS = ("cuda_error_out_of_memory", "cuda out of memory", "cuda oom")
SYSTEM_OOM_TOKENS = ("out of memory", "cannot allocate memory", "bad_alloc")


@dataclass(frozen=True)
class ResourceSnapshot:
    total_system_memory_bytes: int | None
    available_system_memory_bytes: int | None
    process_rss_bytes: int | None
    cuda_free_memory_bytes: int | None = None
    cuda_total_memory_bytes: int | None = None

    def to_payload(self) -> dict[str, int | None]:
        return {
            "totalSystemMemoryBytes": self.total_system_memory_bytes,
            "availableSystemMemoryBytes": self.available_system_memory_bytes,
            "processRssBytes": self.process_rss_bytes,
            "cudaFreeMemoryBytes": self.cuda_free_memory_bytes,
            "cudaTotalMemoryBytes": self.cuda_total_memory_bytes,
        }


@dataclass(frozen=True)
class RuntimeFailure:
    code: str
    stage: str
    reason: str
    detail: str
    suggestion: str
    confidence: str
    resources: ResourceSnapshot

    def to_payload(self) -> dict[str, object]:
        return {
            "code": self.code,
            "stage": self.stage,
            "reason": self.reason,
            "detail": self.detail,
            "suggestion": self.suggestion,
            "confidence": self.confidence,
            "resources": self.resources.to_payload(),
        }


def capture_resource_snapshot(cuda_active: bool = False) -> ResourceSnapshot:
    memory = psutil.virtual_memory()
    cuda_free, cuda_total = _cuda_memory() if cuda_active else (None, None)
    return ResourceSnapshot(memory.total, memory.available, psutil.Process().memory_info().rss, cuda_free, cuda_total)


def _cuda_memory() -> tuple[int | None, int | None]:
    if shutil.which("nvidia-smi") is None:
        return None, None
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free,memory.total", "--format=csv,noheader,nounits"],
            check=True, capture_output=True, text=True, timeout=2,
        )
        first = result.stdout.splitlines()[0].split(",")
        return int(first[0].strip()) * 1024**2, int(first[1].strip()) * 1024**2
    except (IndexError, OSError, subprocess.SubprocessError, ValueError):
        return None, None


def diagnose_runtime_error(exc: BaseException, stage: str, provider_active: list[str]) -> RuntimeFailure:
    message = " ".join(str(exc).split())
    detail = f"{type(exc).__name__}: {message[:500]}"
    lower = message.casefold()
    cuda_active = "CUDAExecutionProvider" in provider_active
    resources = capture_resource_snapshot(cuda_active=cuda_active)
    if isinstance(exc, MemoryError):
        code, confidence, reason = "SYSTEM_OUT_OF_MEMORY", "confirmed", "系统内存不足"
    elif cuda_active and any(token in lower for token in CUDA_OOM_TOKENS):
        code, confidence, reason = "GPU_OUT_OF_MEMORY", "likely", "GPU 显存不足"
    elif any(token in lower for token in SYSTEM_OOM_TOKENS):
        code, confidence, reason = "SYSTEM_OUT_OF_MEMORY", "likely", "系统内存不足"
    elif stage == "model_load":
        code, confidence, reason = "MODEL_LOAD_FAILED", "unknown", "模型加载失败"
    else:
        code, confidence, reason = "INFERENCE_FAILED", "unknown", "推理失败"
    available = resources.available_system_memory_bytes
    memory_hint = f"当前可用内存约 {available / 1024**2:.0f} MiB。" if available is not None else ""
    suggestion = "关闭其他应用，或改用体积更小的量化模型。" if code == "SYSTEM_OUT_OF_MEMORY" else ""
    if code == "GPU_OUT_OF_MEMORY":
        suggestion = "切换到 CPU，或关闭占用 GPU 的应用后重试。"
    if code == "MODEL_LOAD_FAILED":
        suggestion = "确认模型文件完整，并选择当前运行时支持的推理方式。"
    return RuntimeFailure(code, stage, reason, detail, f"{suggestion}{memory_hint}", confidence, resources)
