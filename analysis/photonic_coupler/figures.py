"""Publication figures. All numbers come from the models, not from the LLM draft."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .constants import NM, SI, SIO2, SOI220, UM
from .grating import (
    bloch_neff,
    box_directionality,
    focusing_grating_curves,
    leaky_wave_coupling,
    min_max_fill,
    overlap_apodized,
    overlap_uniform,
    phase_match_period,
    radiation_alpha,
)
from .slab import te_fundamental
from .thermal import detune_il_db, thermal_shift

plt.rcParams.update(
    {
        "figure.dpi": 140,
        "savefig.dpi": 200,
        "font.size": 10,
        "axes.labelsize": 11,
        "axes.titlesize": 11,
        "legend.fontsize": 8.5,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.grid": True,
        "grid.alpha": 0.25,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def _save(fig, out: Path):
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def fig_slab_neff(out: Path):
    p = SOI220
    ds = np.linspace(80e-9, 340e-9, 80)
    ne, ng, g, ds_ok = [], [], [], []
    for d in ds:
        try:
            m = te_fundamental(d, p.wavelength, p.core.n, p.cladding.n)
        except Exception:
            continue
        ds_ok.append(d)
        ne.append(m.n_eff)
        ng.append(m.n_g)
        g.append(m.confinement_si)
    ds = np.asarray(ds_ok)
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.plot(ds / NM, ne, label=r"$n_{\mathrm{eff}}$", color="#1f4e79")
    ax.plot(ds / NM, ng, label=r"$n_g$", color="#c45911")
    ax.axvline(220, color="0.4", ls="--", lw=1, label="220 nm device")
    ax.axvline(150, color="0.5", ls=":", lw=1, label="150 nm after 70 nm etch")
    ax.set_xlabel("Si thickness (nm)")
    ax.set_ylabel("index")
    ax.legend()
    ax.set_title("TE slab modes, oxide-clad, 1550 nm")
    _save(fig, out)


def fig_period_map(out: Path, design):
    p = SOI220
    ffs = np.linspace(design.ff_min, design.ff_max, 60)
    thetas = np.array([6, 8, 10, 12])
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    for th in thetas:
        pers = []
        for ff in ffs:
            ne = bloch_neff(ff, design.n_unetch, design.n_etch)
            pers.append(phase_match_period(ne, p.wavelength, p.cladding.n, th) / NM)
        ax.plot(ffs, pers, label=rf"$\theta={th:.0f}^\circ$")
    ax.axhline(design.period / NM, color="0.3", ls="--", lw=1)
    ax.scatter([design.fill], [design.period / NM], zorder=5, color="black")
    ax.set_xlabel("fill factor (unetched fraction)")
    ax.set_ylabel("period (nm)")
    ax.legend(title="fiber angle in cladding")
    ax.set_title("Phase-match period, first diffraction order")
    _save(fig, out)


def fig_overlap(out: Path, design):
    p = SOI220
    w0 = p.mfd / 2.0
    length = design.length
    z = np.linspace(0, length, 800)
    alphas = np.linspace(0.04e6, 0.25e6, 40)
    ov = [overlap_uniform(a, length, 0.35 * length, w0) for a in alphas]
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.5))
    axes[0].plot(alphas * UM, ov, color="#1f4e79")
    axes[0].axvline(design.alpha * UM, color="0.3", ls="--")
    axes[0].set_xlabel(r"$\alpha$ (1/µm)")
    axes[0].set_ylabel("fiber overlap")
    axes[0].set_title("Uniform grating vs leakage")
    # Radiated profiles
    A_u = np.sqrt(2 * design.alpha) * np.exp(-design.alpha * z)
    A_u = A_u / np.max(A_u)
    ff = np.linspace(design.ff_start, design.ff_end, len(z))
    from .grating import apodized_radiated_field

    A_a = apodized_radiated_field(z, ff, p.t_etch, p.t_si)
    A_a = A_a / (np.max(A_a) + 1e-15)
    fiber = np.exp(-((z - design.z0_apodized) ** 2) / w0**2)
    axes[1].plot(z / UM, A_u, label="uniform radiated", color="#1f4e79")
    axes[1].plot(z / UM, A_a, label="apodized radiated", color="#c45911")
    axes[1].plot(z / UM, fiber, label="SMF-28 field", color="0.35", ls="--")
    axes[1].set_xlabel("z (µm)")
    axes[1].set_ylabel("normalized |E|")
    axes[1].legend()
    axes[1].set_title("Near-field match to the fiber")
    _save(fig, out)


def fig_directionality(out: Path):
    p = SOI220
    tbox = np.linspace(1.0e-6, 3.0e-6, 250)
    D = [
        box_directionality(t, p.wavelength, p.box.n, p.core.n, p.theta_deg) for t in tbox
    ]
    fig, ax = plt.subplots(figsize=(6.2, 3.5))
    ax.plot(tbox / UM, D, color="#1f4e79")
    ax.axvline(2.0, color="0.3", ls="--", label="2 µm BOX")
    ax.set_xlabel("BOX thickness (µm)")
    ax.set_ylabel("upward directionality")
    ax.set_ylim(0.2, 1.0)
    ax.legend()
    ax.set_title("Handle-reflection interference (two-beam model)")
    _save(fig, out)


def fig_thermal(out: Path, design, therm):
    Ts = np.linspace(-20, 40, 121)
    extra = [detune_il_db(therm.dlambda_dT_nm_per_K * T, therm.fwhm_nm) for T in Ts]
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.plot(Ts, extra, color="#1f4e79", label="this model (fixed laser wavelength)")
    ax.axhline(0.01 * 20, color="#c45911", ls="--", label="LLM draft: 0.01 dB/°C × 20°C")
    ax.axhline(0.01, color="#c45911", ls=":", label="LLM draft: 0.01 dB/°C (1 K)")
    ax.set_xlabel(r"$\Delta T$ (K) from 300 K")
    ax.set_ylabel("extra IL at 1550 nm (dB)")
    ax.legend()
    ax.set_title(
        rf"$d\lambda/dT$ = {therm.dlambda_dT_nm_per_K:.3f} nm/K,  "
        rf"1 dB BW = {therm.bw1db_nm:.1f} nm"
    )
    _save(fig, out)


def fig_yield_hist(out: Path, mc: dict):
    il = mc["samples"]["il_db"]
    fig, ax = plt.subplots(figsize=(6.4, 3.7))
    ax.hist(il, bins=40, color="#1f4e79", alpha=0.85, edgecolor="white", density=True)
    ax.axvline(mc["nominal_apodized_il_db"], color="black", ls="--", label="nominal apodized")
    ax.axvline(SOI220.pdk_il_db, color="#c45911", ls="--", label="AIM PDK TE GC (~2.8 dB)")
    ax.axvline(0.5, color="0.4", ls=":", label="LLM target 0.5 dB")
    ax.axvline(1.87, color="0.5", ls="-.", label="220 nm physics floor (~1.9 dB)")
    ax.set_xlabel("insertion loss at 1550 nm (dB)")
    ax.set_ylabel("density")
    ax.legend(loc="upper right")
    ax.set_title(
        f"Process Monte Carlo, n={mc['n']},  "
        f"mean {mc['mean_il_db']:.2f} dB,  σ {mc['std_il_db']:.2f} dB"
    )
    _save(fig, out)


def fig_yield_curve(out: Path, mc: dict):
    specs = np.linspace(0.3, 4.0, 80)
    il = mc["samples"]["il_db"]
    y = [float(np.mean(il <= s)) for s in specs]
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.plot(specs, np.array(y) * 100, color="#1f4e79")
    ax.axhline(70, color="0.4", ls="--", label="70% yield")
    ax.axvline(0.5, color="#c45911", ls=":", label="0.5 dB spec")
    ax.axvline(2.5, color="0.3", ls="--", label="2.5 dB spec (this work)")
    ax.set_xlabel("IL specification (dB)")
    ax.set_ylabel("yield (%)")
    ax.set_ylim(-2, 105)
    ax.legend()
    ax.set_title("Yield vs specification, 220 nm SOI, no back-reflector")
    _save(fig, out)


def fig_sobol(out: Path, sob: dict):
    keys = ["t_si", "etch", "cd", "theta", "offset"]
    labels = [
        r"$t_{\mathrm{Si}}$",
        "etch depth",
        "CD bias",
        r"fiber $\theta$",
        "fiber offset",
    ]
    vals = [sob[k] for k in keys]
    fig, ax = plt.subplots(figsize=(6.2, 3.5))
    ax.bar(labels, vals, color="#1f4e79")
    ax.set_ylabel("first-order Sobol index")
    ax.set_title("Which process errors move insertion loss")
    _save(fig, out)


def fig_energy(out: Path):
    from .energy import module_energy_delta

    ils = np.linspace(0.3, 3.5, 40)
    frac2 = [module_energy_delta(3.0, x, n_couplers=2).module_fraction_saved * 100 for x in ils]
    frac4 = [module_energy_delta(3.0, x, n_couplers=4).module_fraction_saved * 100 for x in ils]
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.plot(ils, frac2, label="2 couplers in path (TX+RX PIC)", color="#1f4e79")
    ax.plot(ils, frac4, label="4 couplers (naive PIC loopback)", color="#c45911")
    ax.axhline(70, color="0.4", ls="--", label="LLM draft: 70% module energy")
    ax.set_xlabel("improved coupler IL (dB), from a 3.0 dB starting point")
    ax.set_ylabel("% of 15 pJ/bit module energy saved")
    ax.set_ylim(-2, 80)
    ax.legend()
    ax.set_title("Laser-share model (25% of module is laser electrical)")
    _save(fig, out)


def fig_sample_size(out: Path):
    from .stats_design import two_proportion_n, two_sample_t_n

    p2 = np.linspace(0.55, 0.90, 20)
    n_y = [two_proportion_n(0.50, p) for p in p2]
    deltas = np.linspace(0.10, 0.60, 20)
    n_t = [two_sample_t_n(d, 0.30) for d in deltas]
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.5))
    axes[0].plot(p2 * 100, n_y, color="#1f4e79")
    axes[0].axhline(50, color="#c45911", ls="--", label="LLM: 50 wafers")
    axes[0].set_xlabel("alternative yield (%) vs H0=50%")
    axes[0].set_ylabel("devices per arm")
    axes[0].set_title("Two-proportion test, 80% power")
    axes[0].legend()
    axes[1].plot(deltas, n_t, color="#1f4e79")
    axes[1].set_xlabel("mean IL difference (dB), σ = 0.30 dB")
    axes[1].set_ylabel("devices per arm")
    axes[1].set_title("Two-sample t-test, 80% power")
    _save(fig, out)


def fig_sota(out: Path):
    d = leaky_wave_coupling()
    rows = [
        ("Wang UGR 2024 (meas., no mirror)", 0.34, False, False),
        ("Huang inverse+mirror (sim.)", 0.35, True, True),
        ("Bozzola 340 nm SOI (sim.)", 0.50, True, False),
        ("Benedikovic SWG+mirror (meas.)", 0.69, False, True),
        ("Valdez TWIG 2025 (meas.)", 0.69, False, False),
        ("Bozzola 220 nm apodized (sim.)", 1.90, True, False),
        ("this model, apodized 220 nm", d.il_apodized_db, True, False),
        ("AIM PDK TE GC (meas.)", 2.80, False, False),
    ]
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    y = np.arange(len(rows))
    colors = ["#c45911" if mir else "#1f4e79" for _, _, _, mir in rows]
    ax.barh(y, [r[1] for r in rows], color=colors, height=0.65)
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows])
    ax.axvline(0.5, color="0.5", ls=":", lw=1)
    ax.set_xlabel("insertion loss (dB), lower is better")
    ax.set_title("Selected coupler results (orange = back-reflector)")
    ax.invert_yaxis()
    _save(fig, out)


def fig_focusing(out: Path, design):
    curves = focusing_grating_curves(
        design.n_eff, SOI220.wavelength, SOI220.cladding.n, SOI220.theta_deg
    )
    fig, ax = plt.subplots(figsize=(5.6, 4.2))
    for pts in curves:
        ax.plot(pts[:, 0] / UM, pts[:, 1] / UM, color="#1f4e79", lw=0.8)
    ax.set_aspect("equal")
    ax.set_xlabel("x (µm)")
    ax.set_ylabel("y (µm)")
    ax.set_title("Focusing grating (confocal construction)")
    _save(fig, out)


def fig_pareto(out: Path, mc: dict):
    """Nominal vs yield is a single design; show IL spec Pareto from the MC tail."""
    il = np.sort(mc["samples"]["il_db"])
    y = np.arange(1, len(il) + 1) / len(il)
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.plot(il, y * 100, color="#1f4e79")
    ax.set_xlabel("IL (dB)")
    ax.set_ylabel("cumulative yield at that IL (%)")
    ax.set_title("Empirical CDF: the yield–loss Pareto of this process")
    _save(fig, out)
