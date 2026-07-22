import resource_diagnostics


def test_memory_error_is_confirmed_oom(monkeypatch):
    snapshot = resource_diagnostics.ResourceSnapshot(8 * 1024**3, 768 * 1024**2, 1024**3)
    monkeypatch.setattr(resource_diagnostics, "capture_resource_snapshot", lambda **_: snapshot)
    failure = resource_diagnostics.diagnose_runtime_error(MemoryError("allocation failed"), "inference", [])
    assert failure.code == "SYSTEM_OUT_OF_MEMORY"
    assert failure.confidence == "confirmed"
    assert failure.resources.available_system_memory_bytes == 768 * 1024**2


def test_cuda_oom_text_is_likely_gpu_oom(monkeypatch):
    snapshot = resource_diagnostics.ResourceSnapshot(8 * 1024**3, 2 * 1024**3, 1024**3, 512 * 1024**2, 8 * 1024**3)
    monkeypatch.setattr(resource_diagnostics, "capture_resource_snapshot", lambda **_: snapshot)
    failure = resource_diagnostics.diagnose_runtime_error(RuntimeError("CUDA_ERROR_OUT_OF_MEMORY"), "inference", ["CUDAExecutionProvider"])
    assert (failure.code, failure.confidence) == ("GPU_OUT_OF_MEMORY", "likely")
    assert failure.resources.cuda_free_memory_bytes == 512 * 1024**2
