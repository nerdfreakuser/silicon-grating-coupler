"""2-D TE FDTD (Ey, Hx, Hz) for an SOI grating coupler.

Polarization is the silicon-photonics TE mode: Ey is out of the xz
plane, the wafer is the xy plane, x is the waveguide, z is the stack.
This is the same 2-D reduction Bozzola, Taillaert, and Lumerical 2-D
FDTD use.

The solver is a Yee grid with a polynomial conductivity PML, a
one-way slab-mode source, and on-the-fly DFTs for the waveguide flux
and the fiber overlap. It is not a replacement for 3-D FDTD; it is the
correct comparison class for the designs in gc_designs.py.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numba import njit, prange

from .constants import SI, SIO2, SOI220, UM
from .gc_designs import GCLayout
from .slab import te_fundamental

C0 = 2.99792458e8
ETA0 = 376.730313461
MU0 = 4.0e-7 * np.pi
EPS0 = 1.0 / (C0 * C0 * MU0)


def _pml_sigma(n: int, n_pml: int, dx: float, m: float = 3.5) -> np.ndarray:
    """Electric conductivity profile, 1-D, zeros in the interior."""
    sig = np.zeros(n, dtype=np.float64)
    # σ_max chosen for ~R < 1e-5 at normal incidence (Taflove).
    sigma_max = 0.8 * (m + 1.0) / (ETA0 * dx)
    if n_pml <= 0:
        return sig
    t = (np.arange(n_pml) + 0.5) / n_pml
    ramp = sigma_max * t**m
    sig[:n_pml] = ramp[::-1]
    sig[-n_pml:] = ramp
    return sig


@njit(cache=True, fastmath=True, parallel=True)
def _step(
    Ey, Hx, Hz,
    cey_a, cey_b,
    chx_a, chx_b,
    chz_a, chz_b,
    nx, nz,
):
    # H update (n+1/2) from E(n)
    for i in prange(nx):
        for k in range(nz - 1):
            Hx[i, k] = chx_a[i, k] * Hx[i, k] + chx_b[i, k] * (Ey[i, k + 1] - Ey[i, k])
    for i in prange(nx - 1):
        for k in range(nz):
            Hz[i, k] = chz_a[i, k] * Hz[i, k] - chz_b[i, k] * (Ey[i + 1, k] - Ey[i, k])
    for i in prange(1, nx - 1):
        for k in range(1, nz - 1):
            curl = (Hx[i, k] - Hx[i, k - 1]) - (Hz[i, k] - Hz[i - 1, k])
            Ey[i, k] = cey_a[i, k] * Ey[i, k] + cey_b[i, k] * curl


@njit(cache=True, fastmath=True)
def _accumulate_dft(Ey, i0, i1, k, re, im, wr, wi):
    for i in range(i0, i1):
        v = Ey[i, k]
        re[i - i0] += v * wr
        im[i - i0] += v * wi


@njit(cache=True, fastmath=True)
def _accumulate_dft_cut(Ey, Hz, i, k0, k1, ey_re, ey_im, hz_re, hz_im, wr, wi):
    for k in range(k0, k1):
        e = Ey[i, k]
        h = Hz[i, k]
        ey_re[k - k0] += e * wr
        ey_im[k - k0] += e * wi
        hz_re[k - k0] += h * wr
        hz_im[k - k0] += h * wi


def slab_ey_profile(z: np.ndarray, z_core_lo: float, t_si: float, wavelength: float) -> np.ndarray:
    """Analytic even-TE Ey(z) of the oxide-clad slab, peak-normalized."""
    mode = te_fundamental(t_si, wavelength, SI.n, SIO2.n)
    k0 = 2.0 * np.pi / wavelength
    kappa = k0 * np.sqrt(SI.n**2 - mode.n_eff**2)
    gamma = k0 * np.sqrt(mode.n_eff**2 - SIO2.n**2)
    zc = z_core_lo + 0.5 * t_si
    u = np.zeros_like(z, dtype=np.float64)
    half = 0.5 * t_si
    core = np.abs(z - zc) <= half
    u[core] = np.cos(kappa * (z[core] - zc))
    clad = ~core
    u[clad] = np.cos(kappa * half) * np.exp(-gamma * (np.abs(z[clad] - zc) - half))
    m = np.max(np.abs(u))
    if m > 0:
        u /= m
    return u, mode.n_eff


@dataclass
class SimGrid:
    dx: float
    nx: int
    nz: int
    x: np.ndarray
    z: np.ndarray
    z_si_lo: float
    z_si_hi: float
    i_src: int
    i_wg: int
    k_fib: int
    n_pml: int
    dt: float


def build_grid(grating_length: float, dx: float = 20e-9, pml_um: float = 1.0) -> SimGrid:
    pml = pml_um * UM
    x_wg = 7.0 * UM
    x_after = 3.5 * UM
    Lx = pml + x_wg + grating_length + x_after + pml
    # z: pml + handle + BOX + Si + clad + pml
    handle = 0.50 * UM
    box = SOI220.t_box
    si = SOI220.t_si
    clad = 3.20 * UM
    Lz = pml + handle + box + si + clad + pml
    nx = int(np.round(Lx / dx))
    nz = int(np.round(Lz / dx))
    x = (np.arange(nx) + 0.5) * dx
    z = (np.arange(nz) + 0.5) * dx
    z0 = pml  # bottom of handle after pml
    z_si_lo = z0 + handle + box
    z_si_hi = z_si_lo + si
    n_pml = int(np.round(pml / dx))
    i_src = n_pml + int(np.round(2.0 * UM / dx))
    i_wg = n_pml + int(np.round(4.0 * UM / dx))
    # Fiber plane ~1.1 um above the Si top, in the oxide.
    k_fib = int(np.round((z_si_hi + 1.20 * UM) / dx))
    k_fib = min(max(k_fib, n_pml + 2), nz - n_pml - 2)
    dt = 0.99 * dx / (C0 * np.sqrt(2.0))
    return SimGrid(dx, nx, nz, x, z, z_si_lo, z_si_hi, i_src, i_wg, k_fib, n_pml, dt)


def _overlap_1d(centers: np.ndarray, dx: float, lo: float, hi: float) -> np.ndarray:
    """Fraction of each cell [c-dx/2, c+dx/2] overlapping [lo, hi]."""
    a = centers - 0.5 * dx
    b = centers + 0.5 * dx
    return np.clip((np.minimum(b, hi) - np.maximum(a, lo)) / dx, 0.0, 1.0)


def build_epsilon(
    grid: SimGrid,
    teeth_abs: np.ndarray,
    t_si: float,
    etch: float,
    n_si: float = SI.n,
    n_ox: float = SIO2.n,
) -> np.ndarray:
    """eps_r(x,z) with volume-weighted (subpixel) Si fill.

    Staircasing a 12 nm etch change on a 25 nm grid is a no-op. Subpixel
    averaging is what makes the manufacturing-tolerance sweeps physical.
    """
    dx = grid.dx
    n_si2, n_ox2 = n_si**2, n_ox**2
    eps = np.full((grid.nx, grid.nz), n_ox2, dtype=np.float64)
    z_handle_lo = grid.n_pml * dx
    z_handle_hi = grid.z_si_lo - SOI220.t_box
    fh = _overlap_1d(grid.z, dx, z_handle_lo, z_handle_hi)
    eps += np.outer(np.ones(grid.nx), fh) * (n_si2 - n_ox2)

    t_remain = max(40e-9, t_si - etch)
    z_lo = grid.z_si_lo
    fz_remain = _overlap_1d(grid.z, dx, z_lo, z_lo + t_remain)
    fz_tooth = _overlap_1d(grid.z, dx, z_lo + t_remain, z_lo + t_si)
    x_g0 = float(teeth_abs[0, 0])
    x_g1 = float(teeth_abs[-1, 1])
    fx_wg = _overlap_1d(grid.x, dx, grid.x[0] - dx, x_g0)
    fx_after = _overlap_1d(grid.x, dx, x_g1, grid.x[-1] + dx)
    fx_grating = _overlap_1d(grid.x, dx, x_g0, x_g1)
    fx_teeth = np.zeros(grid.nx, dtype=np.float64)
    for left, right in teeth_abs:
        fx_teeth += _overlap_1d(grid.x, dx, float(left), float(right))
    fx_teeth = np.clip(fx_teeth, 0.0, 1.0)

    # Waveguide: full t_si. After grating: remaining slab only.
    # Grating grooves: remaining slab. Grating teeth: remaining + tooth sliver.
    fill = (
        fx_wg[:, None] * (fz_remain + fz_tooth)[None, :]
        + fx_after[:, None] * fz_remain[None, :]
        + fx_grating[:, None] * fz_remain[None, :]
        + fx_teeth[:, None] * fz_tooth[None, :]
    )
    fill = np.clip(fill, 0.0, 1.0)
    eps += fill * (n_si2 - n_ox2)
    return eps


def _coefficients(eps_r: np.ndarray, grid: SimGrid):
    dx, dt = grid.dx, grid.dt
    nx, nz = grid.nx, grid.nz
    n_pml = grid.n_pml
    sig_x = _pml_sigma(nx, n_pml, dx)
    sig_z = _pml_sigma(nz, n_pml, dx)
    # Ey at (i,k)
    sig_e = sig_x[:, None] + sig_z[None, :]
    eps = eps_r * EPS0
    cey_a = (1.0 - sig_e * dt / (2.0 * eps)) / (1.0 + sig_e * dt / (2.0 * eps))
    cey_b = (dt / (eps * dx)) / (1.0 + sig_e * dt / (2.0 * eps))
    # Hx at (i, k+1/2): z-PML
    sig_hx = 0.5 * (sig_z[:-1] + sig_z[1:])  # (nz-1,)
    sm_hx = sig_hx * (MU0 / EPS0)  # magnetic conductivity
    chx_a = (1.0 - sm_hx[None, :] * dt / (2.0 * MU0)) / (1.0 + sm_hx[None, :] * dt / (2.0 * MU0))
    chx_b = (dt / (MU0 * dx)) / (1.0 + sm_hx[None, :] * dt / (2.0 * MU0))
    chx_a = np.broadcast_to(chx_a, (nx, nz - 1)).copy()
    chx_b = np.broadcast_to(chx_b, (nx, nz - 1)).copy()
    # Hz at (i+1/2, k): x-PML
    sig_hz = 0.5 * (sig_x[:-1] + sig_x[1:])
    sm_hz = sig_hz * (MU0 / EPS0)
    chz_a = (1.0 - sm_hz[:, None] * dt / (2.0 * MU0)) / (1.0 + sm_hz[:, None] * dt / (2.0 * MU0))
    chz_b = (dt / (MU0 * dx)) / (1.0 + sm_hz[:, None] * dt / (2.0 * MU0))
    chz_a = np.broadcast_to(chz_a, (nx - 1, nz)).copy()
    chz_b = np.broadcast_to(chz_b, (nx - 1, nz)).copy()
    return cey_a, cey_b, chx_a, chx_b, chz_a, chz_b


def _pulse(t, t0, tau, omega):
    return np.exp(-((t - t0) / tau) ** 2) * np.sin(omega * (t - t0))


def run_reference(grid: SimGrid, wavelengths: np.ndarray, t_si: float, nsteps: int | None = None) -> np.ndarray:
    """Straight 220 nm slab: incident waveguide power vs wavelength."""
    eps = np.full((grid.nx, grid.nz), SIO2.n**2, dtype=np.float64)
    z = grid.z
    z_handle_lo = grid.n_pml * grid.dx
    z_handle_hi = grid.z_si_lo - SOI220.t_box
    eps[:, (z >= z_handle_lo) & (z < z_handle_hi)] = SI.n**2
    z_full = (z >= grid.z_si_lo) & (z < grid.z_si_lo + t_si)
    eps[:, z_full] = SI.n**2
    return _run(eps, grid, wavelengths, t_si, store_field=False, fiber=False, nsteps=nsteps)["p_wg"]


def run_gc(
    layout: GCLayout,
    grid: SimGrid,
    wavelengths: np.ndarray,
    t_si: float | None = None,
    etch: float | None = None,
    cd_bias: float = 0.0,
    store_field: bool = False,
    nsteps: int | None = None,
) -> dict:
    t_si = SOI220.t_si if t_si is None else t_si
    etch = SOI220.t_etch if etch is None else etch
    teeth = layout.shifted(grid.x[grid.n_pml] + 7.0 * UM)
    if cd_bias != 0.0:
        # Expand/shrink each tooth about its centre (litho CD bias).
        mid = 0.5 * (teeth[:, 0] + teeth[:, 1])
        half = 0.5 * (teeth[:, 1] - teeth[:, 0]) + 0.5 * cd_bias
        half = np.maximum(half, 20e-9)
        teeth[:, 0] = mid - half
        teeth[:, 1] = mid + half
    eps = build_epsilon(grid, teeth, t_si, etch)
    out = _run(eps, grid, wavelengths, t_si, store_field=store_field, fiber=True, nsteps=nsteps)
    out["teeth"] = teeth
    out["layout"] = layout.short
    return out


def _run(eps, grid: SimGrid, wavelengths: np.ndarray, t_si: float, store_field: bool, fiber: bool, nsteps: int | None = None):
    cey_a, cey_b, chx_a, chx_b, chz_a, chz_b = _coefficients(eps, grid)
    nx, nz, dx, dt = grid.nx, grid.nz, grid.dx, grid.dt
    Ey = np.zeros((nx, nz), dtype=np.float64)
    Hx = np.zeros((nx, nz - 1), dtype=np.float64)
    Hz = np.zeros((nx - 1, nz), dtype=np.float64)

    prof, neff = slab_ey_profile(grid.z, grid.z_si_lo, t_si, SOI220.wavelength)
    # One-way: add Ey and Hz ~ (neff/eta0) Ey. Scale source so numbers are O(1).
    src_scale = 1.0
    omega0 = 2.0 * np.pi * C0 / SOI220.wavelength
    tau = 12e-15
    t0 = 4.0 * tau
    # Time: pulse launch + travel + radiation + a few BOX round-trips
    t_end = t0 + 22e-6 / C0 * 3.5 + 0.45e-12
    n_auto = int(t_end / dt)
    n_auto = max(n_auto, 7000)
    n_auto = min(n_auto, 16000)
    if nsteps is None:
        nsteps = n_auto

    wl = np.asarray(wavelengths, dtype=np.float64)
    omegas = 2.0 * np.pi * C0 / wl
    n_f = len(wl)
    i0 = grid.n_pml
    i1 = nx - grid.n_pml
    n_line = i1 - i0
    ey_fib_re = np.zeros((n_f, n_line), dtype=np.float64)
    ey_fib_im = np.zeros((n_f, n_line), dtype=np.float64)
    hx_fib_re = np.zeros((n_f, n_line), dtype=np.float64)
    hx_fib_im = np.zeros((n_f, n_line), dtype=np.float64)
    k0c = max(1, int(np.round((grid.z_si_lo - 0.4 * UM) / dx)))
    k1c = min(nz - 1, int(np.round((grid.z_si_hi + 0.6 * UM) / dx)))
    n_cut = k1c - k0c
    ey_wg_re = np.zeros((n_f, n_cut), dtype=np.float64)
    ey_wg_im = np.zeros((n_f, n_cut), dtype=np.float64)
    hz_wg_re = np.zeros((n_f, n_cut), dtype=np.float64)
    hz_wg_im = np.zeros((n_f, n_cut), dtype=np.float64)

    # 1550 nm field DFT on a subsampled grid for plots
    k0 = 2.0 * np.pi / SOI220.wavelength
    field_re = field_im = None
    if store_field:
        field_re = np.zeros((nx, nz), dtype=np.float64)
        field_im = np.zeros((nx, nz), dtype=np.float64)

    i_src = grid.i_src
    i_wg = grid.i_wg
    k_fib = grid.k_fib
    hz_imp = neff / ETA0

    for n in range(nsteps):
        t = (n + 0.5) * dt
        _step(Ey, Hx, Hz, cey_a, cey_b, chx_a, chx_b, chz_a, chz_b, nx, nz)
        s = src_scale * _pulse(t, t0, tau, omega0)
        Ey[i_src, :] += s * prof
        wr = np.cos(omegas * t)
        wi = -np.sin(omegas * t)  # e^{-jωt}
        if fiber:
            for iw in range(n_f):
                _accumulate_dft(Ey, i0, i1, k_fib, ey_fib_re[iw], ey_fib_im[iw], wr[iw], wi[iw])
                # Hx lives at k+1/2; use k_fib-1 as the plane just below the Ey line.
                _accumulate_dft(Hx, i0, i1, k_fib - 1, hx_fib_re[iw], hx_fib_im[iw], wr[iw], wi[iw])
        for iw in range(n_f):
            _accumulate_dft_cut(
                Ey, Hz, i_wg, k0c, k1c,
                ey_wg_re[iw], ey_wg_im[iw], hz_wg_re[iw], hz_wg_im[iw],
                wr[iw], wi[iw],
            )
        if store_field:
            wr0 = np.cos(omega0 * t)
            wi0 = -np.sin(omega0 * t)
            field_re += Ey * wr0
            field_im += Ey * wi0

    dt_scale = dt
    ey_fib = (ey_fib_re + 1j * ey_fib_im) * dt_scale
    hx_fib = (hx_fib_re + 1j * hx_fib_im) * dt_scale
    ey_wg = (ey_wg_re + 1j * ey_wg_im) * dt_scale
    hz_wg = (hz_wg_re + 1j * hz_wg_im) * dt_scale
    # Waveguide power from |Ey|^2 and the slab impedance. Avoids Yee
    # half-step quadrature that zeros Re(Ey Hz*). Hz DFT is kept for debug.
    p_wg = 0.5 * (neff / ETA0) * np.sum(np.abs(ey_wg) ** 2, axis=1) * dx

    result = {
        "wavelengths": wl,
        "p_wg": np.abs(p_wg),
        "ey_fib": ey_fib,
        "hx_fib": hx_fib,
        "x_line": grid.x[i0:i1],
        "nsteps": nsteps,
        "dt": dt,
        "dx": dx,
        "k_fib": k_fib,
        "z_fib": grid.z[k_fib],
        "eps": eps,
        "grid": grid,
    }
    if store_field:
        result["field"] = field_re + 1j * field_im
        result["x"] = grid.x
        result["z"] = grid.z
    return result


def fiber_ce(
    ey_line: np.ndarray,
    x: np.ndarray,
    p_in: np.ndarray,
    theta_deg: float,
    mfd: float,
    n_clad: float,
    wavelengths: np.ndarray,
    hx_line: np.ndarray | None = None,
) -> dict:
    """Coupling efficiency vs wavelength, fiber offset actively aligned.

    Upward power is the Poynting flux 1/2 Re(-Ey Hx*) through the monitor
    line (falling back to n|E|^2/2η0 if Hx was not recorded). The fiber
    overlap is the field overlap of Ey with a tilted SMF-28 Gaussian,
    maximized over longitudinal offset — the same degree of freedom a
    probe station uses. CE = (P_up / P_in) * overlap.
    """
    w0 = mfd / 2.0
    n_f = len(wavelengths)
    ce = np.zeros(n_f)
    ov = np.zeros(n_f)
    pup = np.zeros(n_f)
    x0_opt = np.zeros(n_f)
    dx = float(x[1] - x[0])
    theta = np.deg2rad(theta_deg)
    for iw, wl in enumerate(wavelengths):
        e = ey_line[iw]
        # Homogeneous-oxide |E|^2 flux. Yee-staggered Re(E H*) is quadrature
        # unless a half-step phase is applied; |E|^2 is stable for ranking.
        p_up = (n_clad / (2.0 * ETA0)) * float(np.sum(np.abs(e) ** 2) * dx)
        pup[iw] = p_up
        i_pk = int(np.argmax(np.abs(e)))
        x0s = np.linspace(x[i_pk] - 5.0 * UM, x[i_pk] + 5.0 * UM, 101)
        k0 = 2.0 * np.pi / wl
        best_ov = -1.0
        best_x = float(x[i_pk])
        e2 = float(np.sum(np.abs(e) ** 2) * dx)
        for x0 in x0s:
            u = np.exp(-((x - x0) ** 2) / (w0**2)) * np.exp(
                -1j * k0 * n_clad * np.sin(theta) * (x - x0)
            )
            u2 = float(np.sum(np.abs(u) ** 2) * dx)
            num = np.abs(np.sum(np.conjugate(u) * e) * dx) ** 2
            den = e2 * u2
            o = float(num / den) if den > 0.0 else 0.0
            if o > best_ov:
                best_ov = o
                best_x = float(x0)
        ov[iw] = float(np.clip(best_ov, 0.0, 1.0))
        x0_opt[iw] = best_x
        ce[iw] = ov[iw] * p_up / float(p_in[iw]) if p_in[iw] > 0.0 else 0.0
    ce = np.clip(ce, 0.0, 1.0)
    return {
        "ce": ce,
        "il_db": -10.0 * np.log10(np.maximum(ce, 1e-16)),
        "overlap": ov,
        "p_up": pup,
        "p_up_over_pin": pup / np.maximum(p_in, 1e-45),
        "x0_opt": x0_opt,
    }


def index_at_nm(wl_m: np.ndarray, nm: float = 1550.0) -> int:
    """Index of `nm` on a metre-valued wavelength grid.

    numpy.isclose default atol=1e-8 matches 1545 nm to 1550 nm (5e-9 m).
    Require a unique hit within 0.01 nm.
    """
    hit = np.where(np.isclose(np.asarray(wl_m, dtype=float), nm * 1e-9, atol=1e-14, rtol=0.0))[0]
    if len(hit) != 1:
        raise RuntimeError(
            f"{nm:.2f} nm must appear exactly once on the wavelength grid "
            f"{(np.asarray(wl_m, dtype=float) / 1e-9).tolist()}; got {len(hit)} hits. "
            "Do not use numpy.isclose default atol on metre-valued wavelengths."
        )
    return int(hit[0])


def peak_and_bw(wl: np.ndarray, ce: np.ndarray) -> dict:
    i = int(np.argmax(ce))
    peak = float(ce[i])
    wl_peak = float(wl[i])
    # 1 dB bandwidth: ce >= peak * 10^{-0.1}
    thr = peak * 10 ** (-0.1)
    above = np.where(ce >= thr)[0]
    if len(above) >= 2:
        bw = float(wl[above[-1]] - wl[above[0]])
    else:
        bw = 0.0
    i1550 = index_at_nm(wl, 1550.0)
    return {
        "peak_ce": peak,
        "peak_il_db": float(-10.0 * np.log10(max(peak, 1e-16))),
        "wl_peak_nm": wl_peak / 1e-9,
        "bw_1db_nm": bw / 1e-9,
        "ce_1550": float(ce[i1550]),
        "lambda_ce_nm": 1550.0,
    }
