from __future__ import annotations

import gc

import rmbg_onnx
from resource_diagnostics import diagnose_runtime_error


def ready_payload(session: rmbg_onnx.RmbgSession) -> dict[str, object]:
    return {"type": "ready", "metadata": {"providerRequested": list(session.provider_requested), "providerActive": session.provider_active, "loadSeconds": session.load_seconds, "inputShape": list(session.model_input.shape), "inputType": session.model_input.type}}


def serve_requests(connection, session: rmbg_onnx.RmbgSession) -> None:
    while True:
        request = connection.recv()
        kind = request.get("type") if isinstance(request, dict) else None
        if kind == "shutdown":
            connection.send({"type": "stopped"})
            return
        request_id = request.get("requestId") if isinstance(request, dict) else None
        if kind != "remove_background" or not isinstance(request.get("kwargs"), dict):
            connection.send({"type": "protocol_error", "requestId": request_id, "error": "PROTOCOL_ERROR"})
            continue
        try:
            result = session.remove_background(**request["kwargs"])
            connection.send({"type": "result", "requestId": request_id, "result": result})
        except BaseException as exc:
            failure = diagnose_runtime_error(exc, "inference", session.provider_active)
            connection.send({"type": "inference_error", "requestId": request_id, "error": failure.to_payload()})


def worker_main(connection, model_path: str, provider: str, disable_fallback: bool, disable_mem_pattern: bool) -> None:
    session = None
    try:
        session = rmbg_onnx.RmbgSession(model_path=model_path, provider=provider, disable_fallback=disable_fallback, disable_mem_pattern=disable_mem_pattern)
        connection.send(ready_payload(session))
        serve_requests(connection, session)
    except BaseException as exc:
        active = session.provider_active if session is not None else []
        connection.send({"type": "load_error", "error": diagnose_runtime_error(exc, "model_load", active).to_payload()})
    finally:
        session = None
        gc.collect()
        connection.close()
