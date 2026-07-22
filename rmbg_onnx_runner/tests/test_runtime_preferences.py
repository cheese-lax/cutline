
from runtime_preferences import load_last_model, save_last_model
from web_app import choose_startup_model


def test_preferences_round_trip_atomically(tmp_path):
    path = tmp_path / ".runtime-state.json"
    save_last_model(path, "portraits/model_fp16.onnx")
    assert load_last_model(path) == "portraits/model_fp16.onnx"
    assert not path.with_name(f"{path.name}.tmp").exists()


def test_corrupt_preferences_are_ignored(tmp_path):
    path = tmp_path / ".runtime-state.json"
    path.write_text("not json", encoding="utf-8")
    assert load_last_model(path) == ""


def test_explicit_model_wins_over_saved_model(tmp_path):
    models = tmp_path / "models"
    models.mkdir()
    (models / "explicit.onnx").write_bytes(b"x")
    assert choose_startup_model(models, "explicit.onnx", "missing.onnx").name == "explicit.onnx"
