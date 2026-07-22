from __future__ import annotations

import argparse
from pathlib import Path

import rmbg_onnx


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BRIA RMBG-2.0 ONNX background removal.")
    parser.add_argument("--model", default="model.onnx", help="Path to RMBG-2.0 ONNX model.")
    parser.add_argument("--input", default="sample_input.png", help="Input image. A sample is created if missing.")
    parser.add_argument("--output", default="sample_output_rgba.png", help="Output RGBA PNG path.")
    parser.add_argument("--mask", default="sample_mask.png", help="Output alpha mask PNG path.")
    parser.add_argument("--provider", choices=["cuda", "auto", "cpu"], default="cuda")
    parser.add_argument("--activation", choices=["auto", "sigmoid", "none"], default="auto")
    parser.add_argument(
        "--output-index",
        type=int,
        default=-1,
        help="Model output index to use as alpha matte. RMBG reference code uses the last output.",
    )
    parser.add_argument("--disable-mem-pattern", action="store_true")
    parser.add_argument("--disable-mem-reuse", action="store_true")
    parser.add_argument(
        "--strict-provider",
        action="store_true",
        help="Disable ONNX Runtime provider fallback so CUDA errors are not hidden.",
    )
    parser.add_argument(
        "--cuda-cudnn-conv-algo-search",
        choices=["EXHAUSTIVE", "HEURISTIC", "DEFAULT"],
        help="CUDAExecutionProvider cudnn_conv_algo_search option.",
    )
    parser.add_argument(
        "--cuda-cudnn-conv-use-max-workspace",
        choices=["0", "1"],
        help="CUDAExecutionProvider cudnn_conv_use_max_workspace option.",
    )
    parser.add_argument(
        "--cuda-use-tf32",
        choices=["0", "1"],
        help="CUDAExecutionProvider use_tf32 option.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists() and input_path.name == "sample_input.png":
        created = rmbg_onnx.make_sample_image(input_path)
        print(f"created sample input: {created.resolve()}")

    cuda_provider_options = {}
    if args.cuda_cudnn_conv_algo_search:
        cuda_provider_options["cudnn_conv_algo_search"] = args.cuda_cudnn_conv_algo_search
    if args.cuda_cudnn_conv_use_max_workspace:
        cuda_provider_options["cudnn_conv_use_max_workspace"] = args.cuda_cudnn_conv_use_max_workspace
    if args.cuda_use_tf32:
        cuda_provider_options["use_tf32"] = args.cuda_use_tf32

    result = rmbg_onnx.remove_background(
        model_path=args.model,
        input_path=input_path,
        output_path=args.output,
        mask_path=args.mask,
        provider=args.provider,
        activation=args.activation,
        output_index=args.output_index,
        disable_mem_pattern=args.disable_mem_pattern,
        disable_mem_reuse=args.disable_mem_reuse,
        cuda_provider_options=cuda_provider_options or None,
        disable_fallback=args.strict_provider,
    )

    print(f"requested providers: {result.provider_requested}")
    print(f"active providers: {result.provider_active}")
    print(f"input: name={result.input_name}, type={result.input_type}, shape={result.input_shape}")
    print(f"outputs: {result.output_names}")
    print(f"model load seconds: {result.load_seconds:.3f}")
    print(f"inference seconds: {result.inference_seconds:.3f}")
    print(
        "mask stats: "
        f"min={result.mask_min:.6f}, max={result.mask_max:.6f}, mean={result.mask_mean:.6f}"
    )
    print(f"saved rgba: {result.output_path.resolve()}")
    if result.mask_path:
        print(f"saved mask: {result.mask_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
