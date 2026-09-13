"""2-D FDTD comparison: proposed coupler vs strong baselines, identical constraints.

Usage:
    python analysis/run_em_compare.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from photonic_coupler.constants import SI, SIO2, SOI220, UM  # noqa: E402
from photonic_coupler.fdtd2d import (  # noqa: E402
    build_grid,
    fiber_ce,
    index_at_nm,
    peak_and_bw,
    run_gc,
    run_reference,
)
from photonic_coupler.gc_designs import all_designs  # noqa: E402

FIG = ROOT / "analysis" / "figures"
RES = ROOT / "analysis" / "results"
FIG.mkdir(parents=True, exist_ok=True)
RES.mkdir(parents=True, exist_ok=True)

DX = 25e-9
N_PERIODS = 20
# 1550.00 nm is on the grid. Do not infer it from a neighbouring bin.
WL = np.array([1525, 1535, 1545, 1550, 1555, 1565, 1575], dtype=float) * 1e-9

plt.rcParams.update(
    {
        "figure.dpi": 140,
        "savefig.dpi": 200,
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 11,
        "legend.fontsize": 8,
        "figure.facecolor": "white",
        "axes.grid": True,
        "grid.alpha": 0.25,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def _ce(out, pin):
    return fiber_ce(
        out["ey_fib"],
        out["x_line"],
        pin,
        SOI220.theta_deg,
        SOI220.mfd,
        SOI220.cladding.n,
        out["wavelengths"],
        hx_line=out.get("hx_fib"),
    )


def run_campaign() -> dict:
    I1550 = index_at_nm(WL, 1550.0)
    designs = all_designs(N_PERIODS)
    Lmax = max(d.length for d in designs)
    grid = build_grid(Lmax, dx=DX, pml_um=1.0)
    print(
        f"grid {grid.nx} x {grid.nz}  dx={DX*1e9:.1f} nm  "
        f"dt={grid.dt*1e15:.3f} fs  designs={len(designs)}"
    )
    t0 = time.time()
    print("reference waveguide...")
    pin = run_reference(grid, WL, SOI220.t_si)
    print(f"  pin_1550={pin[np.argmin(np.abs(WL-1.55e-6))]:.3e}  ({time.time()-t0:.1f}s)")

    spectra = {}
    fields = {}
    for d in designs:
        t1 = time.time()
        print(f"nominal {d.short}...")
        out = run_gc(d, grid, WL, store_field=d.short in ("uniform", "proposed"))
        met = _ce(out, pin)
        pk = peak_and_bw(WL, met["ce"])
        spectra[d.short] = {
            "name": d.name,
            "color": d.color,
            "proposed": d.proposed,
            "ce": met["ce"].tolist(),
            "il_db": met["il_db"].tolist(),
            "overlap": met["overlap"].tolist(),
            "directionality": met["p_up_over_pin"].tolist(),
            "x0_opt": met["x0_opt"].tolist(),
            **pk,
            "lambda_nm": 1550.0,
            "fill_start": d.fill_start,
            "fill_end": d.fill_end,
            "length_um": d.length / UM,
            "elapsed_s": time.time() - t1,
        }
        print(
            f"  IL@1550={-10*np.log10(max(pk['ce_1550'],1e-16)):.2f} dB  "
            f"peak={pk['peak_il_db']:.2f} dB @ {pk['wl_peak_nm']:.0f} nm  "
            f"BW1dB={pk['bw_1db_nm']:.1f} nm  ({time.time()-t1:.1f}s)"
        )
        if "field" in out:
            fields[d.short] = {
                "field": np.abs(out["field"]),
                "eps": out["eps"],
                "x": out["x"],
                "z": out["z"],
            }

    def dump(payload):
        (RES / "fdtd_compare.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def sweep(kind: str, values, apply, skip_nominal=None):
        table = {d.short: [] for d in designs if d.short in ("uniform", "chirp", "proposed")}
        for val in values:
            for d in designs:
                if d.short not in table:
                    continue
                if skip_nominal is not None and abs(val - skip_nominal) < 1e-12:
                    # reuse nominal 1550 nm result
                    table[d.short].append(
                        {
                            "value": float(val),
                            "lambda_nm": 1550.0,
                            "ce_1550": float(spectra[d.short]["ce"][I1550]),
                            "il_1550": float(spectra[d.short]["il_db"][I1550]),
                            "peak_ce": float(max(spectra[d.short]["ce"])),
                            "elapsed_s": 0.0,
                            "from_nominal": True,
                        }
                    )
                    continue
                t1 = time.time()
                kw = apply(val)
                out = run_gc(d, grid, WL, **kw)
                met = _ce(out, pin)
                table[d.short].append(
                    {
                        "value": float(val),
                        "lambda_nm": 1550.0,
                        "ce_1550": float(met["ce"][I1550]),
                        "il_1550": float(met["il_db"][I1550]),
                        "peak_ce": float(np.max(met["ce"])),
                        "elapsed_s": time.time() - t1,
                    }
                )
                print(
                    f"  {kind}={val:.3g} {d.short}: IL@1550.0nm="
                    f"{met['il_db'][I1550]:.2f} dB ({time.time()-t1:.1f}s)"
                )
        return table

    payload = {
        "dx_nm": DX / 1e-9,
        "n_periods": N_PERIODS,
        "wavelengths_nm": (WL / 1e-9).tolist(),
        "spectra": spectra,
        "etch": {},
        "t_si": {},
        "cd": {},
        "elapsed_s": time.time() - t0,
        "constraints": {
            "t_si_nm": 220,
            "etch_nm": 70,
            "box_um": 2.0,
            "min_cd_nm": 150,
            "theta_deg": 8.0,
            "mfd_um": 10.4,
            "n_periods": N_PERIODS,
        },
    }
    dump(payload)
    print("checkpoint: nominal spectra saved")

    print("etch sweep...")
    etch = sweep(
        "etch_nm",
        [58e-9, 64e-9, 70e-9, 76e-9, 82e-9],
        lambda e: {"etch": e},
        skip_nominal=70e-9,
    )
    payload["etch"] = etch
    dump(payload)
    print("t_si sweep...")
    tsi = sweep(
        "t_si_nm",
        [214e-9, 220e-9, 226e-9],
        lambda t: {"t_si": t},
        skip_nominal=220e-9,
    )
    payload["t_si"] = tsi
    dump(payload)
    print("CD bias sweep...")
    cd = sweep(
        "cd_nm",
        [-5e-9, 0.0, 5e-9],
        lambda c: {"cd_bias": c},
        skip_nominal=0.0,
    )
    payload["cd"] = cd
    payload["elapsed_s"] = time.time() - t0

    payload = {
        "dx_nm": DX / 1e-9,
        "n_periods": N_PERIODS,
        "wavelengths_nm": (WL / 1e-9).tolist(),
        "spectra": spectra,
        "etch": etch,
        "t_si": tsi,
        "cd": cd,
        "elapsed_s": time.time() - t0,
        "constraints": {
            "t_si_nm": 220,
            "etch_nm": 70,
            "box_um": 2.0,
            "min_cd_nm": 150,
            "theta_deg": 8.0,
            "mfd_um": 10.4,
            "n_periods": N_PERIODS,
        },
    }
    # numpy fields saved separately
    np.savez_compressed(RES / "fdtd_fields.npz", **{
        f"{k}_abs": v["field"] for k, v in fields.items()
    } | {
        f"{k}_eps": v["eps"] for k, v in fields.items()
    } | {
        f"{k}_x": v["x"] for k, v in fields.items()
    } | {
        f"{k}_z": v["z"] for k, v in fields.items()
    })
    (RES / "fdtd_compare.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("wrote", RES / "fdtd_compare.json", f"total {time.time()-t0:.1f}s")
    return payload, fields


def _il(ce):
    return -10.0 * np.log10(np.maximum(np.asarray(ce, dtype=float), 1e-16))


def _on_grid(wl_nm: np.ndarray, values: np.ndarray, target_nm: float) -> float:
    wl_nm = np.asarray(wl_nm, dtype=float)
    values = np.asarray(values, dtype=float)
    hit = np.where(np.isclose(wl_nm, target_nm, atol=1e-9))[0]
    if len(hit) == 0:
        raise RuntimeError(
            f"{target_nm} nm is not on the wavelength grid {wl_nm.tolist()}; "
            "do not interpolate a missing design wavelength"
        )
    return float(values[int(hit[0])])


def _il_on_grid(wl_nm: np.ndarray, ce: np.ndarray, target_nm: float = 1550.0) -> float:
    return float(_il(_on_grid(wl_nm, ce, target_nm)))


def _sweep_il(data: dict, kind: str, key: str, value: float) -> float:
    for row in data.get(kind, {}).get(key, []):
        if abs(float(row["value"]) - value) < 1e-12:
            return float(row["il_1550"])
    return float("nan")


def _cache_is_current(data: dict) -> bool:
    wl = [float(x) for x in data.get("wavelengths_nm", [])]
    if not any(abs(x - 1550.0) < 1e-6 for x in wl):
        return False
    etch = data.get("etch") or {}
    if not all(k in etch for k in ("uniform", "chirp", "proposed")):
        return False
    rows = etch.get("proposed") or []
    if not rows:
        return False
    if abs(float(rows[0].get("lambda_nm", 0.0)) - 1550.0) > 1e-6:
        return False
    # skip_nominal 70 nm row must equal the on-grid 1550 sample, not 1545.
    # numpy.isclose default atol=1e-8 aliases those two on a metre grid.
    spec = data.get("spectra") or {}
    if "uniform" not in spec:
        return False
    nom = -10.0 * np.log10(max(float(spec["uniform"]["ce_1550"]), 1e-16))
    u70 = next((r for r in etch["uniform"] if abs(float(r["value"]) - 70e-9) < 1e-12), None)
    if u70 is None or abs(float(u70["il_1550"]) - nom) > 0.05:
        return False
    return True


def make_figures(data: dict, fields: dict) -> None:
    wl = np.array(data["wavelengths_nm"])
    specs = data["spectra"]
    order = ["uniform", "chirp", "taillaert", "proposed"]

    # --- spectra ---
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.0))
    for key in order:
        s = specs[key]
        axes[0].plot(wl, np.array(s["ce"]) * 100, color=s["color"], lw=2.2 if s["proposed"] else 1.6, label=s["name"])
        axes[1].plot(wl, s["il_db"], color=s["color"], lw=2.2 if s["proposed"] else 1.6, label=s["name"])
    axes[0].axvline(1550, color="0.6", ls=":", lw=1)
    axes[1].axvline(1550, color="0.6", ls=":", lw=1)
    axes[0].set_xlabel("wavelength (nm)")
    axes[0].set_ylabel("coupling efficiency (%)")
    axes[0].set_title("2-D FDTD, identical 220 nm SOI constraints")
    axes[1].set_xlabel("wavelength (nm)")
    axes[1].set_ylabel("insertion loss (dB)")
    axes[1].set_title("Lower is better")
    axes[1].invert_yaxis()
    axes[0].legend(loc="best")
    fig.tight_layout()
    fig.savefig(FIG / "em01_spectra.png", bbox_inches="tight")
    plt.close(fig)

    # --- bar chart at 1550 and peak ---
    fig, ax = plt.subplots(figsize=(7.4, 3.8))
    x = np.arange(len(order))
    il1550 = [_il_on_grid(wl, specs[k]["ce"], 1550.0) for k in order]
    ilpeak = [specs[k]["peak_il_db"] for k in order]
    cols = [specs[k]["color"] for k in order]
    w = 0.38
    ax.bar(x - w / 2, il1550, w, color=cols, alpha=0.95, label="IL at 1550.00 nm")
    ax.bar(x + w / 2, ilpeak, w, color=cols, alpha=0.45, hatch="//", label="peak IL")
    ax.set_xticks(x)
    ax.set_xticklabels([specs[k]["name"].split(":")[0] if ":" in specs[k]["name"] else specs[k]["name"] for k in order], rotation=12, ha="right")
    ax.set_ylabel("insertion loss (dB)")
    ax.set_title("Same stack, same min CD, same fiber, same aperture")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "em02_bars.png", bbox_inches="tight")
    plt.close(fig)

    # --- etch tolerance ---
    fig, ax = plt.subplots(figsize=(6.6, 3.8))
    for key, label, col, lw in (
        ("uniform", "Uniform 50%", specs["uniform"]["color"], 1.6),
        ("chirp", "Period chirp", specs["chirp"]["color"], 1.6),
        ("proposed", "Proposed", specs["proposed"]["color"], 2.3),
    ):
        if key not in data.get("etch", {}):
            continue
        xs = [r["value"] * 1e9 for r in data["etch"][key]]
        ys = [r["il_1550"] for r in data["etch"][key]]
        ax.plot(xs, ys, "-o", color=col, lw=lw, label=label)
    ax.axvline(70, color="0.5", ls="--", lw=1)
    ax.set_xlabel("etch depth (nm)")
    ax.set_ylabel("IL at 1550.00 nm (dB)")
    ax.set_title("Manufacturing tolerance: partial-etch depth (includes chirp)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "em03_etch.png", bbox_inches="tight")
    plt.close(fig)

    # --- t_si and CD ---
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 3.8))
    for key, label, col, lw in (
        ("uniform", "Uniform 50%", specs["uniform"]["color"], 1.6),
        ("chirp", "Period chirp", specs["chirp"]["color"], 1.6),
        ("proposed", "Proposed", specs["proposed"]["color"], 2.3),
    ):
        if key in data.get("t_si", {}):
            xs = [r["value"] * 1e9 for r in data["t_si"][key]]
            ys = [r["il_1550"] for r in data["t_si"][key]]
            axes[0].plot(xs, ys, "-o", color=col, lw=lw, label=label)
        if key in data.get("cd", {}):
            xs = [r["value"] * 1e9 for r in data["cd"][key]]
            ys = [r["il_1550"] for r in data["cd"][key]]
            axes[1].plot(xs, ys, "-o", color=col, lw=lw, label=label)
    axes[0].axvline(220, color="0.5", ls="--", lw=1)
    axes[1].axvline(0, color="0.5", ls="--", lw=1)
    axes[0].set_xlabel("Si thickness (nm)")
    axes[1].set_xlabel("CD bias (nm)")
    axes[0].set_ylabel("IL at 1550.00 nm (dB)")
    axes[1].set_ylabel("IL at 1550.00 nm (dB)")
    axes[0].set_title("SOI thickness")
    axes[1].set_title("Litho CD bias")
    axes[0].legend()
    fig.tight_layout()
    fig.savefig(FIG / "em04_tsi_cd.png", bbox_inches="tight")
    plt.close(fig)

    # --- field maps ---
    if "uniform" in fields and "proposed" in fields:
        fig, axes = plt.subplots(2, 1, figsize=(8.4, 5.6), sharex=True)
        for ax, key, title in (
            (axes[0], "uniform", "Uniform 50% fill"),
            (axes[1], "proposed", "Proposed fill + angle-preserving chirp"),
        ):
            f = fields[key]
            xum = f["x"] / UM
            zum = f["z"] / UM
            amp = np.clip(f["field"].T, 1e-3, None)
            im = ax.imshow(
                amp,
                origin="lower",
                extent=[xum[0], xum[-1], zum[0], zum[-1]],
                aspect="auto",
                cmap="magma",
                norm=LogNorm(vmin=np.percentile(amp, 40), vmax=np.percentile(amp, 99.5)),
            )
            # Si outline
            si = f["eps"].T >= (0.5 * (SI.n**2 + SIO2.n**2))
            ax.contour(xum, zum, si.astype(float), levels=[0.5], colors="white", linewidths=0.4)
            ax.set_ylabel("z (µm)")
            ax.set_title(title)
            fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02, label="|Ey| (a.u.)")
        axes[1].set_xlabel("x (µm)")
        fig.suptitle("2-D FDTD |Ey| at 1550 nm, same color scale class", y=1.01)
        fig.tight_layout()
        fig.savefig(FIG / "em05_fields.png", bbox_inches="tight")
        plt.close(fig)

    # --- robustness score: worst IL in etch sweep minus nominal ---
    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    labels, nom, worst, cols = [], [], [], []
    for key in ("uniform", "chirp", "proposed"):
        if key not in data.get("etch", {}):
            continue
        s = specs[key]
        labels.append(s["name"].split("(")[0].strip() if "(" in s["name"] else s["name"].split(":")[0])
        n = _il(s["ce_1550"])
        w = max(r["il_1550"] for r in data["etch"][key])
        nom.append(n)
        worst.append(w)
        cols.append(s["color"])
    x = np.arange(len(labels))
    ax.bar(x - 0.18, nom, 0.36, color=cols, label="nominal IL @ 1550 nm")
    ax.bar(x + 0.18, worst, 0.36, color=cols, alpha=0.4, label="worst IL over etch ±12 nm")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=10, ha="right")
    ax.set_ylabel("insertion loss (dB)")
    ax.set_title("Nominal performance vs etch-depth robustness")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "em06_robust.png", bbox_inches="tight")
    plt.close(fig)

    # --- dashboard ---
    fig = plt.figure(figsize=(12.8, 8.4))
    gs = fig.add_gridspec(2, 2, hspace=0.38, wspace=0.28, left=0.07, right=0.98, top=0.90, bottom=0.08)
    ax0 = fig.add_subplot(gs[0, 0])
    ax1 = fig.add_subplot(gs[0, 1])
    ax2 = fig.add_subplot(gs[1, 0])
    ax3 = fig.add_subplot(gs[1, 1])
    for key in order:
        s = specs[key]
        ax0.plot(wl, _il(s["ce"]), color=s["color"], lw=2.3 if s["proposed"] else 1.5, label=s["name"])
    ax0.axvline(1550, color="0.6", ls=":", lw=1)
    ax0.set_xlabel("wavelength (nm)")
    ax0.set_ylabel("insertion loss (dB)")
    ax0.set_title("A  Spectra under identical constraints")
    ax0.legend(fontsize=7.5, loc="upper right")

    x = np.arange(len(order))
    ax1.bar(x, [_il_on_grid(wl, specs[k]["ce"], 1550.0) for k in order], color=[specs[k]["color"] for k in order])
    ax1.set_xticks(x)
    ax1.set_xticklabels(["Uniform", "Chirp", "Taillaert", "Proposed"])
    ax1.set_ylabel("IL at 1550.00 nm (dB)")
    ax1.set_title("B  Head-to-head at 1550.00 nm")

    for key, lab in (("uniform", "Uniform"), ("chirp", "Chirp"), ("proposed", "Proposed")):
        if key not in data.get("etch", {}):
            continue
        xs = [r["value"] * 1e9 for r in data["etch"][key]]
        ys = [r["il_1550"] for r in data["etch"][key]]
        ax2.plot(xs, ys, "-o", color=specs[key]["color"], lw=2.1 if key == "proposed" else 1.5, label=lab)
    ax2.axvline(70, color="0.5", ls="--")
    ax2.set_xlabel("etch depth (nm)")
    ax2.set_ylabel("IL at 1550.00 nm (dB)")
    ax2.set_title("C  Etch-depth manufacturing tolerance")
    ax2.legend()

    # delta-IL table as bars: proposed minus each baseline at 1550
    base = _il_on_grid(wl, specs["proposed"]["ce"], 1550.0)
    deltas = [base - _il_on_grid(wl, specs[k]["ce"], 1550.0) for k in ("uniform", "chirp", "taillaert")]
    ax3.axhline(0, color="0.5", lw=1)
    ax3.bar(["vs Uniform", "vs Chirp", "vs Taillaert"], deltas, color=["#7a7a7a", "#2e7d32", "#c45911"])
    ax3.set_ylabel("ΔIL at 1550 nm (dB), negative = proposed wins")
    ax3.set_title("D  Proposed minus baseline (identical constraints)")

    fig.suptitle(
        "2-D FDTD  ·  220 nm SOI  ·  70 nm etch  ·  150 nm min CD  ·  8° SMF-28  ·  20 periods",
        fontsize=13,
        fontweight="bold",
        color="#1f4e79",
    )
    fig.savefig(FIG / "em00_dashboard.png", bbox_inches="tight")
    plt.close(fig)

    # --- verdict poster ---
    fig = plt.figure(figsize=(12.6, 7.2))
    fig.patch.set_facecolor("white")
    fig.text(
        0.02, 0.94,
        "2-D FDTD verdict  ·  identical 220 nm SOI constraints",
        fontsize=16, fontweight="bold", color="#1f4e79", va="center",
    )
    fig.text(
        0.02, 0.89,
        "20 periods  ·  70 nm shallow etch  ·  150 nm min CD  ·  8° SMF-28  ·  dx = 25 nm with subpixel permittivity",
        fontsize=9, color="#444444", va="center",
    )

    # Metric cards
    rows = [
        ("Design", "IL 1525 nm", "IL 1550.00 nm", "Peak IL", "Under-etch 58 nm", "CD +5 nm"),
    ]
    for key, lab in (
        ("uniform", "Uniform 50%"),
        ("chirp", "Period chirp"),
        ("taillaert", "Taillaert fill"),
        ("proposed", "Proposed"),
    ):
        s = specs[key]
        ce = np.array(s["ce"])
        il1525 = _il_on_grid(wl, ce, 1525.0)
        il1550 = _il_on_grid(wl, ce, 1550.0)
        peak = s["peak_il_db"]
        u58 = _sweep_il(data, "etch", key, 58e-9)
        cd5 = _sweep_il(data, "cd", key, 5e-9)
        rows.append((lab, f"{il1525:.2f}", f"{il1550:.2f}", f"{peak:.2f}", f"{u58:.2f}" if u58==u58 else "—", f"{cd5:.2f}" if cd5==cd5 else "—"))

    ax_t = fig.add_axes([0.03, 0.48, 0.55, 0.36])
    ax_t.axis("off")
    table = ax_t.table(
        cellText=rows[1:],
        colLabels=rows[0],
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.0, 1.7)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#99aacc")
        if r == 0:
            cell.set_facecolor("#e8eef4")
            cell.set_text_props(weight="bold")
        elif r == 4:
            cell.set_facecolor("#d6e4f0")
        else:
            cell.set_facecolor("white")
    ax_t.set_title("")

    # Etch robustness
    ax_e = fig.add_axes([0.62, 0.50, 0.35, 0.34])
    for key, lab in (("uniform", "Uniform"), ("chirp", "Chirp"), ("proposed", "Proposed")):
        if key not in data.get("etch", {}):
            continue
        xs = [r["value"] * 1e9 for r in data["etch"][key]]
        ys = [r["il_1550"] for r in data["etch"][key]]
        ax_e.plot(xs, ys, "-o", color=specs[key]["color"], lw=2.2 if key == "proposed" else 1.6, label=lab)
    ax_e.axvline(70, color="0.5", ls="--", lw=1)
    ax_e.set_xlabel("etch depth (nm)")
    ax_e.set_ylabel("IL at 1550.00 nm (dB)")
    ax_e.set_title("Etch tolerance at 1550.00 nm")
    ax_e.legend(fontsize=8)

    u1550 = _il_on_grid(wl, specs["uniform"]["ce"], 1550.0)
    p1550 = _il_on_grid(wl, specs["proposed"]["ce"], 1550.0)
    c1550 = _il_on_grid(wl, specs["chirp"]["ce"], 1550.0)
    t1550 = _il_on_grid(wl, specs["taillaert"]["ce"], 1550.0)
    u1525 = _il_on_grid(wl, specs["uniform"]["ce"], 1525.0)
    p1525 = _il_on_grid(wl, specs["proposed"]["ce"], 1525.0)
    u58 = _sweep_il(data, "etch", "uniform", 58e-9)
    p58 = _sweep_il(data, "etch", "proposed", 58e-9)
    c58 = _sweep_il(data, "etch", "chirp", 58e-9)
    u82 = _sweep_il(data, "etch", "uniform", 82e-9)
    p82 = _sweep_il(data, "etch", "proposed", 82e-9)
    c82 = _sweep_il(data, "etch", "chirp", 82e-9)
    u_cd = _sweep_il(data, "cd", "uniform", 5e-9)
    p_cd = _sweep_il(data, "cd", "proposed", 5e-9)
    u_spread = max(r["il_1550"] for r in data["etch"]["uniform"]) - min(r["il_1550"] for r in data["etch"]["uniform"])
    p_spread = max(r["il_1550"] for r in data["etch"]["proposed"]) - min(r["il_1550"] for r in data["etch"]["proposed"])
    takeaways = [
        "What improved",
        f"• Blue-side 1525 nm: proposed {p1525:.2f} dB vs uniform {u1525:.2f} dB ({u1525-p1525:.2f} dB).",
        f"• Under-etch 58 nm at 1550.00 nm: proposed {p58:.2f} vs uniform {u58:.2f} vs chirp {c58:.2f}.",
        f"• Etch-spread over ±12 nm: proposed {p_spread:.2f} dB vs uniform {u_spread:.2f} dB.",
        "",
        "What did not",
        f"• Peak IL: uniform {specs['uniform']['peak_il_db']:.2f} dB at {specs['uniform']['wl_peak_nm']:.0f} nm"
        f" vs proposed {specs['proposed']['peak_il_db']:.2f} dB at {specs['proposed']['wl_peak_nm']:.0f} nm.",
        f"• Over-etch 82 nm: uniform {u82:.2f} vs proposed {p82:.2f} vs chirp {c82:.2f}.",
        f"• CD +5 nm: uniform {u_cd:.2f} dB; proposed {p_cd:.2f} dB.",
        f"• Exact 1550.00 nm: uniform {u1550:.2f}, proposed {p1550:.2f}, Taillaert {t1550:.2f}, chirp {c1550:.2f}.",
        "",
        "Verdict: under identical foundry constraints the method does not beat a uniform",
        "PDK-class cell on peak coupling. Combined fill+chirp is a process-tolerance",
        "choice (blue-side IL; under-etch vs uniform). Chirp-only tracks proposed here;",
        "Tidy3D does not give chirp-only the under-etch credit. Cite Tidy3D for ranking.",
    ]
    fig.text(0.03, 0.44, "\n".join(takeaways), fontsize=9.2, va="top", family="DejaVu Sans", color="#222222")
    fig.savefig(FIG / "em07_verdict.png", bbox_inches="tight")
    plt.close(fig)
    print("figures in", FIG)


def main():
    cache = RES / "fdtd_compare.json"
    field_cache = RES / "fdtd_fields.npz"
    data = None
    if cache.exists() and "--rerun" not in sys.argv:
        data = json.loads(cache.read_text(encoding="utf-8"))
        if not _cache_is_current(data):
            print("cache missing exact 1550.00 nm or chirp etch sweep; recomputing")
            data = None
        else:
            print("loading", cache, "(pass --rerun to recompute)")
            fields = {}
            if field_cache.exists():
                z = np.load(field_cache)
                for key in ("uniform", "proposed"):
                    if f"{key}_abs" in z:
                        fields[key] = {
                            "field": z[f"{key}_abs"],
                            "eps": z[f"{key}_eps"],
                            "x": z[f"{key}_x"],
                            "z": z[f"{key}_z"],
                        }
    if data is None:
        data, fields = run_campaign()
    make_figures(data, fields)
    print("\n=== IL at 1550.00 nm (dB), on-grid ===")
    for k, s in data["spectra"].items():
        lam = s.get("lambda_ce_nm", s.get("lambda_nm", "?"))
        print(
            f"  {s['name']:48s}  {-10*np.log10(max(s['ce_1550'],1e-16)):6.2f}  "
            f"λ={lam} nm  peak {s['peak_il_db']:.2f} @ {s['wl_peak_nm']:.0f} nm  "
            f"BW {s['bw_1db_nm']:.1f} nm"
        )


if __name__ == "__main__":
    main()
