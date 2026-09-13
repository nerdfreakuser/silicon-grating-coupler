"""Link-energy consequences of coupler insertion loss.

The original draft claimed a 0.3 dB coupler yields a 70-90% energy cut
versus copper (5-10 pJ/bit down to <0.5 pJ/bit). That confuses three
different numbers:

1. Module energy of an 800G pluggable (~15 pJ/bit, DSP + laser + drivers).
2. Laser wall-plug share of that module (~20-30%).
3. Copper DAC energy, which is a reach argument, not a coupler argument.

A coupler improvement of Delta dB at *each* fiber interface scales the
required laser optical power by 10^(Delta/10) per coupler. For a
transceiver with one TX and one RX grating, two couplers sit in the
laser-to-PD path on a loopback; a packaged TX-to-RX link through fiber
has one coupler at each PIC. We report both.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnergyResult:
    delta_il_db_per_coupler: float
    n_couplers_in_path: int
    laser_optical_scale: float
    laser_electrical_pj: float
    laser_electrical_pj_improved: float
    module_pj: float
    module_fraction_saved: float
    pj_saved: float


def laser_power_scale(delta_il_db: float, n_couplers: int = 2) -> float:
    """Factor on laser optical (and electrical, at fixed WPE) power."""
    return 10.0 ** (n_couplers * delta_il_db / 10.0)


def module_energy_delta(
    il_from_db: float,
    il_to_db: float,
    n_couplers: int = 2,
    module_pj: float = 15.0,
    laser_share: float = 0.25,
) -> EnergyResult:
    """Save laser_share * (1 - 1/scale) of module energy.

    il_from is the worse coupler, il_to the better one (smaller dB).
    """
    delta = il_from_db - il_to_db
    scale = laser_power_scale(delta, n_couplers)
    # Going from worse to better *reduces* laser power by 1/scale relative
    # to the worse design. Saved fraction of *laser* energy = 1 - 1/scale.
    laser_pj = module_pj * laser_share
    laser_improved = laser_pj / scale
    saved = laser_pj - laser_improved
    return EnergyResult(
        delta_il_db_per_coupler=delta,
        n_couplers_in_path=n_couplers,
        laser_optical_scale=scale,
        laser_electrical_pj=laser_pj,
        laser_electrical_pj_improved=laser_improved,
        module_pj=module_pj,
        module_fraction_saved=saved / module_pj,
        pj_saved=saved,
    )
