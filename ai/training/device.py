"""Where training runs: `auto` takes CUDA when present, otherwise the CPU (SPEC 13 OQ-11:
CI trains small on CPU, real runs go to a GPU machine)."""

from __future__ import annotations

import torch

DEVICE_CHOICES = ("auto", "cpu", "cuda", "mps")


def pick_device(name: str = "auto") -> torch.device:
    if name == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if name == "cuda" and not torch.cuda.is_available():
        raise SystemExit("--device cuda was asked for but no CUDA GPU is available")
    if name == "mps" and not torch.backends.mps.is_available():
        raise SystemExit("--device mps was asked for but Apple's MPS backend is unavailable")
    if name not in DEVICE_CHOICES:
        raise SystemExit(f"unknown device {name!r}; choose from {', '.join(DEVICE_CHOICES)}")
    return torch.device(name)
