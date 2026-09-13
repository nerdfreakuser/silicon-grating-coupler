"""Figures from Tidy3D JSON. Exact 1550.00 nm. Fill-only is on the etch plot."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "analysis" / "figures"
RES = ROOT / "analysis" / "results"

colors = {
    "uniform": "#7a7a7a",
    "chirp": "#2e7d32",
    "taillaert": "#c45911",
    "proposed": "#1f4e79",
}
labels = {
    "uniform": "Uniform 50%",
    "chirp": "Period chirp",
    "taillaert": "Taillaert fill",
    "proposed": "Proposed fill+chirp",
}
ORDER = ["uniform", "chirp", "taillaert", "proposed"]

plt.rcParams.update(
    {
        "figure.dpi": 140,
        "savefig.dpi": 200,
        "font.size": 10,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def _jobs():
    return json.loads((RES / "tidy3d_compare.json").read_text(encoding="utf-8"))


def _il_etch(jobs, key, etch):
    if abs(etch - 70.0) < 1e-9:
        return float(jobs[f"nom_{key}"]["il_1550_db"])
    rec = jobs.get(f"etch{int(etch)}_{key}")
    if rec is None:
        return float("nan")
    return float(rec["il_1550_db"])


def main() -> None:
    payload = _jobs()
    jobs = payload["jobs"]

    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.0))
    for key in ORDER:
        job = jobs.get(f"nom_{key}")
        if not job:
            continue
        axes[0].plot(
            job["wavelengths_nm"],
            job["il_db"],
            color=colors[key],
            lw=2.2 if key == "proposed" else 1.6,
            label=labels[key],
        )
    axes[0].axvline(1550, color="0.45", ls=":", lw=1)
    axes[0].set_xlabel("wavelength (nm)")
    axes[0].set_ylabel("insertion loss (dB)")
    title = "Tidy3D 2-D, Δℓ = 16 nm, exact 1550 nm"
    if payload.get("best_offset_um"):
        title += ", aligned x_fib"
    axes[0].set_title(title)
    axes[0].legend(fontsize=8)

    for key in ORDER:
        xs, ys = [], []
        for etch in (58.0, 70.0, 82.0):
            y = _il_etch(jobs, key, etch)
            if y == y:
                xs.append(etch)
                ys.append(y)
        if len(xs) < 2:
            continue
        axes[1].plot(
            xs, ys, "-o", color=colors[key], lw=2.2 if key == "proposed" else 1.6, label=labels[key]
        )
    axes[1].axvline(70, color="0.45", ls="--", lw=1)
    axes[1].set_xlabel("etch depth (nm)")
    axes[1].set_ylabel("IL at 1550.00 nm (dB)")
    axes[1].set_title("Etch sweep includes fill-only (Taillaert)")
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "td00_spectra_etch.png", bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.6, 3.6))
    ils = [jobs[f"nom_{k}"]["il_1550_db"] for k in ORDER]
    ax.bar(range(4), ils, color=[colors[k] for k in ORDER])
    ax.set_xticks(range(4))
    ax.set_xticklabels([labels[k] for k in ORDER], rotation=12, ha="right")
    ax.set_ylabel("IL at 1550.00 nm (dB)")
    ax.set_title("Tidy3D in-coupling at 1550.00 nm")
    fig.tight_layout()
    fig.savefig(FIG / "td01_bars_1550.png", bbox_inches="tight")
    plt.close(fig)

    # worst-case across the three etch settings
    fig, ax = plt.subplots(figsize=(6.8, 3.7))
    nom, worst = [], []
    for k in ORDER:
        n = jobs[f"nom_{k}"]["il_1550_db"]
        w = max(_il_etch(jobs, k, e) for e in (58.0, 70.0, 82.0))
        nom.append(n)
        worst.append(w)
    x = np.arange(len(ORDER))
    ax.bar(x - 0.18, nom, 0.36, color=[colors[k] for k in ORDER], label="nominal 70 nm")
    ax.bar(x + 0.18, worst, 0.36, color=[colors[k] for k in ORDER], alpha=0.4, label="worst of 58/70/82 nm")
    ax.set_xticks(x)
    ax.set_xticklabels([labels[k] for k in ORDER], rotation=12, ha="right")
    ax.set_ylabel("IL at 1550.00 nm (dB)")
    ax.set_title("Worst-case IL over the three etch settings, not under-etch alone")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "td02_worst_etch.png", bbox_inches="tight")
    plt.close(fig)

    align_path = RES / "tidy3d_align.json"
    if align_path.is_file():
        al = json.loads(align_path.read_text(encoding="utf-8"))
        fig, ax = plt.subplots(figsize=(6.8, 3.7))
        for key in ORDER:
            pts = [
                (j["x_fib_offset_um"], j["il_1550_db"])
                for j in al["jobs"].values()
                if j.get("design") == key
            ]
            pts.sort()
            if not pts:
                continue
            ax.plot(
                [p[0] for p in pts],
                [p[1] for p in pts],
                "-o",
                color=colors[key],
                lw=2.0 if key == "proposed" else 1.5,
                label=labels[key],
            )
        ax.set_xlabel("fiber x offset from grating midpoint (µm)")
        ax.set_ylabel("IL at 1550.00 nm (dB)")
        ax.set_title("Matched alignment: minimise IL over longitudinal fiber offset")
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(FIG / "td03_align.png", bbox_inches="tight")
        plt.close(fig)

    conv_path = RES / "tidy3d_converge.json"
    if conv_path.is_file():
        conv = json.loads(conv_path.read_text(encoding="utf-8"))["jobs"]
        fig, ax = plt.subplots(figsize=(6.8, 3.7))
        for key in ORDER:
            xs, ys = [], []
            if f"nom_{key}" in jobs:
                xs.append(16.0)
                ys.append(jobs[f"nom_{key}"]["il_1550_db"])
            for dl, name in ((8.0, f"conv8_{key}"), (4.0, f"conv4_{key}")):
                if name in conv:
                    xs.append(dl)
                    ys.append(conv[name]["il_1550_db"])
            if len(xs) >= 2:
                ax.plot(
                    xs, ys, "-o", color=colors[key], lw=2.0 if key == "proposed" else 1.5, label=labels[key]
                )
        ax.set_xlabel("grid Δℓ (nm)")
        ax.set_ylabel("IL at 1550.00 nm (dB)")
        ax.set_title("Mesh series at frozen geometry and frozen x_fib")
        ax.invert_xaxis()
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(FIG / "td04_converge.png", bbox_inches="tight")
        plt.close(fig)

    print("wrote td00–td04 as available in", FIG)


if __name__ == "__main__":
    main()
