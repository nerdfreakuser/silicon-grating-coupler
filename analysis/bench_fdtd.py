"""Smoke-test the 2-D FDTD on a coarse grid."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

from photonic_coupler.constants import SOI220
from photonic_coupler.fdtd2d import build_grid, fiber_ce, peak_and_bw, run_gc, run_reference
from photonic_coupler.gc_designs import make_proposed, make_uniform


def main():
    dx = 40e-9
    wl = np.array([1.53e-6, 1.55e-6, 1.57e-6])
    u = make_uniform(16)
    print("uniform length_um", u.length * 1e6, "period_nm", u.period_mean * 1e9, "nteeth", u.n_teeth)
    grid = build_grid(u.length, dx=dx, pml_um=0.8)
    print("grid", grid.nx, "x", grid.nz, "dt_fs", grid.dt * 1e15, "n_pml", grid.n_pml)
    t0 = time.time()
    print("compiling + reference...")
    pin = run_reference(grid, wl, SOI220.t_si, nsteps=8000)
    print("  pin", pin, "elapsed", time.time() - t0)
    t1 = time.time()
    print("uniform GC...")
    out = run_gc(u, grid, wl, store_field=False, nsteps=8000)
    ce = fiber_ce(out["ey_fib"], out["x_line"], pin, SOI220.theta_deg, SOI220.mfd, SOI220.cladding.n, wl, hx_line=out.get("hx_fib"))
    print("  CE", ce["ce"], "IL", ce["il_db"], "ov", ce["overlap"], "Pup/Pin", ce["p_up_over_pin"], "elapsed", time.time() - t1)
    t2 = time.time()
    print("proposed GC...")
    p = make_proposed(16)
    outp = run_gc(p, grid, wl, store_field=False, nsteps=8000)
    cep = fiber_ce(outp["ey_fib"], outp["x_line"], pin, SOI220.theta_deg, SOI220.mfd, SOI220.cladding.n, wl, hx_line=outp.get("hx_fib"))
    print("  CE", cep["ce"], "IL", cep["il_db"], "ov", cep["overlap"], "Pup/Pin", cep["p_up_over_pin"], "elapsed", time.time() - t2)
    print("total", time.time() - t0)


if __name__ == "__main__":
    main()
