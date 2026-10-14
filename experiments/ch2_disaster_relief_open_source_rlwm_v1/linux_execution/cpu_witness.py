"""Seeded CPU-only kernel witness for the Linux execution environment."""

from __future__ import annotations

import os
import importlib


def main() -> int:
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise RuntimeError("CUDA_VISIBLE_DEVICES must be empty")

    import torch

    modules = (
        "numpy",
        "gymnasium",
        "tensordict",
        "torchrl",
        "hydra",
        "einops",
        "ruamel.yaml",
        "psutil",
    )
    for name in modules:
        importlib.import_module(name)
        print(f"IMPORT_OK module={name}")

    torch.manual_seed(8201)
    torch.set_num_threads(1)
    if torch.cuda.is_available() or torch.cuda.is_initialized():
        raise RuntimeError("CUDA was available or initialized in the CPU witness")

    values = torch.rand((2, 2), device="cpu")
    result = values @ values
    finite = bool(torch.isfinite(result).all().item())
    if not finite:
        raise RuntimeError("CPU matrix product returned non-finite values")
    print("WITNESS seed=8201 device=cpu shape=2x2 finite=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
