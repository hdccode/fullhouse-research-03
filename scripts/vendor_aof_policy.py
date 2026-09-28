"""Vendor the FullHouse 4-max AoF production policy v2 into fhr3 (reproducible).

Usage: python scripts/vendor_aof_policy.py [path/to/aof-ml]

Reads aof-ml's canonical results/reference-diagnostics/aof-4max-reference-policy-4m-v2.json
and writes src/fhr3/agents/data/aof_4max_8bb_production_v2.json containing only
the non-fold probability per (decision node, hand class) plus provenance.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

SRC_REL = "results/reference-diagnostics/aof-4max-reference-policy-4m-v2.json"
OUT = Path(__file__).resolve().parents[1] / "src/fhr3/agents/data/aof_4max_8bb_production_v2.json"


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / "aof-ml")
    src = root / SRC_REL
    raw = src.read_bytes()
    d = json.loads(raw)
    commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    nodes = {}
    for n in d["nodes"]:
        nodes[n["decision_node_id"]] = {
            "acting_position": n["acting_position"],
            "prior_actions": ["A" if a["action"] != "fold" else "F" for a in n["prior_action_sequence"]],
            "non_fold_action": [a for a in n["legal_actions"] if a != "fold"][0],
            "p": {},
        }
    for r in d["rows"]:
        node = nodes[r["decision_node_id"]]
        probs = r["action_probabilities"]
        p = probs[node["non_fold_action"]]
        assert abs(p + probs["fold"] - 1.0) < 1e-9
        node["p"][r["hand"]] = p
    assert all(len(n["p"]) == 169 for n in nodes.values()) and len(nodes) == 14
    out = {
        "policy_id": "fullhouse-aof-4max-8bb-production-v2",
        "game": {"players": 4, "stack_bb": 8, "blinds_bb": [0.5, 1.0], "positions": ["CO", "BTN", "SB", "BB"]},
        "provenance": {
            "source_repo": "aof-ml",
            "source_commit": commit,
            "source_file": SRC_REL,
            "source_file_sha256": hashlib.sha256(raw).hexdigest(),
            "source_content_hash": d["content_hash"],
            "source_schema_version": d["schema_version"],
            "source_rules_fingerprint": d["rules_fingerprint"],
            "note": "Adopted production backend v2 (aof-ml docs/AOF_4MAX_PRODUCTION_ADOPTION_PROTOCOL.md).",
        },
        "nodes": nodes,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True))
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
