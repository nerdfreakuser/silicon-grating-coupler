"""Tidy3D 2-D check of the four grating layouts.

Fixes versus the first batch:
- Full-height input waveguide continues through the -x PML (no 220→150 nm
  step at x = 0).
- Fiber x-position is maximised at 1550.00 nm (matched to the in-house
  active-alignment policy). The first batch parked the beam at the grating
  midpoint.
- Etch sweep includes Taillaert fill-only.
- Mesh series 16 → 8 → 4 nm at frozen alignment and frozen geometry.

Wavelength grid always contains 1550.00 nm.

Usage:
    python analysis/run_tidy3d_compare.py --estimate
    python analysis/run_tidy3d_compare.py --campaign
    python analysis/run_tidy3d_compare.py --smoke
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _auth_tidy3d import configure  # noqa: E402
from photonic_coupler.gc_designs import all_designs  # noqa: E402
from photonic_coupler.tidy3d_geom import (  # noqa: E402
    domain_x,
    wg_covers_left_boundary,
    wg_extra_span,
)

import tidy3d as td  # noqa: E402
import tidy3d.web as web  # noqa: E402

RES = ROOT / "analysis" / "results"
RES.mkdir(parents=True, exist_ok=True)

N_SI = 3.476
N_OX = 1.444
T_SI = 0.220
T_BOX = 2.0
T_ETCH_NOM = 0.070
THETA = np.deg2rad(8.0)
MFD = 10.4
WAIST = MFD / 2.0
X_WG = 7.0
WLS_UM = np.array([1.525, 1.535, 1.545, 1.550, 1.555, 1.565, 1.575])
ALIGN_OFFSETS_UM = np.array([-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0])
DESIGNS = ("uniform", "chirp", "taillaert", "proposed")


def _mediums():
    si = td.Medium(permittivity=N_SI**2, name="Si")
    ox = td.Medium(permittivity=N_OX**2, name="SiO2")
    return si, ox


def _teeth_um(layout, x0_um: float, cd_bias_um: float = 0.0) -> np.ndarray:
    teeth = layout.shifted(x0_um * 1e-6) / 1e-6
    if cd_bias_um != 0.0:
        mid = 0.5 * (teeth[:, 0] + teeth[:, 1])
        half = 0.5 * (teeth[:, 1] - teeth[:, 0]) + 0.5 * cd_bias_um
        half = np.maximum(half, 0.02)
        teeth = np.column_stack([mid - half, mid + half])
    return teeth


def _layout_at(layout, n_per: int):
    if layout.n_teeth == n_per:
        return layout
    from photonic_coupler.gc_designs import (
        make_chirp,
        make_proposed,
        make_taillaert,
        make_uniform,
    )

    factory = {
        "uniform": make_uniform,
        "chirp": make_chirp,
        "taillaert": make_taillaert,
        "proposed": make_proposed,
    }[layout.short]
    return factory(n_per)


def build_sim(
    layout,
    *,
    dl: float = 0.016,
    etch_um: float = T_ETCH_NOM,
    t_si_um: float = T_SI,
    cd_bias_um: float = 0.0,
    wls=WLS_UM,
    run_time: float = 1.6e-12,
    x_fib_offset_um: float = 0.0,
    field: bool = False,
    n_periods: int | None = None,
) -> tuple[td.Simulation, dict]:
    si, ox = _mediums()
    n_per = 20 if n_periods is None else n_periods
    layout = _layout_at(layout, n_per)

    teeth = _teeth_um(layout, X_WG, cd_bias_um)
    x_g0, x_g1 = float(teeth[0, 0]), float(teeth[-1, 1])
    x_left, x_right = domain_x(x_g1)
    wg_lo, wg_hi = wg_extra_span(x_g0, x_left)
    if not wg_covers_left_boundary(x_g0, x_left):
        raise RuntimeError("full-height waveguide does not cover the -x boundary")

    t_remain = max(0.04, t_si_um - etch_um)
    extra_h = t_si_um - t_remain
    extra_zc = t_remain + 0.5 * extra_h
    cx = 0.5 * (x_left + x_right)
    lx = x_right - x_left
    remain_lo, remain_hi = wg_lo, x_right + 3.0

    structs = [
        td.Structure(
            geometry=td.Box(
                center=(0.5 * (remain_lo + remain_hi), 0, -T_BOX - 2.0),
                size=(remain_hi - remain_lo, td.inf, 4.0),
            ),
            medium=si,
            name="handle",
        ),
        td.Structure(
            geometry=td.Box(
                center=(0.5 * (remain_lo + remain_hi), 0, 0.5 * t_remain),
                size=(remain_hi - remain_lo, td.inf, t_remain),
            ),
            medium=si,
            name="remain",
        ),
        td.Structure(
            geometry=td.Box(
                center=(0.5 * (wg_lo + wg_hi), 0, extra_zc),
                size=(wg_hi - wg_lo, td.inf, extra_h),
            ),
            medium=si,
            name="wg_extra",
        ),
    ]
    for i, (left, right) in enumerate(teeth):
        w = float(right - left)
        xc = 0.5 * (left + right)
        structs.append(
            td.Structure(
                geometry=td.Box(center=(xc, 0, extra_zc), size=(w, td.inf, extra_h)),
                medium=si,
                name=f"tooth_{i}",
            )
        )

    freqs = td.C_0 / np.asarray(wls, dtype=float)
    freq0 = td.C_0 / 1.550
    fwidth = 0.18 * freq0
    pulse = td.GaussianPulse(freq0=freq0, fwidth=fwidth)

    x_fib_mid = 0.5 * (x_g0 + x_g1)
    x_fib = x_fib_mid + float(x_fib_offset_um)
    z_fib = t_si_um + 1.20
    beam = td.GaussianBeam(
        center=(x_fib, 0, z_fib),
        size=(18.0, td.inf, 0),
        source_time=pulse,
        direction="-",
        angle_theta=THETA,
        angle_phi=0.0,
        pol_angle=np.pi / 2,
        waist_radius=WAIST,
        name="fiber",
        num_freqs=9 if len(wls) > 1 else 5,
    )

    mode_spec = td.ModeSpec(num_modes=1, target_neff=2.85)
    x_mon = min(x_g0 - 2.5, x_g0 - 1.2)
    x_mon = max(x_mon, x_left + 1.4)
    monitors = [
        td.ModeMonitor(
            center=(x_mon, 0, 0.5 * t_si_um),
            size=(0, td.inf, 1.6),
            freqs=list(freqs),
            mode_spec=mode_spec,
            name="wg_left",
        ),
        td.ModeMonitor(
            center=(x_g1 + 1.8, 0, 0.5 * t_remain),
            size=(0, td.inf, 1.6),
            freqs=list(freqs),
            mode_spec=mode_spec,
            name="wg_right",
        ),
    ]
    if field:
        monitors.append(
            td.FieldMonitor(
                center=(x_fib_mid, 0, 0.5 * t_si_um),
                size=(min(22.0, lx), 0, 5.5),
                freqs=[freq0],
                fields=["Ey"],
                name="Ey_xz",
            )
        )

    sim = td.Simulation(
        center=(cx, 0, 0.15),
        size=(lx, 0, 7.0),
        medium=ox,
        structures=structs,
        sources=[beam],
        monitors=monitors,
        grid_spec=td.GridSpec.uniform(dl=dl),
        boundary_spec=td.BoundarySpec(
            x=td.Boundary.pml(num_layers=10),
            y=td.Boundary.periodic(),
            z=td.Boundary.pml(num_layers=10),
        ),
        run_time=run_time,
        shutoff=1e-6,
        subpixel=True,
        normalize_index=0,
    )
    bmin, bmax = sim.bounds
    xmin = float(bmin[0])
    xmax = float(bmax[0])
    geom = {
        "design": layout.short,
        "x_g0_um": x_g0,
        "x_g1_um": x_g1,
        "x_left_um": x_left,
        "x_right_um": x_right,
        "sim_xmin_um": xmin,
        "sim_xmax_um": xmax,
        "wg_extra_lo_um": wg_lo,
        "wg_extra_hi_um": wg_hi,
        "wg_covers_xmin": wg_lo < xmin,
        "x_fib_mid_um": x_fib_mid,
        "x_fib_um": x_fib,
        "x_fib_offset_um": float(x_fib_offset_um),
        "x_mon_um": x_mon,
        "dl_nm": dl * 1000.0,
        "etch_nm": etch_um * 1000.0,
        "n_cells": int(np.prod(sim.grid.num_cells)),
    }
    if not geom["wg_covers_xmin"]:
        raise RuntimeError(f"wg_extra {wg_lo} does not cover sim xmin {xmin}")
    return sim, geom


def _ce_from_data(sim_data, wls) -> dict:
    def power(mon_name, direction):
        amps = sim_data[mon_name].amps.sel(mode_index=0, direction=direction)
        vals = np.abs(np.array(amps)) ** 2
        return vals.reshape(-1)

    p_lm = power("wg_left", "-")
    p_lp = power("wg_left", "+")
    p_rm = power("wg_right", "-")
    p_rp = power("wg_right", "+")
    ce_left = p_lm
    ce_right = p_rp
    ce = np.maximum(ce_left, ce_right)
    i1550 = int(np.where(np.isclose(wls, 1.550, atol=1e-6))[0][0])
    return {
        "wavelengths_nm": (np.asarray(wls) * 1000).tolist(),
        "ce_left": ce_left.tolist(),
        "ce_right": ce_right.tolist(),
        "ce": ce.tolist(),
        "il_db": (-10 * np.log10(np.maximum(ce, 1e-16))).tolist(),
        "ce_1550": float(ce[i1550]),
        "il_1550_db": float(-10 * np.log10(max(ce[i1550], 1e-16))),
        "lambda_reported_nm": 1550.0,
        "p_left_minus": p_lm.tolist(),
        "p_left_plus": p_lp.tolist(),
        "p_right_minus": p_rm.tolist(),
        "p_right_plus": p_rp.tolist(),
        "i1550": i1550,
    }


def _run_batch(sims: dict, folder: str) -> dict:
    configure()
    path = RES / folder
    path.mkdir(parents=True, exist_ok=True)
    batch = web.Batch(simulations=sims, verbose=True)
    return batch.run(path_dir=str(path))


def _layouts():
    return {d.short: d for d in all_designs(20)}


def geometry_check() -> dict:
    layouts = _layouts()
    sim, geom = build_sim(layouts["uniform"], dl=0.016, wls=np.array([1.550]))
    print("geometry", json.dumps(geom, indent=2))
    assert geom["wg_covers_xmin"], geom
    assert geom["wg_extra_lo_um"] < geom["sim_xmin_um"], geom
    return geom


def estimate() -> dict:
    configure()
    layout = _layouts()["uniform"]
    out = {"geometry": geometry_check()}
    for dl, nwl, tag in (
        (0.016, 1, "16nm_1wl"),
        (0.016, 7, "16nm_7wl"),
        (0.008, 1, "8nm_1wl"),
        (0.004, 1, "4nm_1wl"),
    ):
        wls = WLS_UM if nwl == 7 else np.array([1.550])
        sim, geom = build_sim(layout, dl=dl, wls=wls, field=False)
        try:
            job = web.Job(simulation=sim, task_name=f"est_{tag}", verbose=False)
            cost = float(job.estimate_cost())
        except Exception as e:
            cost = None
            print("estimate_cost failed", tag, type(e).__name__, str(e)[:300])
        rec = {"dl_nm": dl * 1000, "n_wl": nwl, "n_cells": geom["n_cells"], "est_flex": cost}
        out[tag] = rec
        print(tag, rec)
    (RES / "tidy3d_estimate.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    n_align = 4 * len(ALIGN_OFFSETS_UM)
    n_nom = 4
    n_etch = 4 * 2
    n_conv = 4 * 2
    def g(tag, n):
        c = out.get(tag, {}).get("est_flex")
        return None if c is None else n * c
    budget = {
        "align_16nm": g("16nm_1wl", n_align),
        "nominal_spectra": g("16nm_7wl", n_nom),
        "etch_1wl": g("16nm_1wl", n_etch),
        "conv_8nm": g("8nm_1wl", 4),
        "conv_4nm": g("4nm_1wl", 4),
    }
    known = [v for v in budget.values() if v is not None]
    budget["sum_known"] = sum(known) if known else None
    out["budget"] = budget
    print("budget", budget)
    (RES / "tidy3d_estimate.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def run_align() -> dict:
    layouts = _layouts()
    sims = {}
    meta = {}
    for short, layout in layouts.items():
        for off in ALIGN_OFFSETS_UM:
            name = f"align_{short}_{off:+.1f}".replace("+", "p").replace("-", "m")
            sim, geom = build_sim(
                layout, dl=0.016, wls=np.array([1.550]), x_fib_offset_um=float(off), field=False
            )
            sims[name] = sim
            meta[name] = {
                "design": short,
                "kind": "align",
                "etch_nm": 70.0,
                "x_fib_offset_um": float(off),
                "geom": geom,
            }
    print("align jobs", len(sims))
    data = _run_batch(sims, "tidy3d_align")
    jobs = {}
    best = {}
    for name, sd in data.items():
        ce = _ce_from_data(sd, np.array([1.550]))
        rec = {**meta[name], **ce}
        rec.pop("geom", None)
        rec["geom"] = meta[name]["geom"]
        jobs[name] = rec
        d = rec["design"]
        cur = best.get(d)
        if cur is None or rec["ce_1550"] > cur["ce_1550"]:
            best[d] = {
                "x_fib_offset_um": rec["x_fib_offset_um"],
                "ce_1550": rec["ce_1550"],
                "il_1550_db": rec["il_1550_db"],
            }
        print(name, "IL", f"{rec['il_1550_db']:.3f}", "off", rec["x_fib_offset_um"])
    payload = {"jobs": jobs, "best_offset_um": {k: v["x_fib_offset_um"] for k, v in best.items()}, "best": best}
    (RES / "tidy3d_align.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("best offsets", payload["best_offset_um"])
    return payload


def _load_offsets() -> dict[str, float]:
    path = RES / "tidy3d_align.json"
    if not path.is_file():
        raise RuntimeError("run --align first; tidy3d_align.json is missing")
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: float(v) for k, v in data["best_offset_um"].items()}


def run_compare() -> dict:
    layouts = _layouts()
    offsets = _load_offsets()
    sims = {}
    meta = {}
    for short, layout in layouts.items():
        off = offsets[short]
        sim, geom = build_sim(
            layout, dl=0.016, wls=WLS_UM, x_fib_offset_um=off, field=short in ("uniform", "proposed")
        )
        name = f"nom_{short}"
        sims[name] = sim
        meta[name] = {
            "design": short,
            "etch_nm": 70.0,
            "kind": "nominal",
            "x_fib_offset_um": off,
            "dl_nm": 16.0,
            "geom": geom,
        }
        print(name, "cells", geom["n_cells"], "offset", off)

    for etch_nm in (58.0, 82.0):
        for short, layout in layouts.items():
            off = offsets[short]
            sim, geom = build_sim(
                layout,
                dl=0.016,
                wls=np.array([1.550]),
                etch_um=etch_nm / 1000.0,
                x_fib_offset_um=off,
                field=False,
            )
            name = f"etch{int(etch_nm)}_{short}"
            sims[name] = sim
            meta[name] = {
                "design": short,
                "etch_nm": etch_nm,
                "kind": "etch",
                "x_fib_offset_um": off,
                "dl_nm": 16.0,
                "geom": geom,
            }

    print("compare jobs", len(sims), "includes taillaert etch:", any("taillaert" in k and k.startswith("etch") for k in sims))
    data = _run_batch(sims, "tidy3d_compare_v2")
    results = {
        "jobs": {},
        "wavelengths_nm": (WLS_UM * 1000).tolist(),
        "best_offset_um": offsets,
        "notes": {
            "wg_continuation": "full-height Si through -x PML",
            "alignment": "x_fib maximised at 1550 nm on 16 nm grid; frozen for etch and spectra",
            "etch_includes": list(DESIGNS),
        },
    }
    for name, sd in data.items():
        w = WLS_UM if meta[name]["kind"] == "nominal" else np.array([1.550])
        ce = _ce_from_data(sd, w)
        rec = {**meta[name], **ce}
        rec["wg_covers_xmin"] = meta[name]["geom"]["wg_covers_xmin"]
        rec["sim_xmin_um"] = meta[name]["geom"]["sim_xmin_um"]
        rec["wg_extra_lo_um"] = meta[name]["geom"]["wg_extra_lo_um"]
        results["jobs"][name] = rec
        print(name, "IL1550", f"{ce['il_1550_db']:.3f}")
    (RES / "tidy3d_compare.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("wrote", RES / "tidy3d_compare.json")
    return results


def run_converge() -> dict:
    layouts = _layouts()
    offsets = _load_offsets()
    sims = {}
    meta = {}
    for dl in (0.008, 0.004):
        for short, layout in layouts.items():
            off = offsets[short]
            sim, geom = build_sim(
                layout, dl=dl, wls=np.array([1.550]), x_fib_offset_um=off, field=False
            )
            name = f"conv{int(dl*1000)}_{short}"
            sims[name] = sim
            meta[name] = {
                "design": short,
                "etch_nm": 70.0,
                "kind": "convergence",
                "x_fib_offset_um": off,
                "dl_nm": dl * 1000.0,
                "geom": geom,
            }
            print(name, "cells", geom["n_cells"])
    data = _run_batch(sims, "tidy3d_conv")
    results = {"jobs": {}, "best_offset_um": offsets}
    for name, sd in data.items():
        ce = _ce_from_data(sd, np.array([1.550]))
        rec = {**meta[name], **ce}
        rec["n_cells"] = meta[name]["geom"]["n_cells"]
        results["jobs"][name] = rec
        print(name, "IL1550", f"{ce['il_1550_db']:.3f}")
    (RES / "tidy3d_converge.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("wrote", RES / "tidy3d_converge.json")
    return results


def smoke():
    configure()
    from photonic_coupler.gc_designs import make_uniform

    layout = make_uniform(12)
    sim, geom = build_sim(layout, dl=0.016, wls=np.array([1.550]), n_periods=12, field=False)
    print("smoke geom", geom)
    job = web.Job(simulation=sim, task_name="gc_smoke_wgfix_1550", verbose=True)
    data = job.run(path=str(RES / "tidy3d_smoke.hdf5"))
    out = _ce_from_data(data, np.array([1.550]))
    out["geom"] = geom
    print("smoke CE@1550", out["ce_1550"], "IL", out["il_1550_db"], "dB")
    (RES / "tidy3d_smoke.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def campaign():
    t0 = time.time()
    estimate()
    run_align()
    run_compare()
    run_converge()
    print("campaign elapsed", time.time() - t0)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--estimate", action="store_true")
    p.add_argument("--align", action="store_true")
    p.add_argument("--compare", action="store_true")
    p.add_argument("--converge", action="store_true")
    p.add_argument("--campaign", action="store_true")
    args = p.parse_args()
    if args.smoke:
        smoke()
    elif args.estimate:
        estimate()
    elif args.align:
        run_align()
    elif args.compare:
        run_compare()
    elif args.converge:
        run_converge()
    elif args.campaign:
        campaign()
    else:
        p.print_help()
        print("\nDefault is --campaign. Pass a flag.")
        sys.exit(2)


if __name__ == "__main__":
    main()
