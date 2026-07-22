from __future__ import annotations

import os
import platform
import site
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
from PIL import Image, ImageColor, ImageFilter

RMBG_IMAGE_SIZE = (1024, 1024)
RMBG_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
RMBG_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
NVIDIA_DLL_PACKAGES = (
    "cudnn",
    "cublas",
    "cuda_runtime",
    "cuda_nvrtc",
    "cufft",
    "curand",
    "nvjitlink",
)
SUPPORTED_OUTPUT_FORMATS = {"png", "webp"}
SUPPORTED_PROCESSING_MODES = {"rmbg", "line_art"}


@dataclass(frozen=True)
class RmbgRunResult:
    output_path: Path
    mask_path: Path | None
    provider_requested: list[object]
    provider_active: list[str]
    input_name: str
    input_type: str
    input_shape: Sequence[object]
    output_names: list[str]
    load_seconds: float
    inference_seconds: float
    mask_min: float
    mask_max: float
    mask_mean: float


class RmbgSession:
    """Reusable RMBG ONNX Runtime session for processing many images."""

    def __init__(
        self,
        model_path: str | Path,
        provider: str = "cuda",
        activation: str = "auto",
        output_index: int = -1,
        disable_mem_pattern: bool = False,
        disable_mem_reuse: bool = False,
        cuda_provider_options: Mapping[str, object] | None = None,
        disable_fallback: bool = False,
    ) -> None:
        import onnxruntime as ort

        available_providers = ort.get_available_providers()
        self.dll_directory_handles = []
        if "CUDAExecutionProvider" in available_providers:
            self.dll_directory_handles = add_nvidia_dll_directories()
            if hasattr(ort, "preload_dlls"):
                ort.preload_dlls(directory="")

        self.model_path = Path(model_path)
        self.activation = activation
        self.output_index = output_index

        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")

        self.provider_requested = with_cuda_provider_options(
            choose_providers(provider),
            cuda_provider_options,
        )
        session_options = ort.SessionOptions()
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        if disable_mem_pattern:
            session_options.enable_mem_pattern = False
        if disable_mem_reuse:
            session_options.enable_mem_reuse = False

        load_started = time.perf_counter()
        self.session = ort.InferenceSession(
            str(self.model_path),
            sess_options=session_options,
            providers=self.provider_requested,
        )
        if disable_fallback:
            self.session.disable_fallback()
        self.load_seconds = time.perf_counter() - load_started

        self.model_input = self.session.get_inputs()[0]
        self.output_names = [output.name for output in self.session.get_outputs()]
        self.input_size = input_size_from_model(self.model_input)

    @property
    def provider_active(self) -> list[str]:
        return self.session.get_providers()

    def remove_background(
        self,
        input_path: str | Path,
        output_path: str | Path,
        mask_path: str | Path | None = None,
        output_format: str = "png",
        edge_optimize: bool = False,
        transparent_background: bool = True,
        background_color: str = "#FFFFFF",
        processing_mode: str = "rmbg",
    ) -> RmbgRunResult:
        input_path = Path(input_path)
        output_path = Path(output_path)
        mask_output_path = Path(mask_path) if mask_path else None
        normalized_output_format = normalize_output_format(output_format)
        normalized_processing_mode = normalize_processing_mode(processing_mode)

        if not input_path.exists():
            raise FileNotFoundError(f"Input image not found: {input_path}")

        with Image.open(input_path) as image:
            if normalized_processing_mode == "line_art":
                output_image, mask, _ = build_line_art_image(image)
                inference_seconds = 0.0
            else:
                input_tensor = preprocess_image(
                    image,
                    size=self.input_size,
                    input_type=self.model_input.type,
                )

                infer_started = time.perf_counter()
                predictions = self.session.run(None, {self.model_input.name: input_tensor})
                inference_seconds = time.perf_counter() - infer_started

                prediction = predictions[self.output_index]
                mask = postprocess_mask(
                    prediction,
                    original_size=image.size,
                    activation=self.activation,
                )
                output_image = build_output_image(
                    image=image,
                    mask=mask,
                    transparent_background=transparent_background,
                    background_color=background_color,
                    edge_optimize=edge_optimize,
                )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        save_output_image(output_image, output_path, normalized_output_format)
        if mask_output_path:
            mask_output_path.parent.mkdir(parents=True, exist_ok=True)
            mask.save(mask_output_path)

        mask_array = np.asarray(mask, dtype=np.float32) / 255.0
        return RmbgRunResult(
            output_path=output_path,
            mask_path=mask_output_path,
            provider_requested=list(self.provider_requested),
            provider_active=self.provider_active,
            input_name=self.model_input.name,
            input_type=self.model_input.type,
            input_shape=self.model_input.shape,
            output_names=list(self.output_names),
            load_seconds=self.load_seconds,
            inference_seconds=inference_seconds,
            mask_min=float(mask_array.min()),
            mask_max=float(mask_array.max()),
            mask_mean=float(mask_array.mean()),
        )


def add_nvidia_dll_directories(site_packages: str | Path | None = None) -> list[object]:
    """Add NVIDIA wheel DLL directories on Windows and keep handles alive."""
    add_dll_directory = getattr(os, "add_dll_directory", None)
    if add_dll_directory is None:
        return []

    if site_packages is None:
        candidates = [Path(path) for path in site.getsitepackages()]
        try:
            candidates.append(Path(site.getusersitepackages()))
        except Exception:
            pass
    else:
        candidates = [Path(site_packages)]

    handles = []
    seen: set[Path] = set()
    for candidate in candidates:
        nvidia_root = candidate / "nvidia"
        for package in NVIDIA_DLL_PACKAGES:
            dll_dir = nvidia_root / package / "bin"
            if dll_dir in seen or not dll_dir.is_dir():
                continue
            seen.add(dll_dir)
            handles.append(add_dll_directory(str(dll_dir)))
    return handles


def input_size_from_model(model_input, default: tuple[int, int] = RMBG_IMAGE_SIZE) -> tuple[int, int]:
    """Return PIL-style (width, height) input size from an ONNX input object."""
    shape = list(getattr(model_input, "shape", []) or [])
    if len(shape) == 4 and isinstance(shape[2], int) and isinstance(shape[3], int):
        height = int(shape[2])
        width = int(shape[3])
        if height > 0 and width > 0:
            return (width, height)
    return default


def preprocess_image(
    image: Image.Image,
    size: tuple[int, int] = RMBG_IMAGE_SIZE,
    input_type: str = "tensor(float)",
) -> np.ndarray:
    """Resize and normalize an image using RMBG-2.0's reference preprocessing."""
    resized = image.convert("RGB").resize(size, Image.Resampling.BILINEAR)
    array = np.asarray(resized, dtype=np.float32) / 255.0
    array = (array - RMBG_MEAN) / RMBG_STD
    tensor = np.transpose(array, (2, 0, 1))[None, :, :, :]
    if "float16" in input_type:
        return tensor.astype(np.float16)
    return tensor.astype(np.float32)


def choose_providers(
    provider: str,
    available: Iterable[str] | None = None,
    system: str | None = None,
) -> list[str]:
    """Choose portable ONNX Runtime providers with a CPU fallback."""
    if available is None:
        import onnxruntime as ort

        available = ort.get_available_providers()

    available_set = set(available)
    system_name = system or platform.system()
    if provider == "cpu":
        return ["CPUExecutionProvider"]
    if provider == "cuda":
        if "CUDAExecutionProvider" not in available_set:
            raise RuntimeError(f"CUDAExecutionProvider is not available: {sorted(available_set)}")
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    if provider == "coreml":
        if "CoreMLExecutionProvider" not in available_set:
            raise RuntimeError(
                f"CoreMLExecutionProvider is not available: {sorted(available_set)}"
            )
        return ["CoreMLExecutionProvider", "CPUExecutionProvider"]
    if provider == "auto":
        if system_name == "Darwin" and "CoreMLExecutionProvider" in available_set:
            return ["CoreMLExecutionProvider", "CPUExecutionProvider"]
        if "CUDAExecutionProvider" in available_set:
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        return ["CPUExecutionProvider"]
    raise ValueError("provider must be one of: auto, cuda, coreml, cpu")


def with_cuda_provider_options(
    providers: Sequence[object],
    provider_options: Mapping[str, object] | None = None,
) -> list[object]:
    """Attach CUDA provider options without changing provider order."""
    if not provider_options:
        return list(providers)
    configured: list[object] = []
    for item in providers:
        if item == "CUDAExecutionProvider":
            configured.append(("CUDAExecutionProvider", dict(provider_options)))
        else:
            configured.append(item)
    return configured


def postprocess_mask(
    prediction: np.ndarray,
    original_size: tuple[int, int],
    activation: str = "auto",
) -> Image.Image:
    """Convert a raw model prediction into an 8-bit alpha mask."""
    mask = np.nan_to_num(np.asarray(prediction).astype(np.float32))
    while mask.ndim > 2 and mask.shape[0] == 1:
        mask = mask[0]
    if mask.ndim == 3:
        if mask.shape[0] == 1:
            mask = mask[0]
        elif mask.shape[-1] == 1:
            mask = mask[..., 0]
        else:
            mask = mask[-1]
    if mask.ndim == 1:
        mask = mask[None, :]
    if mask.ndim != 2:
        raise ValueError(f"Expected a 2D mask after squeeze, got shape {mask.shape}")

    if activation not in {"auto", "sigmoid", "none"}:
        raise ValueError("activation must be one of: auto, sigmoid, none")

    if activation == "sigmoid" or (
        activation == "auto" and (float(mask.min()) < 0.0 or float(mask.max()) > 1.0)
    ):
        mask = 1.0 / (1.0 + np.exp(-np.clip(mask, -80.0, 80.0)))

    mask = np.clip(mask, 0.0, 1.0)
    mask_u8 = (mask * 255.0).round().astype(np.uint8)
    return Image.fromarray(mask_u8, mode="L").resize(original_size, Image.Resampling.LANCZOS)


def normalize_output_format(output_format: str) -> str:
    normalized = (output_format or "png").strip().lower()
    if normalized not in SUPPORTED_OUTPUT_FORMATS:
        raise ValueError("output format must be one of: png, webp")
    return normalized


def normalize_processing_mode(processing_mode: str) -> str:
    normalized = (processing_mode or "rmbg").strip().lower()
    if normalized not in SUPPORTED_PROCESSING_MODES:
        raise ValueError("processing mode must be one of: rmbg, line_art")
    return normalized


def normalize_background_color(background_color: str) -> tuple[int, int, int]:
    try:
        channels = ImageColor.getrgb((background_color or "#FFFFFF").strip())
    except ValueError as exc:
        raise ValueError("background_color must be a valid CSS color such as #FFFFFF") from exc
    if len(channels) == 4:
        return channels[:3]
    return channels


def estimate_background_color(image: Image.Image) -> tuple[int, int, int]:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    border = np.concatenate(
        (rgba[0, :, :], rgba[-1, :, :], rgba[:, 0, :], rgba[:, -1, :]),
        axis=0,
    )
    visible_border = border[border[:, 3] > 0, :3]
    samples = visible_border if visible_border.size else border[:, :3]
    median = np.rint(np.median(samples, axis=0)).astype(np.uint8)
    return tuple(int(channel) for channel in median)


def build_line_art_image(
    image: Image.Image,
) -> tuple[Image.Image, Image.Image, tuple[int, int, int]]:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    rgb = rgba[..., :3]
    background_color = estimate_background_color(image)
    background_rgb = np.asarray(background_color, dtype=np.float32)

    grayscale = np.asarray(Image.fromarray(rgb, mode="RGB").convert("L"), dtype=np.int16)
    background_gray = Image.new("RGB", (1, 1), background_color).convert("L").getpixel((0, 0))
    gray_difference = np.abs(grayscale - int(background_gray)).astype(np.float32)
    border_difference = np.concatenate(
        (
            gray_difference[0, :],
            gray_difference[-1, :],
            gray_difference[:, 0],
            gray_difference[:, -1],
        )
    )
    background_tolerance = min(
        254.0,
        max(1.0, float(np.ceil(np.quantile(border_difference, 0.995))) + 1.0),
    )
    generated_alpha = np.clip(
        (gray_difference - background_tolerance) / (255.0 - background_tolerance),
        0.0,
        1.0,
    )
    source_alpha = rgba[..., 3].astype(np.float32) / 255.0
    alpha = generated_alpha * source_alpha

    foreground_rgb = rgb.astype(np.float32)
    nonzero = generated_alpha > 0
    if np.any(nonzero):
        foreground_rgb[nonzero] = (
            foreground_rgb[nonzero]
            - (1.0 - generated_alpha[nonzero, None]) * background_rgb
        ) / generated_alpha[nonzero, None]
    foreground_rgb = np.clip(np.rint(foreground_rgb), 0, 255).astype(np.uint8)
    alpha_u8 = np.clip(np.rint(alpha * 255.0), 0, 255).astype(np.uint8)

    output = Image.fromarray(np.dstack((foreground_rgb, alpha_u8)), mode="RGBA")
    mask = Image.fromarray(alpha_u8, mode="L")
    return output, mask, background_color


def optimize_alpha_mask(mask: Image.Image) -> Image.Image:
    return mask.convert("L").filter(ImageFilter.GaussianBlur(radius=0.45))


def build_output_image(
    image: Image.Image,
    mask: Image.Image,
    transparent_background: bool = True,
    background_color: str = "#FFFFFF",
    edge_optimize: bool = False,
) -> Image.Image:
    alpha = optimize_alpha_mask(mask) if edge_optimize else mask.convert("L")
    foreground = image.convert("RGBA")
    foreground.putalpha(alpha)
    if transparent_background:
        return foreground

    background = Image.new("RGBA", foreground.size, normalize_background_color(background_color) + (255,))
    background.alpha_composite(foreground)
    return background.convert("RGB")


def save_output_image(image: Image.Image, output_path: str | Path, output_format: str = "png") -> None:
    normalized_output_format = normalize_output_format(output_format)
    if normalized_output_format == "webp":
        image.save(output_path, format="WEBP", lossless=True, quality=95, method=6)
        return
    image.save(output_path, format="PNG")


def make_sample_image(path: str | Path) -> Path:
    """Create a simple local test image when the user has not supplied one yet."""
    output = Path(path)
    image = Image.new("RGB", (900, 650), "white")
    yy, xx = np.mgrid[0:650, 0:900]
    ellipse = ((xx - 450) / 230) ** 2 + ((yy - 335) / 175) ** 2 <= 1
    inner = ((xx - 450) / 95) ** 2 + ((yy - 335) / 70) ** 2 <= 1
    stem = (np.abs(xx - 450) <= 16) & (yy >= 90) & (yy <= 190)
    fruit = np.asarray(image).copy()
    fruit[ellipse] = [176, 32, 72]
    fruit[inner] = [232, 95, 126]
    fruit[stem] = [72, 92, 105]
    image = Image.fromarray(fruit)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    return output


def remove_background(
    model_path: str | Path,
    input_path: str | Path,
    output_path: str | Path,
    mask_path: str | Path | None = None,
    provider: str = "cuda",
    activation: str = "auto",
    output_index: int = -1,
    disable_mem_pattern: bool = False,
    disable_mem_reuse: bool = False,
    cuda_provider_options: Mapping[str, object] | None = None,
    disable_fallback: bool = False,
    output_format: str = "png",
    edge_optimize: bool = False,
    transparent_background: bool = True,
    background_color: str = "#FFFFFF",
    processing_mode: str = "rmbg",
) -> RmbgRunResult:
    """Run RMBG-2.0 ONNX inference and save an RGBA foreground image."""
    session = RmbgSession(
        model_path=model_path,
        provider=provider,
        activation=activation,
        output_index=output_index,
        disable_mem_pattern=disable_mem_pattern,
        disable_mem_reuse=disable_mem_reuse,
        cuda_provider_options=cuda_provider_options,
        disable_fallback=disable_fallback,
    )
    return session.remove_background(
        input_path=input_path,
        output_path=output_path,
        mask_path=mask_path,
        output_format=output_format,
        edge_optimize=edge_optimize,
        transparent_background=transparent_background,
        background_color=background_color,
        processing_mode=processing_mode,
    )
