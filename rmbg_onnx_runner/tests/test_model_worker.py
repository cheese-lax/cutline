from types import SimpleNamespace

import model_worker


class Connection:
    def __init__(self, incoming): self.incoming, self.sent = list(incoming), []
    def recv(self): return self.incoming.pop(0)
    def send(self, value): self.sent.append(value)
    def close(self): pass


def test_worker_reports_ready_result_and_stopped(monkeypatch, tmp_path):
    class Session:
        provider_requested = ["CPUExecutionProvider"]
        provider_active = ["CPUExecutionProvider"]
        load_seconds = 0.01
        model_input = SimpleNamespace(shape=[1, 3, 4, 4], type="tensor(float)")
        def remove_background(self, **kwargs): return {"output": kwargs["output_path"]}
    monkeypatch.setattr(model_worker.rmbg_onnx, "RmbgSession", lambda **_: Session())
    conn = Connection([{"type": "remove_background", "requestId": "one", "kwargs": {"output_path": str(tmp_path / "a.png")}}, {"type": "shutdown"}])
    model_worker.worker_main(conn, "model.onnx", "cpu", False, False)
    assert conn.sent[0]["type"] == "ready"
    assert conn.sent[1] == {"type": "result", "requestId": "one", "result": {"output": str(tmp_path / "a.png")}}
    assert conn.sent[2] == {"type": "stopped"}
