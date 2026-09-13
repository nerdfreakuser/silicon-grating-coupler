"""Tidy3D 2-D domain helpers. No Flexcompute import.

The full-height input waveguide must run through the -x PML. A box that
starts at x = 0 while the simulation starts at x < 0 leaves an artificial
220→150 nm thickness step in front of the absorber.
"""

from __future__ import annotations

# Domain left edge (µm). PML occupies roughly the first 1.6 µm of this.
X_LEFT_UM = -2.5
# Free space after the last tooth before the +x PML.
X_PAD_RIGHT_UM = 3.5
# How far the full-height waveguide and remaining slab extend past the
# domain edge, so the absorber sees a continuous silicon strip.
WG_PML_OVERSHOOT_UM = 3.0


def domain_x(x_g1_um: float) -> tuple[float, float]:
    """Return (x_left, x_right) of the simulation domain in µm."""
    return X_LEFT_UM, float(x_g1_um) + X_PAD_RIGHT_UM


def wg_extra_span(x_g0_um: float, x_left_um: float = X_LEFT_UM) -> tuple[float, float]:
    """Full-height extra-Si box [lo, hi] in µm.

    lo is past the -x domain edge (into / through the PML). hi is the
    first grating tooth. The remaining-thickness slab covers the whole
    domain separately; this box is only the 70 nm of unetched silicon.
    """
    return float(x_left_um) - WG_PML_OVERSHOOT_UM, float(x_g0_um)


def wg_covers_left_boundary(x_g0_um: float, x_left_um: float = X_LEFT_UM) -> bool:
    lo, hi = wg_extra_span(x_g0_um, x_left_um)
    return lo < x_left_um and hi >= float(x_g0_um) - 1e-9
