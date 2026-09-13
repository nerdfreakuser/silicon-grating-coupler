"""Four grating layouts under identical foundry constraints.

Every design uses the same stack (220 nm SOI, 70 nm etch, 2 um BOX, oxide
clad), the same 8 deg SMF-28 fiber, the same 150 nm min CD, and the same
grating aperture (~20 periods, ~12.4 um). The only thing that changes is
how fill and period vary along the grating.

    uniform     50% fill, constant period          -- PDK-class baseline
    chirp       50% fill, linear period chirp      -- bandwidth-oriented
    taillaert   linear fill apodization, const. Λ  -- textbook strong design
    proposed    fill apodization + angle-preserving period chirp (this work)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .constants import NM, SOI220, UM
from .grating import bloch_neff, min_max_fill, phase_match_period
from .slab import grating_section_indices


@dataclass
class GCLayout:
    name: str
    short: str
    color: str
    proposed: bool
    teeth: np.ndarray  # (N, 2) x_left, x_right of unetched bars, metres, grating-local
    period_mean: float
    fill_start: float
    fill_end: float
    length: float
    n_teeth: int
    notes: str = ""

    def shifted(self, x0: float) -> np.ndarray:
        t = self.teeth.copy()
        t += x0
        return t


def _clamp_fill(ff: float, period: float, min_cd: float) -> float:
    lo, hi = min_max_fill(period, min_cd)
    return float(np.clip(ff, lo, hi))


def _teeth_from_periods(periods: np.ndarray, fills: np.ndarray) -> np.ndarray:
    """Build unetched-bar [left, right] from per-period (Λ, fill)."""
    teeth = []
    x = 0.0
    for lam, ff in zip(periods, fills):
        w_un = ff * lam
        # Center the unetched bar in the period (standard).
        left = x + 0.5 * (lam - w_un)
        right = left + w_un
        teeth.append((left, right))
        x += lam
    return np.asarray(teeth, dtype=float)


def _n_bloch():
    un, et = grating_section_indices(SOI220)
    return un.n_eff, et.n_eff


def _period_for_fill(ff: float, n_un: float, n_et: float) -> float:
    nb = bloch_neff(ff, n_un, n_et)
    return phase_match_period(
        nb, SOI220.wavelength, SOI220.cladding.n, SOI220.theta_deg
    )


def make_uniform(n_periods: int = 20) -> GCLayout:
    n_un, n_et = _n_bloch()
    ff = 0.50
    lam = _period_for_fill(ff, n_un, n_et)
    periods = np.full(n_periods, lam)
    fills = np.full(n_periods, ff)
    teeth = _teeth_from_periods(periods, fills)
    return GCLayout(
        name="Uniform 50% (PDK-class)",
        short="uniform",
        color="#7a7a7a",
        proposed=False,
        teeth=teeth,
        period_mean=lam,
        fill_start=ff,
        fill_end=ff,
        length=float(periods.sum()),
        n_teeth=n_periods,
        notes="Constant period and fill. The usual foundry starting cell.",
    )


def make_chirp(n_periods: int = 20, d_period: float = 20e-9) -> GCLayout:
    """Linear period chirp at 50% fill. Common bandwidth trick."""
    n_un, n_et = _n_bloch()
    ff = 0.50
    lam0 = _period_for_fill(ff, n_un, n_et)
    periods = np.linspace(lam0 - d_period, lam0 + d_period, n_periods)
    fills = np.array([_clamp_fill(ff, p, SOI220.min_cd) for p in periods])
    teeth = _teeth_from_periods(periods, fills)
    return GCLayout(
        name="Linear period chirp, 50% fill",
        short="chirp",
        color="#2e7d32",
        proposed=False,
        teeth=teeth,
        period_mean=float(np.mean(periods)),
        fill_start=ff,
        fill_end=ff,
        length=float(periods.sum()),
        n_teeth=n_periods,
        notes="Industrial bandwidth design. Same DRC, same etch, no fill apodization.",
    )


def make_taillaert(n_periods: int = 20) -> GCLayout:
    """Linear fill apodization, constant period — the textbook strong design."""
    n_un, n_et = _n_bloch()
    lam = _period_for_fill(0.50, n_un, n_et)
    lo, hi = min_max_fill(lam, SOI220.min_cd)
    fills = np.linspace(hi, lo, n_periods)  # strong radiation at fiber-facing start
    periods = np.full(n_periods, lam)
    teeth = _teeth_from_periods(periods, fills)
    return GCLayout(
        name="Taillaert fill apodization",
        short="taillaert",
        color="#c45911",
        proposed=False,
        teeth=teeth,
        period_mean=lam,
        fill_start=float(fills[0]),
        fill_end=float(fills[-1]),
        length=float(periods.sum()),
        n_teeth=n_periods,
        notes="Linear duty-cycle apodization at fixed period (Taillaert/Benedikovic class), DRC-clamped.",
    )


def make_proposed(n_periods: int = 20) -> GCLayout:
    """Fill apodization + period chirp that holds the 8 deg radiation angle."""
    n_un, n_et = _n_bloch()
    lam_mid = _period_for_fill(0.50, n_un, n_et)
    lo, hi = min_max_fill(lam_mid, SOI220.min_cd)
    fills = np.linspace(hi, lo, n_periods)
    periods = np.array([_period_for_fill(float(f), n_un, n_et) for f in fills])
    # Re-clamp with the local period (chirp changes min-CD fill slightly).
    fills = np.array([_clamp_fill(float(f), float(p), SOI220.min_cd) for f, p in zip(fills, periods)])
    periods = np.array([_period_for_fill(float(f), n_un, n_et) for f in fills])
    teeth = _teeth_from_periods(periods, fills)
    return GCLayout(
        name="Proposed: fill + angle-preserving chirp",
        short="proposed",
        color="#1f4e79",
        proposed=True,
        teeth=teeth,
        period_mean=float(np.mean(periods)),
        fill_start=float(fills[0]),
        fill_end=float(fills[-1]),
        length=float(periods.sum()),
        n_teeth=n_periods,
        notes="This work. DRC-legal fill apodization with Λ(z) so θ stays 8 deg as n_B(f) changes.",
    )


def all_designs(n_periods: int = 20) -> list[GCLayout]:
    return [
        make_uniform(n_periods),
        make_chirp(n_periods),
        make_taillaert(n_periods),
        make_proposed(n_periods),
    ]
