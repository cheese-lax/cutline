import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pytest
import rmbg_onnx
from PIL import Image


class FakeModelInput:
    def __init__(self, shape):
        self.shape = shape


class RmbgOnnxTests(unittest.TestCase):
    def test_estimate_background_color_uses_border_median(self):
        pixels = np.full((5, 5, 3), (240, 230, 220), dtype=np.uint8)
        pixels[0, 0] = (10, 20, 30)
        pixels[2, 2] = (255, 0, 0)

        background = rmbg_onnx.estimate_background_color(Image.fromarray(pixels, mode="RGB"))

        self.assertEqual(background, (240, 230, 220))

    def test_build_line_art_image_turns_background_transparent_from_grayscale_difference(self):
        pixels = np.full((3, 3, 3), 255, dtype=np.uint8)
        pixels[1, 1] = (255, 0, 0)

        output, mask, background = rmbg_onnx.build_line_art_image(Image.fromarray(pixels, mode="RGB"))

        self.assertEqual(background, (255, 255, 255))
        self.assertEqual(output.mode, "RGBA")
        self.assertEqual(mask.getpixel((0, 0)), 0)
        self.assertEqual(output.getpixel((0, 0)), (255, 255, 255, 0))
        self.assertEqual(mask.getpixel((1, 1)), 179)
        self.assertEqual(output.getpixel((1, 1)), (255, 0, 0, 179))

    def test_build_line_art_image_removes_near_background_noise(self):
        pixels = np.full((5, 5, 3), 255, dtype=np.uint8)
        pixels[2, 2] = (254, 254, 254)

        output, mask, _ = rmbg_onnx.build_line_art_image(Image.fromarray(pixels, mode="RGB"))

        self.assertEqual(mask.getpixel((2, 2)), 0)
        self.assertEqual(output.getpixel((2, 2))[3], 0)

    def test_line_art_mode_skips_model_inference_and_saves_transparent_result(self):
        class FailingInferenceSession:
            def run(self, *_args, **_kwargs):
                raise AssertionError("line art mode must not run ONNX inference")

            def get_providers(self):
                return ["CPUExecutionProvider"]

        runner = rmbg_onnx.RmbgSession.__new__(rmbg_onnx.RmbgSession)
        runner.session = FailingInferenceSession()
        runner.model_input = type("ModelInput", (), {"name": "input", "type": "tensor(float)", "shape": [1, 3, 2, 2]})()
        runner.output_names = ["output"]
        runner.provider_requested = ["CPUExecutionProvider"]
        runner.load_seconds = 0.0
        runner.activation = "auto"
        runner.output_index = -1
        runner.input_size = (2, 2)

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input.png"
            output_path = Path(tmpdir) / "output.png"
            Image.new("RGB", (3, 3), "white").save(input_path)

            result = runner.remove_background(
                input_path=input_path,
                output_path=output_path,
                processing_mode="line_art",
                transparent_background=False,
            )

            with Image.open(output_path) as output:
                self.assertEqual(output.mode, "RGBA")
                self.assertEqual(output.getpixel((0, 0))[3], 0)
        self.assertEqual(result.inference_seconds, 0.0)

    def test_preprocess_matches_rmbg_reference_normalization(self):
        image = Image.new("RGB", (1, 1), (255, 0, 0))

        tensor = rmbg_onnx.preprocess_image(
            image,
            size=(1, 1),
            input_type="tensor(float16)",
        )

        self.assertEqual(tensor.shape, (1, 3, 1, 1))
        self.assertEqual(tensor.dtype, np.float16)
        expected = np.array(
            [
                (1.0 - 0.485) / 0.229,
                (0.0 - 0.456) / 0.224,
                (0.0 - 0.406) / 0.225,
            ],
            dtype=np.float16,
        )
        np.testing.assert_allclose(tensor[0, :, 0, 0], expected, rtol=1e-3)

    def test_postprocess_applies_sigmoid_for_logits_and_resizes(self):
        logits = np.array([[[[-100.0, 0.0, 100.0]]]], dtype=np.float32)

        mask = rmbg_onnx.postprocess_mask(
            logits,
            original_size=(3, 1),
            activation="sigmoid",
        )

        self.assertEqual(mask.mode, "L")
        self.assertEqual(mask.size, (3, 1))
        values = np.asarray(mask, dtype=np.float32) / 255.0
        self.assertLess(values[0, 0], 0.01)
        self.assertTrue(math.isclose(float(values[0, 1]), 0.5, abs_tol=0.02))
        self.assertGreater(values[0, 2], 0.99)

    def test_postprocess_keeps_alpha_probabilities_when_activation_none(self):
        probs = np.array([[[[0.25, 0.75]]]], dtype=np.float32)

        mask = rmbg_onnx.postprocess_mask(probs, original_size=(2, 1), activation="none")

        np.testing.assert_allclose(np.asarray(mask), np.array([[64, 191]], dtype=np.uint8), atol=1)

    def test_input_size_from_static_model_shape(self):
        model_input = FakeModelInput([1, 3, 768, 1024])

        self.assertEqual(rmbg_onnx.input_size_from_model(model_input), (1024, 768))

    def test_input_size_defaults_for_dynamic_model_shape(self):
        model_input = FakeModelInput(["batch", 3, "height", "width"])

        self.assertEqual(rmbg_onnx.input_size_from_model(model_input), (1024, 1024))

    def test_choose_cuda_provider_requires_cuda_availability(self):
        providers = rmbg_onnx.choose_providers(
            "cuda",
            available=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )

        self.assertEqual(providers, ["CUDAExecutionProvider", "CPUExecutionProvider"])

        with self.assertRaisesRegex(RuntimeError, "CUDAExecutionProvider"):
            rmbg_onnx.choose_providers("cuda", available=["CPUExecutionProvider"])

    def test_auto_prefers_coreml_on_macos(self):
        providers = rmbg_onnx.choose_providers(
            "auto",
            available=["CoreMLExecutionProvider", "CPUExecutionProvider"],
            system="Darwin",
        )

        self.assertEqual(providers, ["CoreMLExecutionProvider", "CPUExecutionProvider"])

    def test_auto_prefers_cuda_outside_macos(self):
        providers = rmbg_onnx.choose_providers(
            "auto",
            available=["CUDAExecutionProvider", "CPUExecutionProvider"],
            system="Windows",
        )

        self.assertEqual(providers, ["CUDAExecutionProvider", "CPUExecutionProvider"])

    def test_auto_falls_back_to_cpu(self):
        providers = rmbg_onnx.choose_providers(
            "auto",
            available=["CPUExecutionProvider"],
            system="Linux",
        )

        self.assertEqual(providers, ["CPUExecutionProvider"])

    def test_explicit_coreml_requires_provider(self):
        with pytest.raises(RuntimeError, match="CoreMLExecutionProvider"):
            rmbg_onnx.choose_providers(
                "coreml",
                available=["CPUExecutionProvider"],
                system="Darwin",
            )

    def test_with_cuda_provider_options_preserves_provider_order(self):
        providers = rmbg_onnx.with_cuda_provider_options(
            ["CUDAExecutionProvider", "CPUExecutionProvider"],
            {"use_tf32": "0"},
        )

        self.assertEqual(
            providers,
            [("CUDAExecutionProvider", {"use_tf32": "0"}), "CPUExecutionProvider"],
        )

    def test_add_nvidia_dll_directories_adds_existing_package_bins(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            site_packages = Path(tmpdir)
            cudnn_bin = site_packages / "nvidia" / "cudnn" / "bin"
            cublas_bin = site_packages / "nvidia" / "cublas" / "bin"
            cudnn_bin.mkdir(parents=True)
            cublas_bin.mkdir(parents=True)
            added: list[str] = []

            def fake_add_dll_directory(path):
                added.append(path)
                return object()

            with mock.patch.object(os, "add_dll_directory", fake_add_dll_directory, create=True):
                handles = rmbg_onnx.add_nvidia_dll_directories(site_packages)

        self.assertEqual(added, [str(cudnn_bin), str(cublas_bin)])
        self.assertEqual(len(handles), 2)

    def test_make_sample_image_creates_rgb_png(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = rmbg_onnx.make_sample_image(f"{tmpdir}/sample.png")

            with Image.open(path) as image:
                mode = image.mode
                size = image.size

        self.assertEqual(mode, "RGB")
        self.assertEqual(size, (900, 650))

    def test_build_output_image_keeps_transparent_background_by_default(self):
        image = Image.new("RGB", (2, 1), (10, 20, 30))
        mask = Image.fromarray(np.array([[255, 0]], dtype=np.uint8), mode="L")

        output = rmbg_onnx.build_output_image(image, mask)

        self.assertEqual(output.mode, "RGBA")
        self.assertEqual(output.getpixel((0, 0)), (10, 20, 30, 255))
        self.assertEqual(output.getpixel((1, 0)), (10, 20, 30, 0))

    def test_build_output_image_can_flatten_to_custom_background(self):
        image = Image.new("RGB", (2, 1), (10, 20, 30))
        mask = Image.fromarray(np.array([[255, 0]], dtype=np.uint8), mode="L")

        output = rmbg_onnx.build_output_image(
            image,
            mask,
            transparent_background=False,
            background_color="#112233",
        )

        self.assertEqual(output.mode, "RGB")
        self.assertEqual(output.getpixel((0, 0)), (10, 20, 30))
        self.assertEqual(output.getpixel((1, 0)), (17, 34, 51))

    def test_normalize_output_format_rejects_unknown_values(self):
        self.assertEqual(rmbg_onnx.normalize_output_format("WEBP"), "webp")

        with self.assertRaisesRegex(ValueError, "output format"):
            rmbg_onnx.normalize_output_format("jpg")


if __name__ == "__main__":
    unittest.main()
