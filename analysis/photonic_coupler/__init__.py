"""Foundry-constrained silicon grating-coupler analysis kit.

This package implements the analytic and semi-analytic models used in the
companion technical report. It does not replace 2-D/3-D FDTD; it is the
physics that can be derived in closed form or with a 1-D slab solver, plus
a process Monte Carlo anchored to published foundry variation.
"""

from .constants import Material, Platform
from .slab import SlabMode, te_fundamental
from .grating import GratingDesign, phase_match_period, leaky_wave_coupling
from .thermal import thermal_shift
from .yield_mc import ProcessModel, monte_carlo_il
from .stats_design import two_proportion_n, two_sample_t_n, clopper_pearson
from .energy import laser_power_scale, module_energy_delta

__all__ = [
    "Material",
    "Platform",
    "SlabMode",
    "te_fundamental",
    "GratingDesign",
    "phase_match_period",
    "leaky_wave_coupling",
    "thermal_shift",
    "ProcessModel",
    "monte_carlo_il",
    "two_proportion_n",
    "two_sample_t_n",
    "clopper_pearson",
    "laser_power_scale",
    "module_energy_delta",
]
