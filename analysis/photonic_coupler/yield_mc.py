"""Process Monte Carlo for insertion loss, with first-order Sobol indices.

The insertion-loss model at the *design* wavelength is

    IL = IL_peak(etch, t_si) + IL_detune(delta_lambda) + IL_align(offset, theta)

Peak CE uses the leaky-wave model evaluated at the perturbed geometry.
Wavelength walk uses the published Chrostowski sensitivities, which are
FDTD-derived and more accurate than differentiating the 1-D slab model
alone (the grating radiation angle is more etch-sensitive than n_eff).

Yield is the empirical fraction of draws with IL <= IL_spec. Confidence
intervals are Clopper-Pearson, computed in stats_design.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .constants import D_LAMBDA_NM, PROCESS_SIGMA, Platform, SOI220, UM
from .grating import (
    bloch_neff,
    box_directionality,
    bragg_reflection,
    db,
    min_max_fill,
    overlap_apodized,
    phase_match_period,
    radiation_alpha,
)
from .slab import te_fundamental
from .thermal import detune_il_db, gaussian_fwhm_from_1db


@dataclass
class ProcessModel:
    t_si_nm: float = 2.0
    etch_nm: float = 3.0
    cd_nm: float = 2.6
    theta_deg: float = 0.4
    offset_um: float = 0.8


DEFAULT_PROCESS = ProcessModel(
    t_si_nm=PROCESS_SIGMA["t_si_nm"],
    etch_nm=PROCESS_SIGMA["etch_nm"],
    cd_nm=PROCESS_SIGMA["cd_nm"],
    theta_deg=PROCESS_SIGMA["theta_deg"],
    offset_um=PROCESS_SIGMA["offset_um"],
)


def _peak_eta(
    t_si: float,
    etch: float,
    fill: float,
    theta_deg: float,
    platform: Platform,
    length: float,
    ff_start: float,
    ff_end: float,
    z0: float,
    eta_2d: float = 0.87,
) -> float:
    remaining = max(80e-9, t_si - etch)
    t_si = max(t_si, remaining + 20e-9)
    try:
        un = te_fundamental(t_si, platform.wavelength, platform.core.n, platform.cladding.n)
        et = te_fundamental(remaining, platform.wavelength, platform.core.n, platform.cladding.n)
    except Exception:
        return 1e-4
    n_eff = bloch_neff(fill, un.n_eff, et.n_eff)
    D = box_directionality(
        platform.t_box, platform.wavelength, platform.box.n, platform.core.n, theta_deg
    )
    R = bragg_reflection(theta_deg)
    w0 = platform.mfd / 2.0
    ov = overlap_apodized(length, ff_start, ff_end, etch, t_si, z0, w0)
    eta = D * ov * (1.0 - R) * 0.98 * eta_2d
    return float(max(eta, 1e-6))


def sample_il(
    n: int,
    platform: Platform,
    length: float,
    fill: float,
    ff_start: float,
    ff_end: float,
    z0: float,
    n_eff_nom: float,
    bw1db_nm: float,
    eta_2d: float = 0.87,
    process: ProcessModel = DEFAULT_PROCESS,
    rng: np.random.Generator | None = None,
) -> dict[str, np.ndarray]:
    rng = rng or np.random.default_rng(0)
    t_si = platform.t_si + rng.normal(0.0, process.t_si_nm * 1e-9, n)
    etch = platform.t_etch + rng.normal(0.0, process.etch_nm * 1e-9, n)
    cd = rng.normal(0.0, process.cd_nm, n)  # nm
    theta = platform.theta_deg + rng.normal(0.0, process.theta_deg, n)
    offset = z0 + rng.normal(0.0, process.offset_um * UM, n)

    fwhm = gaussian_fwhm_from_1db(bw1db_nm)
    # Wavelength walk from published d lambda / d geometry.
    dlam = (
        D_LAMBDA_NM["per_nm_tsi"] * (t_si - platform.t_si) / 1e-9
        + D_LAMBDA_NM["per_nm_etch"] * (etch - platform.t_etch) / 1e-9
        + D_LAMBDA_NM["per_nm_cd"] * cd
    )
    il_detune = np.array([detune_il_db(float(x), fwhm) for x in dlam])

    il_peak = np.empty(n)
    for i in range(n):
        eta = _peak_eta(
            float(t_si[i]),
            float(etch[i]),
            fill,
            float(theta[i]),
            platform,
            length,
            ff_start,
            ff_end,
            float(offset[i]),
            eta_2d,
        )
        il_peak[i] = db(eta)

    # Alignment extra: fiber offset already in overlap; add a small
    # angular mismatch as extra detune-like loss ~ 0.15 dB/deg^2 around 8 deg
    # (typical GC angular 1 dB half-width ~ 2 deg).
    dtheta = theta - platform.theta_deg
    il_angle = 0.15 * dtheta**2

    il = il_peak + il_detune + il_angle
    return {
        "il_db": il,
        "il_peak_db": il_peak,
        "il_detune_db": il_detune,
        "il_angle_db": il_angle,
        "dlambda_nm": dlam,
        "t_si_nm": t_si / 1e-9,
        "etch_nm": etch / 1e-9,
        "cd_nm": cd,
        "theta_deg": theta,
        "offset_um": offset / UM,
    }


def monte_carlo_il(
    n: int = 4000,
    platform: Platform = SOI220,
    design=None,
    process: ProcessModel = DEFAULT_PROCESS,
    specs: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5),
    seed: int = 0,
) -> dict:
    from .grating import bandwidth_1db_nm, leaky_wave_coupling

    if design is None:
        design = leaky_wave_coupling(platform)
    bw = bandwidth_1db_nm(
        design.n_eff, design.n_g, platform.cladding.n, platform.theta_deg, platform.wavelength
    )
    rng = np.random.default_rng(seed)
    samples = sample_il(
        n,
        platform,
        design.length,
        design.fill,
        design.ff_start,
        design.ff_end,
        design.z0_apodized,
        design.n_eff,
        bw,
        getattr(design, "eta_2d", 0.87),
        process,
        rng,
    )
    il = samples["il_db"]
    yields = {f"y_le_{s:.1f}dB": float(np.mean(il <= s)) for s in specs}
    return {
        "n": n,
        "mean_il_db": float(np.mean(il)),
        "median_il_db": float(np.median(il)),
        "std_il_db": float(np.std(il, ddof=1)),
        "p05_il_db": float(np.percentile(il, 5)),
        "p95_il_db": float(np.percentile(il, 95)),
        "nominal_apodized_il_db": design.il_apodized_db,
        "bw1db_nm": bw,
        "yields": yields,
        "samples": samples,
        "specs": list(specs),
    }


def sobol_first_order(
    n_base: int = 1024,
    platform: Platform = SOI220,
    design=None,
    process: ProcessModel = DEFAULT_PROCESS,
    seed: int = 1,
) -> dict[str, float]:
    """Pick-freeze first-order Sobol indices for IL.

    Factors: t_si, etch, cd, theta, offset. Saltelli estimator
    S_i = mean( y_A * (y_{C_i} - y_B) ) / var(y)  (Saltelli 2010).
    """
    from .grating import bandwidth_1db_nm, leaky_wave_coupling

    if design is None:
        design = leaky_wave_coupling(platform)
    bw = bandwidth_1db_nm(
        design.n_eff, design.n_g, platform.cladding.n, platform.theta_deg, platform.wavelength
    )
    rng = np.random.default_rng(seed)
    names = ["t_si", "etch", "cd", "theta", "offset"]

    def draw_matrix(rng):
        return {
            "t_si": platform.t_si + rng.normal(0.0, process.t_si_nm * 1e-9, n_base),
            "etch": platform.t_etch + rng.normal(0.0, process.etch_nm * 1e-9, n_base),
            "cd": rng.normal(0.0, process.cd_nm, n_base),
            "theta": platform.theta_deg + rng.normal(0.0, process.theta_deg, n_base),
            "offset": design.z0_apodized + rng.normal(0.0, process.offset_um * UM, n_base),
        }

    A = draw_matrix(rng)
    B = draw_matrix(rng)

    def il_from(m):
        fwhm = gaussian_fwhm_from_1db(bw)
        dlam = (
            D_LAMBDA_NM["per_nm_tsi"] * (m["t_si"] - platform.t_si) / 1e-9
            + D_LAMBDA_NM["per_nm_etch"] * (m["etch"] - platform.t_etch) / 1e-9
            + D_LAMBDA_NM["per_nm_cd"] * m["cd"]
        )
        il = np.empty(n_base)
        for i in range(n_base):
            eta = _peak_eta(
                float(m["t_si"][i]),
                float(m["etch"][i]),
                design.fill,
                float(m["theta"][i]),
                platform,
                design.length,
                design.ff_start,
                design.ff_end,
                float(m["offset"][i]),
                getattr(design, "eta_2d", 0.87),
            )
            il[i] = db(eta) + detune_il_db(float(dlam[i]), fwhm) + 0.15 * (
                m["theta"][i] - platform.theta_deg
            ) ** 2
        return il

    yA = il_from(A)
    yB = il_from(B)
    var = float(np.var(np.concatenate([yA, yB]), ddof=1))
    out = {}
    stot = {}
    for name in names:
        # A_B^{(i)}: all columns from A except i, which is taken from B.
        C = {k: A[k].copy() for k in names}
        C[name] = B[name]
        yC = il_from(C)
        # Jansen (1999): first-order and total-order, both in [0, 1] in expectation.
        si = 1.0 - 0.5 * float(np.mean((yB - yC) ** 2)) / var
        sti = 0.5 * float(np.mean((yA - yC) ** 2)) / var
        out[name] = float(np.clip(si, 0.0, 1.0))
        stot[name] = float(np.clip(sti, 0.0, 1.5))
    s_sum = sum(out.values())
    out["sum_first_order"] = s_sum
    out["interactions_residual"] = max(0.0, 1.0 - s_sum)
    out["total_order"] = stot
    return out
