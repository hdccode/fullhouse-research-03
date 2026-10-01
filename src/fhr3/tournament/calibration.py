"""Balanced field EV calibration (research reference, never a tournament score).

Design: a calibration *round* is a uniformly random partition of the bots into
tables of the mode's size (a keyed shuffle; when the pool size is not a multiple of
the table size the last ``P mod k`` bots of the shuffle sit out that round). Every
table plays one match under the protocol's own match rules (H hands, stack rule, the
2026 dealer rotation). Over many rounds every bot meets random opponents in random
seats, so

    mu_field(i) = E[ chip delta of i per match | uniformly random table ]

is i's long-run balanced field EV in chips per H-hand match. Rounds are independent
units: the primary per-bot SE is analytic (sd / sqrt(matches)); a bootstrap over round
*groups* that resamples the complete bot vector jointly (cross-bot covariance kept) feeds
ranking / gap / robustness diagnostics only.

Matched (duplicate) calibration plays every table as k lanes (k = table size) and stores
the lane-summed delta per bot. The reported reference is on the ordinary-match scale,

    mu_field = mean(lane_sum) / k,

with the raw ``mu_field_lane_sum`` kept for provenance. Compact per-lane outcomes (no hand
histories) are persisted beside every chunk under ``lanes/`` and validated: each lane is
zero-sum, every bot starts in every seat exactly once per duplicate match, the lane count
equals the mode's table size, and lane deltas add up exactly to the stored lane sum.

Common random numbers: the seed depends on (seed_family, namespace) only, so every field
reference in one namespace reads the same chance/decision streams for a given
(round, table, hand). Cross-field reference estimates are therefore *coupled* (correlated),
not independent replications, and must not be analysed under an independence assumption.

Matchup structure: ``M[i, j] = E[delta_i | j at the table] - mu_i`` (presence effect)
and its antisymmetric part ``A = M - M^T``. ``hodge`` / ``subset_hodge`` (the retired v1
matchup gate) remain available for provenance only; ``analyse_calibration`` no longer
computes them.

Seeds: ``derive_seed("fhr3b-calibration", seed_family, namespace)`` with namespace
``pool-calibration`` or ``field-reference`` (disjoint from tournaments).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from fhr3.tournament.agents import build_agent
from fhr3.rng import KeyedStream, derive_seed
from fhr3.tournament.fields import FieldManifest, Mode, field_from_dict, game_from_dict
from fhr3.tournament.manifests import check_namespace, engine_source_hash, identity_hash
from fhr3.tournament.match import (
    MATCH_ENGINE_VERSION,
    DuplicateMatchPlayer,
    MatchKey,
    PokerMatchPlayer,
    SyntheticMatchPlayer,
)

CALIBRATION_VERSION = "fhr3b-calibration-v1"
LANE_STORE_VERSION = "fhr3b-calibration-lanes-v1"  # duplicate calibrations only (identity key)
ROW_SCHEMA = pa.schema([("round", pa.int32()), ("table_index", pa.int16()), ("seat", pa.int8()),
                        ("table_size", pa.int8()), ("bot_id", pa.string()), ("chip_delta", pa.int64()),
                        ("hands_played", pa.int32())])
LANE_SCHEMA = pa.schema([("round", pa.int32()), ("table_index", pa.int16()), ("lane", pa.int8()),
                         ("bot_id", pa.string()), ("start_seat", pa.int8()), ("chip_delta", pa.int64()),
                         ("hands_played", pa.int32()), ("bust_hand", pa.int32()), ("busted", pa.bool_())])


class CalibrationLaneError(AssertionError):
    pass


@dataclass(frozen=True)
class CalibrationSpec:
    mode: Mode
    field: FieldManifest
    hands_per_match: int
    stack_policy: str
    seed_family: str
    namespace: str  # pool-calibration | field-reference | test
    chunk_rounds: int = 25
    synthetic: dict[str, Any] | None = None
    match_format: str = "ordinary"  # "duplicate": matched k-lane matches (equal-work rounds set by the caller)

    def __post_init__(self) -> None:
        check_namespace(self.namespace)
        if self.match_format not in ("ordinary", "duplicate"):
            raise ValueError("match_format must be ordinary or duplicate")

    @cached_property
    def identity(self) -> dict[str, Any]:
        return {"calibration_version": CALIBRATION_VERSION, "match_engine_version": MATCH_ENGINE_VERSION,
                "mode": self.mode.to_dict(), "field_hash": self.field.field_hash, "H": self.hands_per_match,
                "stack_policy": self.stack_policy, "seed_family": self.seed_family, "namespace": self.namespace,
                "chunk_rounds": self.chunk_rounds, "synthetic": self.synthetic} | (
                    {"match_format": self.match_format, "lane_store": LANE_STORE_VERSION}
                    if self.match_format != "ordinary" else {})

    @property
    def lanes(self) -> int:
        """Duplicate lanes per match (= table size); 1 for ordinary calibration."""
        return self.mode.table_size if self.match_format == "duplicate" else 1

    @property
    def calib_id(self) -> str:
        fmt = ".dup" if self.match_format == "duplicate" else ""
        return (f"{self.mode.mode}.{self.field.field_id}.H{self.hands_per_match}{fmt}.{self.namespace}"
                f".{identity_hash(self.identity)[:8]}")

    @property
    def seed(self) -> int:
        return derive_seed("fhr3b-calibration", self.seed_family, self.namespace)

    def partition(self, round_: int) -> list[list[str]]:
        order = KeyedStream("fhr3b-calibration-partition", self.seed, round_).shuffle(sorted(self.field.bot_ids))
        k = self.mode.table_size
        full = len(order) // k
        return [order[t * k : (t + 1) * k] for t in range(full)]

    def make_player(self) -> Any:
        if self.synthetic is not None:
            return SyntheticMatchPlayer(self.synthetic["strength"], self.synthetic.get("noise_sd", 100.0),
                                        self.synthetic.get("edge"))
        specs = self.field.specs()
        if self.match_format == "duplicate":
            return DuplicateMatchPlayer(self.mode.game, self.stack_policy,
                                        lambda: {b: build_agent(s) for b, s in specs.items()})
        return PokerMatchPlayer(self.mode.game, self.stack_policy, {b: build_agent(s) for b, s in specs.items()})

    def to_dict(self) -> dict[str, Any]:
        return {"mode": self.mode.to_dict() | {"primary": self.mode.primary}, "field": self.field.to_dict(),
                "hands_per_match": self.hands_per_match, "stack_policy": self.stack_policy,
                "seed_family": self.seed_family, "namespace": self.namespace, "chunk_rounds": self.chunk_rounds,
                "synthetic": self.synthetic, "match_format": self.match_format}


def spec_from_dict(d: dict[str, Any]) -> CalibrationSpec:
    m = d["mode"]
    mode = Mode(m["mode"], game_from_dict(m["game"]), int(m["table_size"]), m["stack_policy"],
                m["agent_family"], bool(m.get("primary", False)))
    return CalibrationSpec(mode, field_from_dict(d["field"]), int(d["hands_per_match"]), d["stack_policy"],
                           d["seed_family"], d["namespace"], int(d.get("chunk_rounds", 25)), d.get("synthetic"),
                           d.get("match_format", "ordinary"))


def play_rounds(spec: CalibrationSpec, start: int, end: int, player: Any,
                lane_rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Calibration rows of rounds [start, end); duplicate matches also append per-lane rows to ``lane_rows``."""
    chance = derive_seed("fhr3b-calibration-chance", spec.seed)
    decision = derive_seed("fhr3b-calibration-decision", spec.seed)
    rows = []
    for r in range(start, end):
        for t, seat_order in enumerate(spec.partition(r)):
            res = player.play(MatchKey(chance, decision, r, t), seat_order, spec.hands_per_match)
            if sum(res.deltas.values()) != 0:
                raise AssertionError(f"calibration round {r} table {t}: not zero-sum")
            for s, b in enumerate(seat_order):
                rows.append({"round": r, "table_index": t, "seat": s, "table_size": len(seat_order), "bot_id": b,
                             "chip_delta": int(res.deltas[b]), "hands_played": res.hands_played})
            if lane_rows is not None:
                for ln in res.info.get("duplicate_lanes", ()):
                    for start_seat, b in enumerate(ln["seat_order"]):
                        bh = int(ln["bust_hand"].get(b, -1))
                        lane_rows.append({"round": r, "table_index": t, "lane": ln["lane"], "bot_id": b,
                                          "start_seat": start_seat, "chip_delta": int(ln["deltas"][b]),
                                          "hands_played": int(ln["hands_played"]), "bust_hand": bh,
                                          "busted": bh >= 0})
    return rows


def validate_lane_rows(rows: Sequence[dict[str, Any]], lane_rows: Sequence[dict[str, Any]], lanes: int) -> None:
    """Per-lane invariants of a duplicate calibration chunk (raises CalibrationLaneError)."""

    def fail(msg: str) -> None:
        raise CalibrationLaneError(msg)

    tables: dict[tuple[int, int], dict[str, dict[str, Any]]] = {}
    for x in rows:
        tables.setdefault((int(x["round"]), int(x["table_index"])), {})[x["bot_id"]] = x
    by: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for ln in lane_rows:
        by.setdefault((int(ln["round"]), int(ln["table_index"])), []).append(ln)
    if set(by) != set(tables):
        fail("lane rows do not cover exactly the calibration tables")
    for (r, t), members in tables.items():
        lr = by[(r, t)]
        k = len(members)
        if k != lanes:
            fail(f"round {r} table {t}: table size {k} != lane count {lanes}")
        if sorted({int(ln["lane"]) for ln in lr}) != list(range(lanes)) or len(lr) != lanes * k:
            fail(f"round {r} table {t}: lane count does not match mode ({lanes})")
        lane_hands = {}
        for lane in range(lanes):
            one = [ln for ln in lr if int(ln["lane"]) == lane]
            if sorted(ln["bot_id"] for ln in one) != sorted(members):
                fail(f"round {r} table {t} lane {lane}: seated bots differ from the table")
            if sum(int(ln["chip_delta"]) for ln in one) != 0:
                fail(f"round {r} table {t} lane {lane}: not zero-sum")
            if sorted(int(ln["start_seat"]) for ln in one) != list(range(k)):
                fail(f"round {r} table {t} lane {lane}: start seats incomplete")
            if len({int(ln["hands_played"]) for ln in one}) != 1:
                fail(f"round {r} table {t} lane {lane}: inconsistent hands_played")
            lane_hands[lane] = int(one[0]["hands_played"])
            if any(bool(ln["busted"]) != (int(ln["bust_hand"]) >= 0) for ln in one):
                fail(f"round {r} table {t} lane {lane}: busted flag disagrees with bust_hand")
        for b, row in members.items():
            mine = [ln for ln in lr if ln["bot_id"] == b]
            if sorted(int(ln["start_seat"]) for ln in mine) != list(range(k)):
                fail(f"round {r} table {t}: {b} does not start in every seat exactly once")
            if sum(int(ln["chip_delta"]) for ln in mine) != int(row["chip_delta"]):
                fail(f"round {r} table {t}: {b} lane deltas do not sum to the stored lane-summed delta")
            if sum(lane_hands.values()) != int(row["hands_played"]):
                fail(f"round {r} table {t}: lane hands do not sum to the stored hands_played")


# ------------------------------------------------------------------ storage + execution
def calib_dir(root: Path, spec: CalibrationSpec) -> Path:
    return Path(root) / "calibration" / spec.calib_id


def _chunk_path(root: Path, spec: CalibrationSpec, a: int, b: int) -> Path:
    return calib_dir(root, spec) / "chunks" / f"c_{a:07d}_{b:07d}.parquet"


def _lane_path(root: Path, spec: CalibrationSpec, a: int, b: int) -> Path:
    return calib_dir(root, spec) / "lanes" / f"l_{a:07d}_{b:07d}.parquet"


def _write_atomic(p: Path, table: pa.Table) -> None:
    import os

    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(f".parquet.tmp{os.getpid()}")
    pq.write_table(table, tmp, compression="zstd")
    os.replace(tmp, p)


_W: dict[str, Any] = {}


def _init(d: dict[str, Any], root: str) -> None:
    spec = spec_from_dict(d)
    _W.update(spec=spec, root=Path(root), player=spec.make_player())


def _work(ab: tuple[int, int]) -> int:
    a, b = ab
    spec, root = _W["spec"], _W["root"]
    dup = spec.match_format == "duplicate"
    lane_rows: list[dict[str, Any]] | None = [] if dup else None
    rows = play_rounds(spec, a, b, _W["player"], lane_rows)
    if dup:  # validate, then write lanes first: the chunk file is the completion marker
        validate_lane_rows(rows, lane_rows, spec.lanes)
        _write_atomic(_lane_path(root, spec, a, b), pa.Table.from_pylist(lane_rows, schema=LANE_SCHEMA))
    _write_atomic(_chunk_path(root, spec, a, b), pa.Table.from_pylist(rows, schema=ROW_SCHEMA))
    return len(rows)


def run_calibration(spec: CalibrationSpec, root: Path, rounds: int, workers: int = 1,
                    allow_source_change: bool = False, progress: bool = True) -> dict[str, Any]:
    from concurrent.futures import ProcessPoolExecutor, as_completed
    from multiprocessing import get_context

    from fhr3.tournament.store import write_json_atomic

    root = Path(root)
    d = calib_dir(root, spec)
    lock = {"calib_id": spec.calib_id, "identity": spec.identity, "identity_hash": identity_hash(spec.identity),
            "spec": spec.to_dict(), "engine_source_hash": engine_source_hash()}
    lock = json.loads(json.dumps(lock, default=str))
    lp = d / "calibration.lock.json"
    if lp.exists():
        have = json.loads(lp.read_text())
        if have["identity_hash"] != lock["identity_hash"]:
            raise RuntimeError(f"{lp}: calibration identity differs")
        if have["engine_source_hash"] != lock["engine_source_hash"] and not allow_source_change:
            raise RuntimeError(f"{lp}: result-relevant source changed; use --allow-source-change deliberately")
    else:
        write_json_atomic(lp, lock)
    c = spec.chunk_rounds
    units = [(a, min(a + c, rounds)) for a in range(0, rounds, c)]
    todo = [u for u in units if not _chunk_path(root, spec, *u).exists()]
    if spec.match_format == "duplicate":
        missing = [u for u in units if u not in todo and not _lane_path(root, spec, *u).exists()]
        if missing:
            raise RuntimeError(f"{d}: chunks without per-lane rows {missing[:3]}")
    if workers <= 1:
        _init(spec.to_dict(), str(root))
        for i, u in enumerate(todo, 1):
            _work(u)
            if progress:
                print(f"  {spec.calib_id} chunk {i}/{len(todo)}", flush=True)
    elif todo:
        with ProcessPoolExecutor(workers, mp_context=get_context("spawn"), initializer=_init,
                                 initargs=(spec.to_dict(), str(root))) as ex:
            futs = [ex.submit(_work, u) for u in todo]
            for i, f in enumerate(as_completed(futs), 1):
                f.result()
                if progress:
                    print(f"  {spec.calib_id} chunk {i}/{len(todo)}", flush=True)
    return {"calib_id": spec.calib_id, "chunks_total": len(units), "chunks_run": len(todo)}


def verify_calibration_lanes(root: Path, spec: CalibrationSpec) -> int:
    """Re-validate every stored chunk of a duplicate calibration against its per-lane rows."""
    if spec.match_format != "duplicate":
        return 0
    n = 0
    for f in sorted((calib_dir(root, spec) / "chunks").glob("c_*.parquet")):
        _, a, b = f.stem.split("_")
        lp = _lane_path(root, spec, int(a), int(b))
        if not lp.exists():
            raise CalibrationLaneError(f"{f.name}: per-lane rows missing")
        validate_lane_rows(pq.read_table(f).to_pylist(), pq.read_table(lp).to_pylist(), spec.lanes)
        n += 1
    return n


def load_calibration(root: Path, spec: CalibrationSpec, max_rounds: int | None = None) -> list[pa.Table]:
    files = sorted((calib_dir(root, spec) / "chunks").glob("c_*.parquet"))
    tabs = [pq.read_table(f) for f in files]
    if max_rounds is not None:
        tabs = [t for t, f in zip(tabs, files, strict=True) if int(f.stem.split("_")[2]) <= max_rounds]
    return tabs


# ------------------------------------------------------------------ analysis
@dataclass
class GroupStats:
    """Additive sufficient statistics of one group of calibration rounds."""

    n: np.ndarray  # (P,) matches per bot
    s: np.ndarray  # (P,) sum of deltas
    ss: np.ndarray  # (P,) sum of squared deltas
    pn: np.ndarray  # (P, P) matches where i and j shared a table
    ps: np.ndarray  # (P, P) sum of delta_i over those matches
    pss: np.ndarray  # (P, P) sum of squared delta_i


def group_stats(table: pa.Table, bots: Sequence[str]) -> GroupStats:
    idx = {b: i for i, b in enumerate(bots)}
    p = len(bots)
    g = GroupStats(np.zeros(p), np.zeros(p), np.zeros(p), np.zeros((p, p)), np.zeros((p, p)), np.zeros((p, p)))
    d = table.to_pydict()
    matches: dict[tuple[int, int], list[tuple[int, float]]] = {}
    for r, t, b, x in zip(d["round"], d["table_index"], d["bot_id"], d["chip_delta"], strict=True):
        matches.setdefault((r, t), []).append((idx[b], float(x)))
    for members in matches.values():
        ids = np.array([i for i, _ in members])
        xs = np.array([x for _, x in members])
        g.n[ids] += 1
        g.s[ids] += xs
        g.ss[ids] += xs * xs
        g.pn[np.ix_(ids, ids)] += 1
        g.ps[np.ix_(ids, ids)] += xs[:, None]
        g.pss[np.ix_(ids, ids)] += (xs * xs)[:, None]
    for arr in (g.pn, g.ps, g.pss):
        np.fill_diagonal(arr, 0)
    return g


def _combine(groups: Sequence[GroupStats], w: np.ndarray | None = None) -> GroupStats:
    w = np.ones(len(groups)) if w is None else w
    return GroupStats(*(sum(wi * getattr(g, f) for wi, g in zip(w, groups, strict=True))
                        for f in ("n", "s", "ss", "pn", "ps", "pss")))


def _matchup(g: GroupStats) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(mu, M, var(M)) from combined stats. M[i,j] = E[delta_i | j present] - mu_i."""
    with np.errstate(invalid="ignore", divide="ignore"):
        mu = g.s / g.n
        var_i = g.ss / g.n - mu * mu
        cond = g.ps / g.pn
        m = cond - mu[:, None]
        cond_var = g.pss / g.pn - cond * cond
        var_m = cond_var / g.pn
    m = np.where(g.pn > 0, m, np.nan)
    np.fill_diagonal(m, 0.0)
    var_m = np.where(g.pn > 1, var_m, np.nan)
    np.fill_diagonal(var_m, 0.0)
    return mu, m, var_m


def hodge(a: np.ndarray, var_a: np.ndarray) -> dict[str, float]:
    """Transitive/cyclic split of an antisymmetric flow on the complete graph, noise-debiased."""
    p = a.shape[0]
    iu = np.triu_indices(p, 1)
    if not np.isfinite(a[iu]).all():
        return {"total": np.nan, "gradient": np.nan, "cyclic": np.nan, "noise": np.nan,
                "cyclic_share_raw": np.nan, "cyclic_share_debiased": np.nan}
    r = a.mean(axis=1)
    grad = r[:, None] - r[None, :]
    total = float((a[iu] ** 2).sum())
    g_e = float((grad[iu] ** 2).sum())
    c_e = total - g_e
    noise = float(np.nansum(var_a[iu]))
    npairs = len(iu[0])
    frac_grad = (p - 1) / npairs
    c_star = c_e - noise * (1 - frac_grad)
    g_star = g_e - noise * frac_grad
    denom = c_star + g_star
    return {"total": total, "gradient": g_e, "cyclic": c_e, "noise": noise,
            "cyclic_share_raw": c_e / total if total > 0 else np.nan,
            "cyclic_share_debiased": c_star / denom if denom > 0 else np.nan}


def cyclic_triads(a: np.ndarray) -> dict[str, float]:
    """Fraction of triads whose majority-of-flow signs form a cycle (i>j>k>i)."""
    p = a.shape[0]
    s = np.sign(np.nan_to_num(a))
    cyc = tot = 0
    for i in range(p):
        for j in range(i + 1, p):
            for k in range(j + 1, p):
                tot += 1
                if s[i, j] == s[j, k] == s[k, i] != 0:
                    cyc += 1
    return {"triads": tot, "cyclic_triads": cyc, "cyclic_fraction": cyc / tot if tot else np.nan}


def analyse_calibration(tables: Sequence[pa.Table], bots: Sequence[str], n_boot: int = 300,
                        seed: int = 20260929, lanes: int = 1) -> dict[str, Any]:
    """Per-bot reference strength on the ordinary-match scale.

    ``mu`` = mean stored delta / ``lanes`` (``lanes`` = k for matched calibration, so the
    k-lane sum becomes ordinary-match-equivalent); ``mu_lane_sum`` keeps the raw mean.
    ``se`` is the analytic sd / sqrt(matches) (primary). ``boot_mu`` (n_boot x P) comes from
    resampling round groups with ONE weight vector for the whole bot vector, so cross-bot
    covariance is preserved; it is for ranking / gap / robustness diagnostics, and
    ``se_boot`` is reported only as a check. ``M``/``var_M`` are on the same scale as ``mu``.
    """
    groups = [group_stats(t, bots) for t in tables]
    tot = _combine(groups)
    mu_raw, m, var_m = _matchup(tot)
    sd_raw = np.sqrt(np.maximum(tot.ss / tot.n - mu_raw * mu_raw, 0))
    sc = 1.0 / lanes
    n_arr = np.stack([g.n for g in groups])
    s_arr = np.stack([g.s for g in groups])
    rng = np.random.Generator(np.random.PCG64(seed))
    w = rng.multinomial(len(groups), np.full(len(groups), 1 / len(groups)), size=n_boot).astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        boot_mu = (w @ s_arr) / (w @ n_arr) * sc
    se_boot = boot_mu.std(axis=0, ddof=1) if n_boot > 1 else np.full(len(bots), np.nan)
    return {"bots": list(bots), "lanes": lanes, "mu": mu_raw * sc, "mu_lane_sum": mu_raw,
            "se": sd_raw / np.sqrt(tot.n) * sc, "se_boot": se_boot, "sd": sd_raw * sc, "sd_lane_sum": sd_raw,
            "n_matches": tot.n, "M": m * sc, "var_M": var_m * sc * sc, "pair_n": tot.pn, "boot_mu": boot_mu,
            "rounds_groups": len(groups), "groups": groups}


def subset_share_ci(res: dict[str, Any], ids: Sequence[str], n_boot: int = 300,
                    seed: int = 20260931) -> tuple[float, float, float]:
    """Debiased cyclic share of a bot subset with a bootstrap (over round groups) 95% CI."""
    ix = [res["bots"].index(b) for b in ids]
    point = subset_hodge(res, ids)["cyclic_share_debiased"]
    groups = res["groups"]
    rng = np.random.Generator(np.random.PCG64(seed))
    vals = []
    for _ in range(n_boot):
        w = rng.multinomial(len(groups), np.full(len(groups), 1 / len(groups))).astype(float)
        _, bm, bv = _matchup(_combine(groups, w))
        m, v = bm[np.ix_(ix, ix)], bv[np.ix_(ix, ix)]
        x = hodge(m - m.T, v + v.T)["cyclic_share_debiased"]
        if np.isfinite(x):
            vals.append(x)
    if len(vals) < 10:
        return point, float("nan"), float("nan")
    return point, float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))


def calibration_digest(root: Path, spec: CalibrationSpec) -> str:
    import hashlib

    h = hashlib.sha256()
    for f in sorted((calib_dir(root, spec) / "chunks").glob("c_*.parquet")):
        h.update(f.name.encode() + b"\0" + f.read_bytes())
    for f in sorted((calib_dir(root, spec) / "lanes").glob("l_*.parquet")):  # duplicate only; none for pool
        h.update(f.name.encode() + b"\0" + f.read_bytes())
    return h.hexdigest()[:32]


def subset_hodge(res: dict[str, Any], ids: Sequence[str]) -> dict[str, float]:
    ix = [res["bots"].index(b) for b in ids]
    m = res["M"][np.ix_(ix, ix)]
    v = res["var_M"][np.ix_(ix, ix)]
    return hodge(m - m.T, v + v.T)


def select_matchup(res: dict[str, Any], candidates: Sequence[str], n: int) -> list[str]:
    """Greedy backward elimination maximising the debiased cyclic share (ties: bot_id)."""
    keep = sorted(candidates)
    while len(keep) > n:
        best = None
        for b in keep:
            rest = [x for x in keep if x != b]
            share = subset_hodge(res, rest)["cyclic_share_debiased"]
            share = -np.inf if not np.isfinite(share) else share
            if best is None or share > best[0] + 1e-15:
                best = (share, b)
        keep.remove(best[1])
    return keep


def bot_rows(res: dict[str, Any], field: FieldManifest) -> list[dict[str, Any]]:
    meta = {b["bot_id"]: b.get("meta", {}) for b in field.bots}
    order = np.argsort(-res["mu"], kind="stable")
    rows = []
    for rank, i in enumerate(order, 1):
        b = res["bots"][i]
        row = {"bot_id": b, "reference_rank": rank, "mu_field": float(res["mu"][i]),
               "se": float(res["se"][i]), "ci_lo": float(res["mu"][i] - 1.96 * res["se"][i]),
               "ci_hi": float(res["mu"][i] + 1.96 * res["se"][i]), "sd_per_match": float(res["sd"][i]),
               "n_matches": int(res["n_matches"][i])}
        if res.get("lanes", 1) > 1:  # matched calibration: provenance of the k-lane sum
            row |= {"lanes": int(res["lanes"]), "mu_field_lane_sum": float(res["mu_lane_sum"][i]),
                    "sd_lane_sum": float(res["sd_lane_sum"][i]), "se_bootstrap": float(res["se_boot"][i])}
        rows.append(row | {f"meta_{k}": v for k, v in meta.get(b, {}).items()})
    return rows


def matchup_rows(res: dict[str, Any]) -> Iterable[dict[str, Any]]:
    bots = res["bots"]
    for i, a in enumerate(bots):
        for j, c in enumerate(bots):
            if i != j:
                yield {"bot_id": a, "opponent_id": c, "n_shared_matches": int(res["pair_n"][i, j]),
                       "presence_effect": float(res["M"][i, j]), "se": float(np.sqrt(res["var_M"][i, j]))
                       if np.isfinite(res["var_M"][i, j]) else float("nan")}
