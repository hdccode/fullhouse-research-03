"""Sparse PHH tracing.

Which blocks are traced is itself deterministic (a keyed hash of the block
seed), so the traced subset is identical across serial/parallel/resumed runs.
Any untraced block can be traced later with ``fhr3 replay --trace``.
"""

from __future__ import annotations

from pathlib import Path

from fhr3.configs.experiment import TracePolicy
from fhr3.rng import KeyedStream


def should_trace(policy: TracePolicy, block_id: int, seed: int) -> bool:
    if block_id in policy.block_ids:
        return True
    if policy.rate <= 0:
        return False
    return KeyedStream("trace-selection", seed).random() < policy.rate


def trace_dir(root: Path, experiment_id: str, pairing_id: str, block_id: int) -> Path:
    return Path(root) / experiment_id / pairing_id / f"block_{block_id:09d}"


def write_traces(directory: Path, traces: dict[str, str]) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    out = []
    for name, text in sorted(traces.items()):
        p = directory / f"{name}.phh"
        p.write_text(text)
        out.append(p)
    return out
