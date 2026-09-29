"""Shared design system for the FHR3 paper figures (Matplotlib).

Every visual constant lives here: palette, encodings, orders, type sizes, line widths,
reference-line style, tick formatting, panel letters, deterministic label placement and
export. Figure scripts import from this module and never define their own styling.

Palette: the 7 categorical slots of the dataviz reference palette, in slot order. It is
validated with the skill's validate_palette.js for light mode: lightness band, chroma floor,
adjacent CVD ΔE ≥ 8 (worst 9.1), normal-vision floor ≥ 15 (worst 19.6). Three slots sit below
3:1 contrast on white; every figure therefore carries direct labels or marker shapes as
relief, and colour is never the only encoding. Okabe-Ito and Paul Tol muted/bright failed the
lightness band for thin marks on white (see ARCHITECTURE.md).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator

# ------------------------------------------------------------------ geometry & type
MM = 1 / 25.4
WIDTH = 183 * MM  # double-column width, inches
FONT = "Arial"  # present on the build machine; Helvetica is the fallback
BASE = 6.5  # pt at final size
SMALL = 6.0
TINY = 5.5
LETTER = 8.0
INK = "#1a1a1a"  # text primary
INK2 = "#52514e"  # text secondary
INK3 = "#8a8984"  # muted
RULE = "#c9c8c3"  # hairline reference / guide
LW_DATA = 1.0
LW_THIN = 0.6
LW_AXIS = 0.5
MS = 3.6  # marker size, pt
RIBBON_ALPHA = 0.14

# ------------------------------------------------------------------ encodings
FORMATS = ["AoF 4-max 8BB", "NLHE 4-max", "NLHE 6-max", "Crazy Pineapple", "Nit Game", "PLO", "Bomb Pot"]
FORMAT_SHORT = {"AoF 4-max 8BB": "AoF 8BB", "NLHE 4-max": "NLHE 4-max", "NLHE 6-max": "NLHE 6-max",
                "Crazy Pineapple": "Crazy Pineapple", "Nit Game": "Nit Game", "PLO": "PLO", "Bomb Pot": "Bomb Pot"}
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7"]
FORMAT_COLOR = dict(zip(FORMATS, PALETTE, strict=True))
ROLES = ("p1", "p2", "p3")
ROLE_MARKER = {"p1": "o", "p2": "s", "p3": "^"}
ROLE_MS = {"p1": MS, "p2": MS * 0.88, "p3": MS * 1.05}  # visually equal areas
# RQ7 methods: red = the invalid rule, near-black = the valid sequential method, grey = fixed look
METHODS = ["fixed-N (one look)", "naive peeking", "confidence sequence"]
METHOD_COLOR = {"fixed-N (one look)": "#8a8984", "naive peeking": "#e34948", "confidence sequence": "#1a1a1a"}
METHOD_MARKER = {"fixed-N (one look)": "D", "naive peeking": "X", "confidence sequence": "h"}
METHOD_MS = {"fixed-N (one look)": MS * 0.85, "naive peeking": MS * 1.05, "confidence sequence": MS * 1.05}


def setup() -> None:
    mpl.rcParams.update({
        "font.family": FONT, "font.size": BASE, "text.color": INK,
        "axes.labelsize": BASE, "axes.labelcolor": INK, "axes.titlesize": BASE, "axes.edgecolor": INK2,
        "axes.linewidth": LW_AXIS, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": False, "axes.titlelocation": "left", "axes.titlepad": 3,
        "xtick.labelsize": SMALL, "ytick.labelsize": SMALL, "xtick.color": INK2, "ytick.color": INK2,
        "xtick.labelcolor": INK, "ytick.labelcolor": INK,
        "xtick.major.width": LW_AXIS, "ytick.major.width": LW_AXIS, "xtick.minor.width": 0.35, "ytick.minor.width": 0.35,
        "xtick.major.size": 2.5, "ytick.major.size": 2.5, "xtick.minor.size": 1.4, "ytick.minor.size": 1.4,
        "xtick.major.pad": 1.8, "ytick.major.pad": 1.8, "lines.linewidth": LW_DATA, "lines.solid_capstyle": "round",
        "legend.fontsize": SMALL, "legend.frameon": False, "savefig.facecolor": "white",
        "svg.fonttype": "none", "svg.hashsalt": "fhr3-figures", "pdf.fonttype": 42, "ps.fonttype": 42,
        "axes.unicode_minus": True, "path.simplify": False,
    })


# ------------------------------------------------------------------ axes helpers
def fmt_count(x: float, _=None) -> str:
    """Log-axis count labels: 10k, 100k, 1M, 10M (plain for < 1,000)."""
    if x >= 1e9:
        return f"{x / 1e9:g}B"
    if x >= 1e6:
        return f"{x / 1e6:g}M"
    if x >= 1e3:
        return f"{x / 1e3:g}k"
    return f"{x:g}"


def minus(text: str) -> str:
    """Typographic minus for signed numbers in annotations (Arial has U+2212)."""
    return text.replace("-", "\u2212")


def fmt_hours(x: float, _=None) -> str:
    if x >= 1:
        return f"{x:g} h"
    if x >= 1 / 60:
        return f"{x * 60:g} min"
    return f"{x * 3600:g} s"


def log_axis(ax, which: str, ticks: Sequence[float], formatter=fmt_count, minor: bool = False) -> None:
    axis = ax.xaxis if which == "x" else ax.yaxis
    (ax.set_xscale if which == "x" else ax.set_yscale)("log")
    axis.set_major_locator(FixedLocator(list(ticks)))
    axis.set_major_formatter(FuncFormatter(formatter))
    if not minor:
        axis.set_minor_locator(NullLocator())


def ref_line(ax, value: float, axis: str = "x", color: str = INK2, lw: float = LW_THIN, dashed: bool = True, **kw) -> None:
    style = dict(color=color, lw=lw, zorder=0.5, **kw)
    if dashed:
        style["dashes"] = (2.2, 1.6)
    (ax.axvline if axis == "x" else ax.axhline)(value, **style)


def panel_letter(fig, ax, letter: str, dx: float = -0.0, dy: float = 0.0) -> None:
    """Bold lowercase letter aligned to the figure-left of the axes' tight bbox, top edge."""
    fig.canvas.draw()
    bb = ax.get_tightbbox(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
    fig.text(bb.x0 + dx, bb.y1 + dy, letter, fontsize=LETTER, fontweight="bold", va="top", ha="left", color=INK)


def panel_title(ax, letter: str, title: str, right: str | None = None, y: float = 1.06) -> None:
    """Bold lowercase panel letter + sentence-case title on one baseline above the axes;
    optional right-aligned muted note on the same baseline."""
    ax.text(0.0, y, letter, transform=ax.transAxes, fontsize=LETTER, fontweight="bold", ha="right", va="baseline",
            color=INK)
    ax.text(0.02, y, title, transform=ax.transAxes, fontsize=BASE, ha="left", va="baseline", color=INK)
    if right:
        ax.text(1.0, y, right, transform=ax.transAxes, fontsize=TINY, ha="right", va="baseline", color=INK2)


def role_handles(color: str = INK2) -> list:
    from matplotlib.lines import Line2D

    return [Line2D([], [], ls="none", marker=ROLE_MARKER[r], ms=ROLE_MS[r], mfc=color, mec="white", mew=0.4,
                   label=f"pairing {r}") for r in ROLES]


def spread_labels(y: Sequence[float], min_gap: float, lo: float | None = None, hi: float | None = None) -> np.ndarray:
    """Deterministic 1-D label de-overlap: keep order, enforce min_gap, minimise total displacement
    (pool-adjacent-violators on y_i - i*gap), then clamp to [lo, hi]."""
    y = np.asarray(y, float)
    order = np.argsort(y)
    z = y[order] - np.arange(y.size) * min_gap
    blocks = [[v] for v in z]  # isotonic regression (non-decreasing) by pooling
    i = 0
    while i < len(blocks) - 1:
        if np.mean(blocks[i]) > np.mean(blocks[i + 1]):
            blocks[i] += blocks.pop(i + 1)
            i = max(i - 1, 0)
        else:
            i += 1
    fitted = np.concatenate([[np.mean(b)] * len(b) for b in blocks]) + np.arange(y.size) * min_gap
    if lo is not None and fitted[0] < lo:
        fitted += lo - fitted[0]
    if hi is not None and fitted[-1] > hi:
        fitted -= fitted[-1] - hi
    out = np.empty_like(fitted)
    out[order] = fitted
    return out


# ------------------------------------------------------------------ export
OUT = Path(__file__).parent / "final"


def save(fig, stem: str) -> dict[str, str]:
    """SVG (editable text), PDF (TrueType), 600-dpi PNG (RGB); fixed metadata for determinism."""
    OUT.mkdir(parents=True, exist_ok=True)
    meta_common = {"Creator": "FHR3 paper/figures (matplotlib)"}
    fig.savefig(OUT / f"{stem}.svg", format="svg", metadata={**meta_common, "Date": None})
    fig.savefig(OUT / f"{stem}.pdf", format="pdf", metadata={**meta_common, "CreationDate": None, "ModDate": None})
    # Agg always renders RGBA: flatten onto white and write RGB (Google Docs / print friendly)
    import io

    from PIL import Image

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=600)
    buf.seek(0)
    rgba = Image.open(buf)
    rgb = Image.new("RGB", rgba.size, "white")
    rgb.paste(rgba, mask=rgba.split()[3])
    rgb.save(OUT / f"{stem}.png", format="PNG", dpi=(600, 600), optimize=False)
    plt.close(fig)
    return {ext: hashlib.sha256((OUT / f"{stem}.{ext}").read_bytes()).hexdigest() for ext in ("svg", "pdf", "png")}
