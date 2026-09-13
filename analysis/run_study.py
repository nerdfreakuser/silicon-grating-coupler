"""Run the full analytic study and write results + figures.

Usage (from the analysis/ directory or the photonic/ root):

    python analysis/run_study.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from photonic_coupler.constants import PROCESS_SIGMA, SOI220  # noqa: E402
from photonic_coupler.energy import module_energy_delta  # noqa: E402
from photonic_coupler.figures import (  # noqa: E402
    fig_directionality,
    fig_energy,
    fig_focusing,
    fig_overlap,
    fig_pareto,
    fig_period_map,
    fig_sample_size,
    fig_slab_neff,
    fig_sobol,
    fig_sota,
    fig_thermal,
    fig_yield_curve,
    fig_yield_hist,
)
from photonic_coupler.grating import bandwidth_1db_nm, leaky_wave_coupling  # noqa: E402
from photonic_coupler.optimize import optimize_apodization  # noqa: E402
from photonic_coupler.slab import grating_section_indices  # noqa: E402
from photonic_coupler.stats_design import (  # noqa: E402
    clopper_pearson,
    paired_t_n,
    two_proportion_n,
    two_sample_t_n,
)
from photonic_coupler.thermal import thermal_shift  # noqa: E402
from photonic_coupler.yield_mc import monte_carlo_il, sobol_first_order  # noqa: E402


def _jsonable(obj):
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items() if k != "samples"}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(x) for x in obj]
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def main() -> None:
    figdir = ROOT / "analysis" / "figures"
    resdir = ROOT / "analysis" / "results"
    figdir.mkdir(parents=True, exist_ok=True)
    resdir.mkdir(parents=True, exist_ok=True)

    unetched, etched = grating_section_indices(SOI220)
    design = leaky_wave_coupling(SOI220)
    therm = thermal_shift(design)
    print("=== slab ===")
    print(f"  unetched n_eff={unetched.n_eff:.4f}  n_g={unetched.n_g:.4f}  Gamma={unetched.confinement_si:.3f}")
    print(f"  etched   n_eff={etched.n_eff:.4f}  n_g={etched.n_g:.4f}  Gamma={etched.confinement_si:.3f}")
    print("=== grating ===")
    for k, v in design.as_dict().items():
        if isinstance(v, float):
            print(f"  {k:24s} {v:.6f}")
        else:
            print(f"  {k:24s} {v}")
    bw = bandwidth_1db_nm(
        design.n_eff, design.n_g, SOI220.cladding.n, SOI220.theta_deg, SOI220.wavelength
    )
    print(f"  bw1db_nm                 {bw:.2f}")
    print("=== thermal ===")
    print(f"  dlambda/dT = {therm.dlambda_dT_nm_per_K:.4f} nm/K")
    print(f"  extra IL at +1 K  = {therm.extra_il_per_K_linearized_db:.4f} dB")
    print(f"  extra IL at +20 K = {therm.extra_il_20K_db:.4f} dB")
    print(f"  1 dB BW = {therm.bw1db_nm:.2f} nm, FWHM = {therm.fwhm_nm:.2f} nm")

    print("=== Monte Carlo ===")
    mc = monte_carlo_il(n=2500, seed=0)
    print(f"  mean {mc['mean_il_db']:.3f}  median {mc['median_il_db']:.3f}  std {mc['std_il_db']:.3f}")
    print(f"  p05 {mc['p05_il_db']:.3f}  p95 {mc['p95_il_db']:.3f}")
    for k, v in mc["yields"].items():
        print(f"  {k}: {100*v:.2f}%")

    print("=== Sobol (this takes a bit) ===")
    sob = sobol_first_order(n_base=384, seed=1)
    for k, v in sob.items():
        if isinstance(v, dict):
            print(f"  {k}: {v}")
        else:
            print(f"  {k:24s} {v:.3f}")

    print("=== apodization CVaR opt ===")
    opt = optimize_apodization(n_mc=180, seed=2)
    for k, v in opt.items():
        print(f"  {k}: {v}")

    print("=== energy ===")
    e_pdk_to_model = module_energy_delta(SOI220.pdk_il_db, design.il_apodized_db, n_couplers=2)
    e_pdk_to_half = module_energy_delta(SOI220.pdk_il_db, 0.5, n_couplers=2)
    e_3_to_03 = module_energy_delta(3.0, 0.3, n_couplers=2)
    print("  PDK 2.8 -> model apodized:", e_pdk_to_model)
    print("  PDK 2.8 -> 0.5 dB:", e_pdk_to_half)
    print("  3.0 -> 0.3 dB (draft claim setup):", e_3_to_03)

    print("=== stats ===")
    n_prop = two_proportion_n(0.50, 0.70)
    n_t = two_sample_t_n(0.30, 0.30)
    n_pair = paired_t_n(0.30, 0.20)
    n_prop_90 = two_proportion_n(0.70, 0.90)
    # Clopper-Pearson on MC yield at 2.5 dB
    k = int(round(mc["yields"]["y_le_2.5dB"] * mc["n"]))
    lo, hi = clopper_pearson(k, mc["n"])
    stats = {
        "n_per_arm_yield_50_vs_70": n_prop,
        "n_per_arm_mean_il_0p3dB_sigma_0p3": n_t,
        "n_paired_0p3dB_sigma_diff_0p2": n_pair,
        "n_per_arm_yield_70_vs_90": n_prop_90,
        "mc_yield_2p5dB_clopper_pearson": {"k": k, "n": mc["n"], "lo": lo, "hi": hi},
        "wrong_draft_n_wafers": 50,
    }
    print(stats)

    payload = {
        "platform": "SOI-220, 70 nm shallow etch, 2 um BOX, oxide clad, 8 deg, SMF-28",
        "slab": {
            "unetched": {
                "n_eff": unetched.n_eff,
                "n_g": unetched.n_g,
                "Gamma": unetched.confinement_si,
            },
            "etched": {
                "n_eff": etched.n_eff,
                "n_g": etched.n_g,
                "Gamma": etched.confinement_si,
            },
        },
        "design": design.as_dict(),
        "thermal": {
            "dlambda_dT_nm_per_K": therm.dlambda_dT_nm_per_K,
            "dn_eff_dT": therm.dn_eff_dT,
            "n_g": therm.n_g,
            "bw1db_nm": therm.bw1db_nm,
            "fwhm_nm": therm.fwhm_nm,
            "extra_il_1K_db": therm.extra_il_per_K_linearized_db,
            "extra_il_20K_db": therm.extra_il_20K_db,
        },
        "monte_carlo": _jsonable(mc),
        "sobol": sob,
        "optimize": opt,
        "energy": {
            "pdk_to_model": e_pdk_to_model.__dict__,
            "pdk_to_0p5dB": e_pdk_to_half.__dict__,
            "from3p0_to_0p3": e_3_to_03.__dict__,
        },
        "stats": stats,
        "process_sigma": PROCESS_SIGMA,
        # Bozzola 2015 published 2-D FDTD ceiling. Citation, not a model clamp.
        "physics_cap_db": float(-10 * np.log10(SOI220.ce_physics_cap)),
        "literature_220nm_ceiling_db": float(-10 * np.log10(SOI220.ce_physics_cap)),
        "pdk_il_db": SOI220.pdk_il_db,
    }
    out_json = resdir / "study.json"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("wrote", out_json)

    print("=== figures ===")
    fig_slab_neff(figdir / "fig01_slab_neff.png")
    fig_period_map(figdir / "fig02_period.png", design)
    fig_overlap(figdir / "fig03_overlap.png", design)
    fig_directionality(figdir / "fig04_directionality.png")
    fig_thermal(figdir / "fig05_thermal.png", design, therm)
    fig_yield_hist(figdir / "fig06_yield_hist.png", mc)
    fig_yield_curve(figdir / "fig07_yield_curve.png", mc)
    fig_sobol(figdir / "fig08_sobol.png", sob)
    fig_energy(figdir / "fig09_energy.png")
    fig_sample_size(figdir / "fig10_sample_size.png")
    fig_sota(figdir / "fig11_sota.png")
    fig_focusing(figdir / "fig12_focusing.png", design)
    fig_pareto(figdir / "fig13_cdf.png", mc)
    print("figures in", figdir)


if __name__ == "__main__":
    main()
