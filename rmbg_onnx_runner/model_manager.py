from __future__ import annotations

import multiprocessing
import platform
import threading
import uuid
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from model_worker import worker_main

RUNTIME_STATES = {"no_model", "loading", "ready", "processing", "switching", "error", "stopped"}


class RuntimeBusyError(RuntimeError):
    pass


class RuntimeLoadError(RuntimeError):
    def __init__(self, message: str, detail: dict[str, object] | None = None):
        super().__init__(message)
        self.detail = detail or {}
        self.restored_model: str | None = None


class RuntimeStopError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeSelection:
    model_id: str
    model_path: Path
    provider: str
    disable_fallback: bool = False
    disable_mem_pattern: bool = False


@dataclass(frozen=True)
class RuntimeMetadata:
    provider_requested: list[object]
    provider_active: list[str]
    load_seconds: float
    input_shape: list[object]
    input_type: str


def provider_catalog(available: Iterable[str], system_name: str | None = None) -> list[dict[str, str]]:
    values = set(available)
    choices = [{"id": "auto", "label": "自动检测"}]
    if (system_name or platform.system()) == "Darwin" and "CoreMLExecutionProvider" in values:
        choices.append({"id": "coreml", "label": "Apple CoreML"})
    if "CUDAExecutionProvider" in values:
        choices.append({"id": "cuda", "label": "NVIDIA CUDA"})
    if "CPUExecutionProvider" in values:
        choices.append({"id": "cpu", "label": "CPU"})
    return choices


class RuntimeSessionProxy:
    def __init__(self, manager: "ModelManager"):
        self._manager = manager

    def remove_background(self, **kwargs):
        return self._manager.call_remove_background(kwargs)


class RuntimeLease(AbstractContextManager):
    def __init__(self, manager: "ModelManager"):
        self._manager = manager
        self.session = RuntimeSessionProxy(manager)
        self._closed = False

    def close(self):
        if not self._closed:
            self._closed = True
            self._manager._release()

    def __exit__(self, *_):
        self.close()


class ModelManager:
    def __init__(self, load_timeout_seconds: float = 60, shutdown_timeout_seconds: float = 5):
        self._context = multiprocessing.get_context("spawn")
        self._load_timeout_seconds = load_timeout_seconds
        self._shutdown_timeout_seconds = shutdown_timeout_seconds
        self._process = None
        self._connection = None
        self._selection = None
        self._metadata = None
        self._state = "no_model"
        self._last_error = None
        self._leases = 0
        self._lock = threading.RLock()
        self._rpc_lock = threading.Lock()

    @property
    def state(self):
        return self._state

    @property
    def selection(self):
        return self._selection

    def status(self) -> dict[str, object]:
        metadata = self._metadata
        return {
            "ready": self._state == "ready",
            "runtimeState": self._state,
            "model": self._selection.model_id if self._selection else None,
            "provider": self._selection.provider if self._selection else "auto",
            "providerRequested": metadata.provider_requested if metadata else [],
            "providerActive": metadata.provider_active if metadata else [],
            "loadSeconds": metadata.load_seconds if metadata else None,
            "inputShape": metadata.input_shape if metadata else None,
            "inputType": metadata.input_type if metadata else None,
            "lastError": self._last_error,
        }

    def start(self, selection: RuntimeSelection):
        with self._lock:
            self._start_worker(selection)

    def switch(self, selection: RuntimeSelection):
        with self._lock:
            if self._leases:
                raise RuntimeBusyError("当前有任务正在处理，请完成后再切换模型或推理方式。")
            old_selection = self._selection
            self._state = "switching"
            self._stop_worker()
            try:
                self._start_worker(selection)
            except RuntimeLoadError as exc:
                if old_selection:
                    try:
                        self._start_worker(old_selection)
                        exc.restored_model = old_selection.model_id
                    except RuntimeLoadError:
                        pass
                raise

    def _start_worker(self, selection: RuntimeSelection):
        self._state = "loading"
        parent, child = self._context.Pipe()
        process = self._context.Process(
            target=worker_main,
            args=(child, str(selection.model_path), selection.provider, selection.disable_fallback, selection.disable_mem_pattern),
            daemon=True,
        )
        process.start()
        child.close()
        if not parent.poll(self._load_timeout_seconds):
            process.terminate()
            process.join(self._shutdown_timeout_seconds)
            self._state = "error"
            raise RuntimeLoadError("模型加载超时")
        try:
            message = parent.recv()
        except EOFError:
            message = None
        if not isinstance(message, dict) or message.get("type") != "ready":
            process.join(self._shutdown_timeout_seconds)
            self._state = "error"
            self._last_error = message.get("error") if isinstance(message, dict) else None
            raise RuntimeLoadError("模型加载失败", self._last_error)
        data = message["metadata"]
        self._process = process
        self._connection = parent
        self._selection = selection
        self._metadata = RuntimeMetadata(
            data["providerRequested"], data["providerActive"], data["loadSeconds"], data["inputShape"], data["inputType"]
        )
        self._state = "ready"
        self._last_error = None

    def _stop_worker(self):
        process = self._process
        if process is None:
            return
        try:
            self._connection.send({"type": "shutdown"})
        except (BrokenPipeError, EOFError, OSError):
            pass
        process.join(self._shutdown_timeout_seconds)
        if process.is_alive():
            process.terminate()
            process.join(self._shutdown_timeout_seconds)
        if process.is_alive() and hasattr(process, "kill"):
            process.kill()
            process.join(self._shutdown_timeout_seconds)
        if process.is_alive():
            raise RuntimeStopError("旧推理进程未能退出，已取消加载新模型。")
        self._connection.close()
        self._process = self._connection = self._selection = self._metadata = None

    def acquire(self) -> RuntimeLease:
        with self._lock:
            if self._state != "ready":
                raise RuntimeBusyError("模型尚未就绪")
            self._leases += 1
            self._state = "processing"
            return RuntimeLease(self)

    def _release(self):
        with self._lock:
            self._leases -= 1
            if not self._leases and self._process:
                self._state = "ready"

    def call_remove_background(self, kwargs):
        with self._rpc_lock:
            if not self._connection:
                raise RuntimeLoadError("推理进程不可用")
            request_id = uuid.uuid4().hex
            self._connection.send({"type": "remove_background", "requestId": request_id, "kwargs": kwargs})
            if not self._connection.poll(self._load_timeout_seconds):
                raise RuntimeLoadError("推理请求超时")
            response = self._connection.recv()
            if response.get("type") == "result" and response.get("requestId") == request_id:
                return response["result"]
            raise RuntimeLoadError("推理失败", response.get("error"))

    def close(self):
        with self._lock:
            self._stop_worker()
            self._state = "stopped"
