"""Run manifests: provenance for every CLI invocation that produces results."""

from __future__ import annotations

import hashlib
import importlib.metadata as md
import os
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fhr3.eval.matched import MATCHED_PROTOCOL_VERSION
from fhr3.io.schema import SCHEMA_VERSION
from fhr3.rng import SEED_DERIVATION_VERSION

REPO_ROOT = Path(__file__).resolve().parents[3]


def _run(cmd: list[str]) -> str | None:
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=10, check=True
        ).stdout.strip()
    except Exception:
        return None


def git_info() -> dict[str, Any]:
    sha = _run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"])
    status = _run(["git", "-C", str(REPO_ROOT), "status", "--porcelain", "--", "src", "pyproject.toml"])
    return {"sha": sha, "dirty": bool(status) if status is not None else None}


def dependency_info() -> dict[str, Any]:
    dists = sorted(
        {(d.metadata["Name"] or "").lower(): d.version for d in md.distributions()}.items()
    )
    lock = REPO_ROOT / "uv.lock"
    return {
        "packages": dict(dists),
        "uv_lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest() if lock.exists() else None,
        "pokerkit": md.version("pokerkit"),
    }


def machine_info() -> dict[str, Any]:
    brand = _run(["sysctl", "-n", "machdep.cpu.brand_string"]) if sys.platform == "darwin" else None
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_brand": brand,
        "cpu_count": os.cpu_count(),
        "hostname": platform.node(),
    }


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class RunManifest:
    run_id: str
    command: list[str]
    config_path: str | None
    config: dict[str, Any]
    config_hash: str
    pairing_hashes: dict[str, str]
    started_at: str = field(default_factory=now_iso)
    finished_at: str | None = None
    python: str = field(default_factory=lambda: sys.version)
    git: dict[str, Any] = field(default_factory=git_info)
    dependencies: dict[str, Any] = field(default_factory=dependency_info)
    machine: dict[str, Any] = field(default_factory=machine_info)
    seed_derivation_version: str = SEED_DERIVATION_VERSION
    schema_version: str = SCHEMA_VERSION
    matched_protocol_version: str = MATCHED_PROTOCOL_VERSION
    work: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    estimator_provenance: dict[str, Any] | None = None
    estimator_config_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def new_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    return f"{stamp}-{os.getpid()}-{os.urandom(3).hex()}"
