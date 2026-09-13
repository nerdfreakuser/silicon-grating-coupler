"""Chance-constrained design on the leaky-wave surrogate.

The Maxwell inverse-design problem is non-convex. What *can* be solved
here is the reduced problem in the apodization parameters

    x = (ff_start, ff_end, length)

subject to DRC (min CD) and a sample-average yield constraint

    (1/N) sum 1[ IL(x, p_k) <= IL_spec ]  >= Y_spec

or, more stably, a CVaR penalty on the upper tail of IL. We minimise
expected IL plus a penalty on CVaR_{0.9}(IL). This is the correct
replacement for the original scalarization

    f = w1 L - w2 Y + w3 T + w4 P

which added incommensurate units and treated PDK rules as a soft term.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize

from .constants import Platform, SOI220
from .grating import db, min_max_fill, overlap_apodized
from .yield_mc import DEFAULT_PROCESS, ProcessModel, sample_il


def cvar(samples: np.ndarray, alpha: float = 0.90) -> float:
    """Conditional value-at-risk (upper tail): mean of the worst (1-alpha)."""
    s = np.sort(samples)
    k = max(1, int(np.ceil((1.0 - alpha) * len(s))))
    return float(np.mean(s[-k:]))


def design_objective(
    x: np.ndarray,
    platform: Platform,
    period: float,
    fill: float,
    n_eff: float,
    bw1db_nm: float,
    process: ProcessModel,
    rng: np.random.Generator,
    n_mc: int = 400,
    il_spec: float = 2.5,
    cvar_weight: float = 0.35,
) -> float:
    ff_start, ff_end, length_um = x
    length = length_um * 1e-6
    lo, hi = min_max_fill(period, platform.min_cd)
    if not (lo <= ff_start <= hi and lo <= ff_end <= hi):
        return 50.0
    if length < 8e-6 or length > 40e-6:
        return 50.0
    w0 = platform.mfd / 2.0
    # Nominal overlap at z0 = length/3 (typical).
    z0 = 0.35 * length
    ov = overlap_apodized(length, ff_start, ff_end, platform.t_etch, platform.t_si, z0, w0)
    from .grating import box_directionality, bragg_reflection

    D = box_directionality(
        platform.t_box,
        platform.wavelength,
        platform.box.n,
        platform.core.n,
        platform.theta_deg,
    )
    R = bragg_reflection(platform.theta_deg)
    eta = D * ov * (1.0 - R) * 0.98 * 0.87
    il_nom = db(eta)
    mc = sample_il(
        n_mc,
        platform,
        length,
        fill,
        ff_start,
        ff_end,
        z0,
        n_eff,
        bw1db_nm,
        process=process,
        rng=rng,
    )
    il = mc["il_db"]
    return float(il_nom + 0.25 * np.mean(il) + cvar_weight * cvar(il, 0.90))


def optimize_apodization(
    platform: Platform = SOI220,
    n_mc: int = 300,
    seed: int = 2,
) -> dict:
    from .grating import bandwidth_1db_nm, leaky_wave_coupling

    d0 = leaky_wave_coupling(platform)
    bw = bandwidth_1db_nm(
        d0.n_eff, d0.n_g, platform.cladding.n, platform.theta_deg, platform.wavelength
    )
    lo, hi = d0.ff_min, d0.ff_max
    x0 = np.array([d0.ff_start, d0.ff_end, d0.length / 1e-6])
    bounds = [(lo, hi), (lo, hi), (10.0, 30.0)]
    rng = np.random.default_rng(seed)

    def fun(x):
        return design_objective(
            x,
            platform,
            d0.period,
            d0.fill,
            d0.n_eff,
            bw,
            DEFAULT_PROCESS,
            rng,
            n_mc=n_mc,
        )

    res = minimize(fun, x0, method="Nelder-Mead", bounds=bounds, options={"maxiter": 25, "xatol": 2e-3, "fatol": 1e-3})
    x = res.x
    # Evaluate a larger MC at the optimum.
    from .yield_mc import sample_il

    length = x[1] and x[2] * 1e-6
    ff_start, ff_end, length_um = x
    length = length_um * 1e-6
    z0 = 0.35 * length
    big = sample_il(
        2000,
        platform,
        length,
        d0.fill,
        ff_start,
        ff_end,
        z0,
        d0.n_eff,
        bw,
        eta_2d=getattr(d0, "eta_2d", 0.87),
        process=DEFAULT_PROCESS,
        rng=np.random.default_rng(seed + 7),
    )
    il = big["il_db"]
    return {
        "ff_start": float(ff_start),
        "ff_end": float(ff_end),
        "length_um": float(length_um),
        "success": bool(res.success),
        "fun": float(res.fun),
        "mean_il_db": float(np.mean(il)),
        "cvar90_il_db": cvar(il, 0.90),
        "yield_2p5dB": float(np.mean(il <= 2.5)),
        "yield_2p0dB": float(np.mean(il <= 2.0)),
        "yield_1p5dB": float(np.mean(il <= 1.5)),
        "yield_0p5dB": float(np.mean(il <= 0.5)),
        "x0": x0.tolist(),
    }
