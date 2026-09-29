"""Visual QA sheets: grayscale and colour-vision-deficiency simulations of every final figure,
plus a contact sheet of all six at a common width.

Usage: .venv-figures/bin/python paper/figures/qa.py  ->  paper/figures/qa/*.png

CVD simulation: Machado, Oliveira & Fernandes (2009) matrices at severity 1.0 (protanopia,
deuteranopia), applied in linear RGB. This is the same model the dataviz palette validator uses.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
FINAL, QA = HERE / "final", HERE / "qa"
MACHADO = {
    "protanopia": np.array([[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]]),
    "deuteranopia": np.array([[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]]),
}
W = 1600  # px width of QA renderings


def to_lin(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def to_srgb(x):
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(np.clip(x, 0, 1), 1 / 2.4) - 0.055)


def variants(img: Image.Image) -> dict[str, Image.Image]:
    a = np.asarray(img.convert("RGB"), float) / 255
    lin = to_lin(a)
    out = {"color": img.convert("RGB"), "grayscale": img.convert("L").convert("RGB")}
    for k, m in MACHADO.items():
        sim = to_srgb(np.clip(lin @ m.T, 0, 1))
        out[k] = Image.fromarray((sim * 255).round().astype(np.uint8))
    return out


def main() -> None:
    QA.mkdir(exist_ok=True)
    sheet_rows = []
    for png in sorted(FINAL.glob("figure*.png")):
        img = Image.open(png)
        img = img.resize((W, round(img.height * W / img.width)), Image.LANCZOS)
        v = variants(img)
        grid = Image.new("RGB", (W * 2, img.height * 2), "white")
        for i, k in enumerate(("color", "grayscale", "protanopia", "deuteranopia")):
            grid.paste(v[k], ((i % 2) * W, (i // 2) * img.height))
        grid.save(QA / f"{png.stem}_qa.png", optimize=True)
        sheet_rows.append(img)
    total = sum(r.height for r in sheet_rows) + 40 * (len(sheet_rows) - 1)
    sheet = Image.new("RGB", (W, total), "white")
    y = 0
    for r in sheet_rows:
        sheet.paste(r, (0, y))
        y += r.height + 40
    sheet.save(QA / "all_figures_contact_sheet.png", optimize=True)
    print(f"wrote {len(sheet_rows)} QA grids + contact sheet to {QA}")


if __name__ == "__main__":
    main()
