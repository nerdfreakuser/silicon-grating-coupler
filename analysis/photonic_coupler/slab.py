"""TE slab-waveguide modes for the unetched and shallow-etched grating sections.

The grating is treated as a 1-D multilayer in the vertical direction. The
Bloch effective index of a rectangular grating is then the duty-cycle
average of the unetched and etched slab indices, which is the standard
first-order design formula (Taillaert, Benedikovic, and foundry PDKs).

Even TE modes of a symmetric three-layer slab satisfy

    kappa * sin(kappa * d/2) - gamma * cos(kappa * d/2) = 0

with kappa = k0 sqrt(n_core^2 - n_eff^2) and
gamma = k0 sqrt(n_eff^2 - n_clad^2). The fundamental is the first root
between the cladding and core indices, below the first tan pole.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq

from .constants import NM, Platform, SOI220


@dataclass(frozen=True)
class SlabMode:
    n_eff: float
    n_g: float
    confinement_si: float
    thickness: float
    wavelength: float

    @property
    def dn_eff_dlambda(self) -> float:
        # n_g = n_eff - lambda * dn_eff/dlambda
        return (self.n_eff - self.n_g) / self.wavelength


def _even_te_residual(n_eff: float, d: float, n_core: float, n_clad: float, k0: float) -> float:
    inside = n_core**2 - n_eff**2
    outside = n_eff**2 - n_clad**2
    if inside <= 0.0 or outside <= 0.0:
        return 1e6
    kappa = k0 * np.sqrt(inside)
    gamma = k0 * np.sqrt(outside)
    arg = 0.5 * kappa * d
    return kappa * np.sin(arg) - gamma * np.cos(arg)


def _bracket_even_te(thickness: float, n_core: float, n_clad: float, k0: float) -> tuple[float, float]:
    """Bracket the fundamental even TE root.

    tan(kappa d/2) has its first pole at kappa = pi/d. The fundamental lives
    at *smaller* kappa (higher n_eff) than that pole, i.e. between the pole
    and n_core. If the pole lies below n_clad (thin slab), the bracket is
    (n_clad, n_core).
    """
    hi = n_core - 1e-8
    disc = n_core**2 - (np.pi / (k0 * thickness)) ** 2
    if disc > n_clad**2:
        lo = float(np.sqrt(disc) + 1e-8)
    else:
        lo = n_clad + 1e-8
    if lo >= hi:
        lo = n_clad + 1e-8
    return lo, hi


def te_neff_only(thickness: float, wavelength: float, n_core: float, n_clad: float) -> float:
    k0 = 2.0 * np.pi / wavelength
    lo, hi = _bracket_even_te(thickness, n_core, n_clad, k0)
    r_lo = _even_te_residual(lo, thickness, n_core, n_clad, k0)
    r_hi = _even_te_residual(hi, thickness, n_core, n_clad, k0)
    if r_lo * r_hi > 0:
        raise RuntimeError(
            f"No TE even root in ({lo:.4f}, {hi:.4f}) for d={thickness/NM:.1f} nm"
        )
    return float(brentq(_even_te_residual, lo, hi, args=(thickness, n_core, n_clad, k0)))


def te_fundamental(
    thickness: float,
    wavelength: float,
    n_core: float,
    n_clad: float,
    dn_dlambda_step: float = 2e-9,
) -> SlabMode:
    """Fundamental even TE mode of a symmetric clad/core/clad slab."""
    k0 = 2.0 * np.pi / wavelength
    n_eff = te_neff_only(thickness, wavelength, n_core, n_clad)
    n_plus = te_neff_only(thickness, wavelength + dn_dlambda_step, n_core, n_clad)
    n_minus = te_neff_only(thickness, wavelength - dn_dlambda_step, n_core, n_clad)
    dn_dl = (n_plus - n_minus) / (2.0 * dn_dlambda_step)
    n_g = n_eff - wavelength * dn_dl

    kappa = k0 * np.sqrt(n_core**2 - n_eff**2)
    gamma = k0 * np.sqrt(n_eff**2 - n_clad**2)
    # Even Ey ~ cos(kappa x) in core, continuous to cos(kappa d/2) exp(-gamma u) in clad.
    core_i = 0.5 * thickness + np.sin(kappa * thickness) / (2.0 * kappa)
    interface = np.cos(0.5 * kappa * thickness) ** 2
    clad_i = interface / gamma  # both claddings
    gamma_si = float(core_i / (core_i + clad_i))
    return SlabMode(
        n_eff=n_eff,
        n_g=float(n_g),
        confinement_si=gamma_si,
        thickness=thickness,
        wavelength=wavelength,
    )


def grating_section_indices(platform: Platform = SOI220) -> tuple[SlabMode, SlabMode]:
    """Unetched (full 220 nm) and shallow-etched (remaining Si) slab modes."""
    unetched = te_fundamental(
        platform.t_si, platform.wavelength, platform.core.n, platform.cladding.n
    )
    remaining = platform.t_si - platform.t_etch
    etched = te_fundamental(
        remaining, platform.wavelength, platform.core.n, platform.cladding.n
    )
    return unetched, etched
