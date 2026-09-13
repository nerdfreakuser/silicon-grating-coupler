"""Phase matching, leaky-wave fiber overlap, directionality, and DRC.

Coupling efficiency is factored as

    eta = D * eta_overlap * (1 - R) * eta_taper

where D is the up/down directionality (BOX-interference model), eta_overlap
is the overlap of the radiated near-field with the SMF-28 Gaussian,
R is the second-order Bragg reflection (suppressed by the off-vertical
fiber angle), and eta_taper is taken as 0.98 for a long adiabatic taper.

This is the Taillaert / Roelkens / Benedikovic decomposition. Absolute
calibration of D is anchored so a uniform 70 nm-etch, 2 um BOX, 50% fill
grating sits at the published ~53.7% 2-D FDTD result of Bozzola et al.,
Opt. Express 23, 16289 (2015). The overlap and reflection pieces are
computed from the model, not fitted.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .constants import NM, Platform, SOI220, UM
from .slab import SlabMode, grating_section_indices, te_fundamental


def phase_match_period(
    n_eff: float,
    wavelength: float,
    n_clad: float,
    theta_deg: float,
    order: int = 1,
) -> float:
    """Lambda = m * lambda / (n_eff - n_clad sin theta)."""
    denom = n_eff - n_clad * np.sin(np.deg2rad(theta_deg))
    if denom <= 0:
        raise ValueError("phase-match denominator is non-positive")
    return order * wavelength / denom


def bloch_neff(ff: float, n_unetch: float, n_etch: float) -> float:
    """First-order volume average of the two grating sections."""
    ff = np.clip(ff, 0.0, 1.0)
    return ff * n_unetch + (1.0 - ff) * n_etch


def min_max_fill(period: float, min_cd: float) -> tuple[float, float]:
    """DRC window: tooth and groove both >= min_cd."""
    lo = min_cd / period
    hi = 1.0 - lo
    if lo >= hi:
        raise ValueError("period too small for min CD on both tooth and groove")
    return lo, hi


def radiation_alpha(etch_m, fill, t_si, alpha_ref: float = 0.11e6):
    """Field radiation constant alpha (1/m) so power ~ exp(-2 alpha z).

    Calibrated so a 70 nm etch, 50% fill, 220 nm SOI grating has
    alpha ~ 0.11 /um, i.e. a ~15 um 1/e field length, matching typical
    20-period C-band couplers. Scales as (etch/t_si)^2 * sin^2(pi ff)
    in the shallow-etch perturbation limit, with a soft cap at full etch.
    Accepts scalars or ndarrays.
    """
    contrast = np.clip(np.asarray(etch_m, dtype=float) / t_si, 0.0, 1.0)
    fill_factor = np.sin(np.pi * np.clip(np.asarray(fill, dtype=float), 0.0, 1.0)) ** 2
    scale = (contrast / (70e-9 / 220e-9)) ** 2 * fill_factor
    out = alpha_ref * scale
    return float(out) if np.ndim(out) == 0 else out


def box_directionality(
    t_box: float,
    wavelength: float,
    n_ox: float,
    n_si: float,
    theta_clad_deg: float,
    intrinsic_up: float = 0.62,
) -> float:
    """Upward fraction after interference with the handle reflection.

    Two-beam model: the downward radiated amplitude reflects at the
    BOX/handle interface with amplitude r = (n_ox - n_si)/(n_ox + n_si)
    and round-trip phase 4 pi n_ox t_box cos(theta_ox) / lambda.
    intrinsic_up is the no-substrate up-fraction of a 70 nm partial etch
    (broken vertical symmetry). Result is clipped to (0.05, 0.95).
    """
    theta = np.deg2rad(theta_clad_deg)
    # Angle in the BOX from Snell, using the grating diffraction angle.
    sin_box = np.clip((1.0 * np.sin(theta)), -1.0, 1.0)
    cos_box = np.sqrt(max(1e-12, 1.0 - sin_box**2))
    r = (n_ox - n_si) / (n_ox + n_si)
    phase = 4.0 * np.pi * n_ox * t_box * cos_box / wavelength
    a_up = np.sqrt(intrinsic_up)
    a_dn = np.sqrt(max(1e-12, 1.0 - intrinsic_up))
    e_up = a_up + r * a_dn * np.exp(1j * phase)
    p_up = float(np.abs(e_up) ** 2)
    p_sub = (1.0 - r**2) * a_dn**2  # transmitted into the handle
    denom = p_up + p_sub
    d = p_up / denom if denom > 0 else 0.5
    return float(np.clip(d, 0.05, 0.95))


def bragg_reflection(theta_deg: float, r0: float = 0.18) -> float:
    """Second-order Bragg reflection vs fiber angle.

    At theta = 0 the first-order fiber-coupling period coincides with the
    second-order Bragg period and on-chip reflection is large. An 8-10 deg
    tilt detunes them. Exponential detuning is a compact fit to typical
    FDTD (R ~ 15-20% at 0 deg, ~1-3% at 8-10 deg for a uniform grating).
    """
    return float(r0 * np.exp(-((theta_deg / 4.0) ** 2)))


def _gaussian_field(z: np.ndarray, z0: float, w0: float) -> np.ndarray:
    """SMF-28 field: intensity 1/e^2 diameter = 2 w0 = MFD, so E ~ exp(-r^2/w0^2)."""
    return np.exp(-((z - z0) ** 2) / (w0**2))


def overlap_uniform(alpha: float, length: float, z0: float, w0: float, n: int = 512) -> float:
    """Overlap of exp(-alpha z) radiated field with a Gaussian fiber mode."""
    z = np.linspace(0.0, length, n)
    radiated = np.sqrt(2.0 * alpha) * np.exp(-alpha * z)  # |A|^2 integrates to 1-exp(-2aL)
    # The sqrt(2 alpha) exp(-alpha z) is the field whose power density is 2a e^{-2a z}.
    fiber = _gaussian_field(z, z0, w0)
    num = np.trapezoid(radiated * fiber, z) ** 2
    den = np.trapezoid(radiated**2, z) * np.trapezoid(fiber**2, z)
    if den <= 0:
        return 0.0
    return float(num / den)


def best_uniform_overlap(alpha: float, w0: float, length: float | None = None) -> tuple[float, float, float]:
    """Maximize overlap over fiber offset; length defaults to ~3/alpha."""
    if length is None:
        length = min(40e-6, max(8e-6, 3.0 / max(alpha, 1e3)))
    z0s = np.linspace(0.0, length, 41)
    vals = [overlap_uniform(alpha, length, z0, w0) for z0 in z0s]
    i = int(np.argmax(vals))
    return float(vals[i]), float(z0s[i]), float(length)


def apodized_radiated_field(
    z: np.ndarray,
    ff: np.ndarray,
    etch_m: float,
    t_si: float,
) -> np.ndarray:
    """Power-conserving radiated field for a z-dependent fill (hence alpha)."""
    alpha = np.asarray(radiation_alpha(etch_m, ff, t_si), dtype=float)
    dz = z[1] - z[0] if len(z) > 1 else 1e-9
    logP = np.concatenate([[0.0], np.cumsum(-2.0 * alpha[:-1] * dz)])
    P = np.exp(logP)
    irad = 2.0 * alpha * P
    return np.sqrt(np.maximum(irad, 0.0))


def overlap_apodized(
    length: float,
    ff_start: float,
    ff_end: float,
    etch_m: float,
    t_si: float,
    z0: float,
    w0: float,
    n: int = 512,
) -> float:
    z = np.linspace(0.0, length, n)
    ff = np.linspace(ff_start, ff_end, n)
    radiated = apodized_radiated_field(z, ff, etch_m, t_si)
    fiber = _gaussian_field(z, z0, w0)
    num = np.trapezoid(radiated * fiber, z) ** 2
    den = np.trapezoid(radiated**2, z) * np.trapezoid(fiber**2, z)
    if den <= 0:
        return 0.0
    return float(num / den)


def best_apodized_overlap(
    length: float,
    ff_start: float,
    ff_end: float,
    etch_m: float,
    t_si: float,
    w0: float,
) -> tuple[float, float]:
    z0s = np.linspace(0.0, length, 41)
    vals = [
        overlap_apodized(length, ff_start, ff_end, etch_m, t_si, z0, w0) for z0 in z0s
    ]
    i = int(np.argmax(vals))
    return float(vals[i]), float(z0s[i])


@dataclass
class GratingDesign:
    period: float
    fill: float
    n_eff: float
    n_unetch: float
    n_etch: float
    n_g: float
    confinement: float
    ff_min: float
    ff_max: float
    directionality: float
    reflection: float
    eta_uniform: float
    eta_apodized: float
    il_uniform_db: float
    il_apodized_db: float
    overlap_uniform: float
    overlap_apodized: float
    alpha: float
    length: float
    z0_uniform: float
    z0_apodized: float
    ff_start: float
    ff_end: float
    taper_eta: float = 0.98
    eta_2d: float = 0.87

    def as_dict(self) -> dict:
        return {
            "period_nm": self.period / NM,
            "fill": self.fill,
            "n_eff": self.n_eff,
            "n_unetch": self.n_unetch,
            "n_etch": self.n_etch,
            "n_g": self.n_g,
            "confinement_si": self.confinement,
            "ff_min": self.ff_min,
            "ff_max": self.ff_max,
            "directionality": self.directionality,
            "reflection": self.reflection,
            "eta_uniform": self.eta_uniform,
            "eta_apodized": self.eta_apodized,
            "il_uniform_db": self.il_uniform_db,
            "il_apodized_db": self.il_apodized_db,
            "overlap_uniform": self.overlap_uniform,
            "overlap_apodized": self.overlap_apodized,
            "alpha_per_um": self.alpha * UM,
            "length_um": self.length / UM,
            "z0_uniform_um": self.z0_uniform / UM,
            "z0_apodized_um": self.z0_apodized / UM,
            "ff_start": self.ff_start,
            "ff_end": self.ff_end,
            "eta_2d": self.eta_2d,
        }


def db(eta: float) -> float:
    eta = max(eta, 1e-16)
    return float(-10.0 * np.log10(eta))


def leaky_wave_coupling(platform: Platform = SOI220, fill: float = 0.50) -> GratingDesign:
    unetched, etched = grating_section_indices(platform)
    n_eff = bloch_neff(fill, unetched.n_eff, etched.n_eff)
    period = phase_match_period(
        n_eff, platform.wavelength, platform.cladding.n, platform.theta_deg
    )
    ff_min, ff_max = min_max_fill(period, platform.min_cd)
    D = box_directionality(
        platform.t_box,
        platform.wavelength,
        platform.box.n,
        platform.core.n,
        platform.theta_deg,
    )
    R = bragg_reflection(platform.theta_deg)
    alpha = radiation_alpha(platform.t_etch, fill, platform.t_si)
    w0 = platform.mfd / 2.0
    ov_u, z0_u, length = best_uniform_overlap(alpha, w0)
    # 2-D correction: the overlap above is a 1-D (z only) inner product.
    # A focusing coupler still has a finite y-overlap with SMF-28, and the
    # 2-D radiated wavefront is not a perfect Gaussian. We set this factor
    # so a uniform 70 nm-etch, 2 um BOX, 50% fill device lands on Bozzola
    # et al.'s 53.7% 2-D FDTD result (Opt. Express 23, 16289, 2015).
    taper = 0.98
    eta_u_1d = D * ov_u * (1.0 - R) * taper
    eta_2d = 0.537 / max(eta_u_1d, 1e-6)
    eta_2d = float(np.clip(eta_2d, 0.70, 1.0))

    # Grid-search a linear fill apodization inside DRC. Strong radiation at
    # the fiber-facing end (high fill contrast) is the usual construction.
    best_ov, ff_start, ff_end, length_a, z0_a = ov_u, fill, fill, length, z0_u
    for L in (12e-6, 16e-6, 20e-6, 24e-6):
        for fs in (0.55, 0.65, 0.72, ff_max):
            fs = min(float(fs), ff_max)
            for fe in (ff_min, 0.32, 0.42):
                fe = max(float(fe), ff_min)
                if fs < fe + 0.08:
                    continue
                ov, z0 = best_apodized_overlap(
                    L, fs, fe, platform.t_etch, platform.t_si, w0
                )
                if ov > best_ov:
                    best_ov, ff_start, ff_end, length_a, z0_a = ov, fs, fe, L, z0
    ov_a = best_ov
    length = length_a
    # Do not clamp to Bozzola's 65% ceiling. That number is a published 2-D
    # FDTD result, not a bound this model is allowed to impose on itself.
    eta_u = eta_u_1d * eta_2d
    eta_a = D * ov_a * (1.0 - R) * taper * eta_2d
    # Weighted group index / confinement for thermal model.
    n_g = fill * unetched.n_g + (1.0 - fill) * etched.n_g
    conf = fill * unetched.confinement_si + (1.0 - fill) * etched.confinement_si
    return GratingDesign(
        period=period,
        fill=fill,
        n_eff=n_eff,
        n_unetch=unetched.n_eff,
        n_etch=etched.n_eff,
        n_g=n_g,
        confinement=conf,
        ff_min=ff_min,
        ff_max=ff_max,
        directionality=D,
        reflection=R,
        eta_uniform=eta_u,
        eta_apodized=eta_a,
        il_uniform_db=db(eta_u),
        il_apodized_db=db(eta_a),
        overlap_uniform=ov_u,
        overlap_apodized=ov_a,
        alpha=alpha,
        length=length,
        z0_uniform=z0_u,
        z0_apodized=z0_a,
        ff_start=ff_start,
        ff_end=ff_end,
        taper_eta=taper,
        eta_2d=eta_2d,
    )


def focusing_grating_curves(
    n_eff: float,
    wavelength: float,
    n_clad: float,
    theta_deg: float,
    n_lines: int = 25,
    y_span: float = 12e-6,
    n_pts: int = 200,
) -> list[np.ndarray]:
    """Confocal grating lines: m lambda = n_eff r - x n_clad sin theta.

    Origin is the focal point (waveguide end). Returns a list of (x, y)
    polylines, one per grating line.
    """
    s = n_clad * np.sin(np.deg2rad(theta_deg))
    curves = []
    for m in range(8, 8 + n_lines):
        ys = np.linspace(-y_span, y_span, n_pts)
        # n_eff sqrt(x^2+y^2) - x s = m lambda
        # Let r = sqrt(x^2+y^2). n_eff r - s x = m lambda.
        # Solve quadratic for x given y.
        target = m * wavelength
        # (n_eff^2 - s^2) x^2 + 2 s target x + n_eff^2 y^2 - target^2 = 0
        a = n_eff**2 - s**2
        b = 2.0 * s * target
        c = n_eff**2 * ys**2 - target**2
        disc = b**2 - 4.0 * a * c
        x = np.full_like(ys, np.nan)
        ok = disc >= 0
        x[ok] = (-b + np.sqrt(disc[ok])) / (2.0 * a)
        pts = np.column_stack([x, ys])
        pts = pts[np.isfinite(pts[:, 0]) & (pts[:, 0] > 0)]
        if len(pts) > 5:
            curves.append(pts)
    return curves


def bandwidth_1db_nm(n_eff: float, n_g: float, n_clad: float, theta_deg: float, wavelength: float) -> float:
    """First-order 1 dB bandwidth from angular/fiber acceptance.

    From the phase-match derivative, d theta / d lambda ~ (n_g - n_clad sin theta)
    / (lambda n_clad cos theta). A fiber NA-like acceptance of ~0.07 rad
    (empirical, Waldhausl / Halir) gives Delta lambda_1dB ~ 30-40 nm.
    We use the published proportionality Delta lambda_1dB ~ 0.07 * lambda
    * n_clad cos theta / (n_g - n_clad sin theta) converted to nm, which
    reproduces the ~30 nm AIM PDK number on this stack.
    """
    theta = np.deg2rad(theta_deg)
    denom = n_g - n_clad * np.sin(theta)
    dlam = 0.07 * wavelength * n_clad * np.cos(theta) / denom
    return float(dlam / NM)
