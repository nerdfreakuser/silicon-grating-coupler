"""Thermo-optic shift of a grating coupler at fixed fiber angle.

Phase match: n_eff(lambda, T) - n_c sin theta = lambda / Lambda.

Differentiating at fixed theta and Lambda (thermal expansion of Lambda is
kept, it is a ~1% correction):

    d lambda / dT = lambda * (dn_eff/dT + n_eff * alpha_th)
                    / (n_g - n_c sin theta)

because n_g = n_eff - lambda dn_eff/dlambda, and
dn_eff/dT = Gamma_si * dn_si/dT + (1 - Gamma_si) * dn_ox/dT.

A Gaussian-like coupling spectrum of 1 dB full-width Delta then gives an
extra insertion loss at the *design* wavelength of

    Delta IL(dB) = (40 log10(e) ln 2) * (delta_lambda / FWHM)^2
                 = 12.041 * (delta_lambda / FWHM)^2

with FWHM = Delta_1dB / sqrt(log2(10^{0.1})) wait — derived in the
function body from eta/eta0 = 10^{-0.1} on a Gaussian in wavelength.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .constants import NM, Platform, SI, SIO2, SOI220
from .grating import GratingDesign, leaky_wave_coupling


@dataclass(frozen=True)
class ThermalResult:
    dlambda_dT_nm_per_K: float
    dn_eff_dT: float
    n_g: float
    fwhm_nm: float
    bw1db_nm: float
    extra_il_per_K_db: float  # small-signal quadratic coefficient at T0, per K^2 actually
    extra_il_20K_db: float
    extra_il_per_K_linearized_db: float  # extra IL at +1 K
    claimed_001_db_per_C: float  # linear 0.01 dB/°C, for comparison


def gaussian_fwhm_from_1db(bw1db_nm: float) -> float:
    """eta = eta0 exp(-4 ln 2 (dl/FWHM)^2). At |dl| = bw1db/2, eta/eta0 = 10^{-0.1}."""
    # 4 ln 2 * (bw1db/2 / FWHM)^2 = -ln(10^{-0.1}) = 0.1 ln 10
    # ln 2 * (bw1db / FWHM)^2 = 0.1 ln 10
    # (bw1db / FWHM)^2 = 0.1 ln 10 / ln 2
    ratio_sq = 0.1 * np.log(10.0) / np.log(2.0)
    return float(bw1db_nm / np.sqrt(ratio_sq))


def detune_il_db(delta_nm: float, fwhm_nm: float) -> float:
    """Extra IL in dB for a Gaussian spectrum detuned by delta_nm."""
    if fwhm_nm <= 0:
        return 0.0
    x = 4.0 * np.log(2.0) * (delta_nm / fwhm_nm) ** 2
    return float(10.0 * x / np.log(10.0))  # -10 log10(e^{-x}) = 10 x / ln 10


def thermal_shift(
    design: GratingDesign | None = None,
    platform: Platform = SOI220,
    bw1db_nm: float | None = None,
    dT: float = 20.0,
) -> ThermalResult:
    if design is None:
        design = leaky_wave_coupling(platform)
    if bw1db_nm is None:
        from .grating import bandwidth_1db_nm

        bw1db_nm = bandwidth_1db_nm(
            design.n_eff, design.n_g, platform.cladding.n, platform.theta_deg, platform.wavelength
        )
    gamma = design.confinement
    dn_eff_dT = gamma * SI.dn_dT + (1.0 - gamma) * SIO2.dn_dT
    theta = np.deg2rad(platform.theta_deg)
    n_c = platform.cladding.n
    # Include expansion of the period: dLambda/Lambda = alpha_si dT.
    # Differentiating n_eff - n_c sin theta = lambda/Lambda:
    # dn_eff - (d lambda)/Lambda + lambda dLambda / Lambda^2 = 0
    # d lambda / dT = Lambda * dn_eff/dT + lambda * alpha
    # and Lambda = lambda / (n_eff - n_c sin theta), n_g correction:
    denom = design.n_g - n_c * np.sin(theta)
    dlambda_dT = platform.wavelength * (dn_eff_dT + design.n_eff * SI.alpha_thermal) / denom
    dlambda_dT_nm = float(dlambda_dT / NM)
    fwhm = gaussian_fwhm_from_1db(bw1db_nm)
    extra_20 = detune_il_db(dlambda_dT_nm * dT, fwhm)
    extra_1 = detune_il_db(dlambda_dT_nm * 1.0, fwhm)
    return ThermalResult(
        dlambda_dT_nm_per_K=dlambda_dT_nm,
        dn_eff_dT=float(dn_eff_dT),
        n_g=design.n_g,
        fwhm_nm=fwhm,
        bw1db_nm=float(bw1db_nm),
        extra_il_per_K_db=float(extra_1 / 1.0),  # at +1 K
        extra_il_20K_db=float(extra_20),
        extra_il_per_K_linearized_db=float(extra_1),
        claimed_001_db_per_C=0.01,
    )
