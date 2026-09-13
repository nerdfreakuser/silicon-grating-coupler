"""Sanity checks for the analytic kit. Run: python -m pytest analysis/tests -q
or: python analysis/tests/test_sanity.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from photonic_coupler.constants import SOI220
from photonic_coupler.energy import module_energy_delta
from photonic_coupler.fdtd2d import index_at_nm, peak_and_bw
from photonic_coupler.grating import leaky_wave_coupling, phase_match_period
from photonic_coupler.slab import grating_section_indices
from photonic_coupler.stats_design import two_proportion_n, two_sample_t_n
from photonic_coupler.thermal import thermal_shift
from photonic_coupler.tidy3d_geom import (
    domain_x,
    wg_covers_left_boundary,
    wg_extra_span,
)


def test_slab_indices_in_range():
    un, et = grating_section_indices()
    assert 2.6 < un.n_eff < 3.0, un.n_eff
    assert 2.3 < et.n_eff < 2.7, et.n_eff
    assert un.n_eff > et.n_eff
    assert 0.7 < un.confinement_si < 0.95
    assert un.n_g > un.n_eff


def test_period_is_cband_typical():
    d = leaky_wave_coupling()
    assert 580 < d.period / 1e-9 < 680, d.period / 1e-9
    assert 0.2 < d.ff_min < 0.4
    assert 0.6 < d.ff_max < 0.85


def test_uniform_calibrated_to_bozzola():
    d = leaky_wave_coupling()
    assert abs(d.eta_uniform - 0.537) < 1e-6
    assert 2.5 < d.il_uniform_db < 2.9
    assert d.il_apodized_db < d.il_uniform_db


def test_half_db_is_impossible():
    d = leaky_wave_coupling()
    # Uncapped leaky-wave still sits well above 0.5 dB on this stack.
    # Do not use SOI220.ce_physics_cap here: that is a literature citation,
    # not a bound the model may impose on itself.
    assert d.il_apodized_db > 1.5
    assert d.il_uniform_db > 1.5
    assert abs(d.eta_apodized - 0.65) > 1e-6
    assert abs(d.eta_uniform - 0.65) > 1e-6


def test_metre_isclose_does_not_alias_1545():
    wl = np.array([1525, 1535, 1545, 1550, 1555], dtype=float) * 1e-9
    default_hits = np.where(np.isclose(wl, 1.550e-6))[0]
    assert 2 in default_hits, "trap: default atol=1e-8 must match 1545 nm"
    assert abs(wl[index_at_nm(wl)] / 1e-9 - 1550.0) < 1e-9


def test_peak_and_bw_requires_exact_1550():
    wl_skip = np.array([1525, 1535, 1545, 1555], dtype=float) * 1e-9
    ce_skip = np.array([0.30, 0.40, 0.50, 0.55])
    try:
        peak_and_bw(wl_skip, ce_skip)
        raise AssertionError("nearest-bin 1550 must be rejected")
    except RuntimeError:
        pass
    wl = np.array([1525, 1550, 1555], dtype=float) * 1e-9
    out = peak_and_bw(wl, np.array([0.30, 0.41, 0.55]))
    assert out["lambda_ce_nm"] == 1550.0
    assert abs(out["ce_1550"] - 0.41) < 1e-12


def test_thermal_is_not_0p01_db_per_C():
    th = thermal_shift()
    assert 0.04 < th.dlambda_dT_nm_per_K < 0.12
    assert th.extra_il_20K_db < 0.05


def test_energy_is_not_seventy_percent():
    e = module_energy_delta(3.0, 0.3, n_couplers=2)
    assert e.module_fraction_saved < 0.30


def test_tidy3d_waveguide_covers_left_pml():
    # The bug: extra-Si box from 0 to x_g0 while the domain starts at -1.75.
    x_g0, x_g1 = 7.0, 19.5
    x_left, x_right = domain_x(x_g1)
    assert x_left < 0.0
    assert x_right > x_g1
    lo, hi = wg_extra_span(x_g0, x_left)
    assert lo < x_left
    assert abs(hi - x_g0) < 1e-12
    assert wg_covers_left_boundary(x_g0, x_left)
    # The old construction (center=0.5*x_g0, size=x_g0) starts at 0.
    old_lo = 0.0
    assert old_lo > x_left
    assert not (old_lo < x_left)


def test_sample_size_is_devices_not_wafers():
    n = two_proportion_n(0.50, 0.70)
    assert 70 < n < 120
    n_t = two_sample_t_n(0.30, 0.30)
    assert 10 < n_t < 30


if __name__ == "__main__":
    for fn in [
        test_slab_indices_in_range,
        test_period_is_cband_typical,
        test_uniform_calibrated_to_bozzola,
        test_half_db_is_impossible,
        test_metre_isclose_does_not_alias_1545,
        test_peak_and_bw_requires_exact_1550,
        test_thermal_is_not_0p01_db_per_C,
        test_energy_is_not_seventy_percent,
        test_sample_size_is_devices_not_wafers,
        test_tidy3d_waveguide_covers_left_pml,
    ]:
        fn()
        print("ok", fn.__name__)
    print("all sanity checks passed")
