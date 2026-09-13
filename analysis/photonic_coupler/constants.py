"""Physical constants and the 220 nm SOI process assumed throughout.

Index values are at 1550 nm, 300 K. Thermo-optic coefficients are from
Komma et al., Appl. Phys. Lett. 101, 041905 (2012) for Si and the
standard fused-silica value for SiO2. Process sigmas are literature
within-wafer numbers for 193 nm DUV silicon photonics (see the report).
"""

from __future__ import annotations

from dataclasses import dataclass


NM = 1e-9
UM = 1e-6


@dataclass(frozen=True)
class Material:
    name: str
    n: float  # refractive index at 1550 nm
    dn_dT: float  # 1/K
    alpha_thermal: float  # linear expansion, 1/K


SI = Material("silicon", n=3.476, dn_dT=1.80e-4, alpha_thermal=2.6e-6)
SIO2 = Material("silica", n=1.444, dn_dT=1.00e-5, alpha_thermal=0.5e-6)
AIR = Material("air", n=1.000, dn_dT=0.0, alpha_thermal=0.0)


@dataclass(frozen=True)
class Platform:
    """Standard 220 nm SOI MPW stack (AIM / imec / Cornerstone class)."""

    name: str = "SOI-220"
    t_si: float = 220 * NM
    t_box: float = 2.0 * UM
    t_etch: float = 70 * NM  # remaining Si in grooves = t_si - t_etch
    min_cd: float = 150 * NM
    wavelength: float = 1.550 * UM
    theta_deg: float = 8.0  # fiber angle in the top cladding
    cladding: Material = SIO2
    core: Material = SI
    box: Material = SIO2
    mfd: float = 10.4 * UM  # SMF-28 at 1550 nm, 1/e^2 intensity diameter
    # Literature citation only (Bozzola 2015, 2-D FDTD, no back-reflector).
    # Do not clamp any model or Monte Carlo draw to this number.
    ce_physics_cap: float = 0.65  # -1.87 dB
    # AIM Photonics PDK TE vertical coupler (Analog Photonics / Fahrenkopf).
    pdk_il_db: float = 2.8
    pdk_bw1db_nm: float = 30.0


SOI220 = Platform()


# Within-wafer 1-sigma process variation. Thickness and width from
# ACS Photonics 10, 928 (2023) compilation of IMEC/AMF data; etch depth
# is typically comparable to or slightly worse than width. These are
# *not* 3-sigma datasheet limits; they are 1-sigma WIW numbers used for
# Monte Carlo. Overlay applies only to two-layer (poly-Si) designs.
PROCESS_SIGMA = {
    "t_si_nm": 2.0,  # IMEC 193 nm dry, sigma(Delta t) ~ 2 nm
    "etch_nm": 3.0,  # partial-etch depth, conservative
    "cd_nm": 2.6,  # IMEC 193 nm dry, sigma(Delta w) ~ 2.59 nm
    "theta_deg": 0.4,  # fiber angle after active alignment
    "offset_um": 0.8,  # fiber longitudinal offset
    "overlay_nm": 10.0,  # unused on single-etch platform
}


# Chrostowski, Silicon Photonics Design (CUP 2015), Ch. 11: grating
# coupler peak-wavelength sensitivities on 220 nm SOI.
D_LAMBDA_NM = {
    "per_nm_tsi": 1.82,
    "per_nm_etch": 1.90,
    "per_nm_cd": 0.215,
}
