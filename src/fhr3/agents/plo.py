"""PLO heuristic family: the HeuristicAgent decision skeleton with Omaha features.

Same philosophy as the NLHE family (soft thresholds, one uniform per decision,
explicit action distributions), different hand evaluation:

* preflop strength = percentile of a Hutchison-style 4-card score;
* postflop made-hand strength uses the exact 2-hole + 3-board rule, with set /
  top-two / nut-flush distinctions and paired/flushy-board discounts;
* draws: Omaha flush draws (two suited hole cards + two on board; non-nut draws
  discounted) and straight outs computed under the 2+3 rule.

Bet sizes are clamped to PokerKit's pot-limit bounds by ``_raise_action``, so
"pot" is simply ``raise_max``.
"""

from __future__ import annotations

from dataclasses import replace

from fhr3.agents.heuristic import HeuristicAgent, StyleParams, _clip01
from fhr3.agents.omaha_features import omaha_postflop_features, omaha_preflop_percentile
from fhr3.games.base import Observation

PLO_IMPL_VERSION = "plo-heuristic-1.0.0"

_PLO_BASE = StyleParams(
    open_pct_by_seats_behind=(0.50, 0.34, 0.25, 0.20, 0.18, 0.16, 0.15, 0.14),
    sb_open_pct=0.40,
    call_open_pct=0.18,
    bb_defend_pct=0.40,
    threebet_pct=0.06,
    call_3bet_pct=0.10,
    fourbet_pct=0.025,
    call_4bet_pct=0.04,
    preflop_temperature=0.02,
    open_size_bb=3.5,  # a pot-sized open from the first position
    threebet_mult=3.5,  # clamped to the pot limit by the legal range
    fourbet_mult=3.0,
    value_threshold=0.62,
    raise_threshold=0.85,
    bet_fraction=0.75,
    raise_pot_fraction=1.0,
    semibluff_freq=0.5,
    bluff_freq=0.08,
    multiway_exponent=0.6,
)

PLO_STYLES: dict[str, StyleParams] = {
    "neutral": _PLO_BASE,
    "tight": replace(_PLO_BASE, looseness=0.75, aggression=0.9, call_margin=0.03),
    "loose": replace(_PLO_BASE, looseness=1.35, call_margin=-0.03, bluff_freq=0.06),
    "aggressive": replace(_PLO_BASE, looseness=1.15, aggression=1.4, bluff_freq=0.14, semibluff_freq=0.65),
}


class PLOHeuristicAgent(HeuristicAgent):
    IMPL = PLO_IMPL_VERSION
    STYLE_TABLE = PLO_STYLES

    def preflop_strength(self, obs: Observation) -> float:
        return omaha_preflop_percentile(obs.hole_cards)

    def strength(self, obs: Observation) -> tuple[float, float]:
        f = omaha_postflop_features(obs.hole_cards, obs.board)
        cat = int(f["category"])
        hole_ranks = [c[0] for c in obs.hole_cards]
        board_ranks = [c[0] for c in obs.board]
        top = f["top_rank"]
        if cat == 0:
            s = 0.08
        elif cat == 1:
            pocket = hole_ranks.count("23456789TJQKA"[int(top)]) >= 2
            if pocket and top > f["board_high"]:
                s = 0.35
            elif top == f["board_high"]:
                s = 0.30
            else:
                s = 0.18
        elif cat == 2:
            s = 0.50 if top == f["board_high"] else 0.38
        elif cat == 3:
            rank = "23456789TJQKA"[int(top)]
            is_set = hole_ranks.count(rank) >= 2 and board_ranks.count(rank) == 1
            s = (0.78 if top == f["board_high"] else 0.70) if is_set else 0.55
        elif cat == 4:
            s = 0.78
        elif cat == 5:
            s = 0.93 if f["nut_flush"] else 0.80
        elif cat == 6:
            s = 0.95
        else:
            s = 0.99
        if cat <= 4:
            s -= 0.12 * f["board_flushy"] + 0.08 * f["board_paired"]
        elif cat == 5:
            s -= 0.10 * f["board_paired"]
        outs = 9.0 * f["flush_draw"] * (1.0 if f["nut_flush_draw"] else 0.7) + min(4.0 * f["straight_outs"], 20.0)
        to_come = 5 - len(obs.board)
        draw_eq = _clip01(outs * (0.04 if to_come == 2 else 0.02 if to_come == 1 else 0.0))
        return _clip01(s), draw_eq
