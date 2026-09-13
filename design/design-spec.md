# Design specification: yield-aware grating coupler on 220 nm SOI

**Status:** Draft, 13 September 2026  
**Companion:** `paper/manuscript.md` (physics and claims)  
**Code:** `analysis/photonic_coupler/`  
**This document is the implementation spec.** It is written so an engineer can build the FDTD loop, the GDS, and the MPW without rereading the paper.

---

## Overview

Single-device, single-process pipeline:

1. Analytic period / DRC / yield (done; `analysis/run_study.py`).
2. 2-D FDTD verification of the analytic ranking.
3. Adjoint inverse design with a density filter, Heaviside projection, and a CVaR process batch.
4. GDS of a focusing coupler plus PDK reference loopbacks.
5. One AIM (or Cornerstone / imec) MPW.

The coupler is a C-band TE focusing grating on 220 nm SOI, 70 nm shallow etch, oxide clad, 8° SMF-28.

## Goals

- Beat the AIM PDK TE vertical coupler (~2.8 dB, ~30 nm 1 dB BW) by ≥ 0.20 dB in paired on-wafer loopbacks.
- Hold \(P(\mathrm{IL}(1550\,\mathrm{nm})\le 2.5\,\mathrm{dB})\ge 0.80\) in the process model, then confirm empirically.
- Keep 1 dB bandwidth ≥ 25 nm and on-chip reflection < −12 dB.
- Stay inside 150 nm min CD / min space, single shallow etch, no back-reflector, no extra deposited overlay unless the PDK already has it.

## Non-goals

- Sub-0.5 dB on this stack (physics floor is ~1.9 dB without a mirror; see the paper).
- Quantum, cryogenic, 256-channel PIC, TCO, or dual-use write-ups.
- Claiming validation before FDTD and MPW exist.

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| Device | Focusing GC, TE, 1550 nm, 8° | Wafer-probeable; PDK baseline exists |
| Stack | 220 nm / 2 µm BOX / 70 nm etch | Public MPW |
| Min CD | 150 nm | 193 nm DUV, conservative vs 120 nm PDKs |
| Objective | \(\mathbb{E}[\mathrm{IL}]\) + 0.35 CVaR\(_{0.9}\) | Chance constraint without fake convexity |
| Spec | 2.5 dB @ 80% yield | Above the model mean (2.42 dB); below PDK |
| Parameterization | Linear fill apodization first; then filtered density | Splines after FDTD shows they help |
| Experiment | One MPW, paired loopbacks, device-level stats | 91 devices/arm powers a 50 vs 70% yield test |
| Solver | Tidy3D or Meep 2-D, then 3-D on the winner | 2-D is the Bozzola comparison class |

## Alternatives considered

1. **Edge coupler.** Better IL and bandwidth, no wafer-level test. Rejected because the original problem was a *coupler that foundries actually ship as a GC*, and because MPW learning requires die-on-wafer probing.
2. **Backside metal / DBR.** Gets you to ~0.5–0.7 dB (Benedikovic, Huang). Rejected for v1 because AIM/Cornerstone passive MPWs do not give you a designer-controlled handle mirror. Revisit if the PDK has a poly-Si overlay (imec, some AIM layers).
3. **340 nm SOI.** Bozzola’s −0.5 dB no-mirror result. Rejected because it is not the 220 nm MPW. A Cornerstone 340 nm run is a valid *second* paper.
4. **Scalarized \(\omega_1 L-\omega_2 Y+\omega_3 T+\omega_4 P\).** Rejected: mixed units, non-convex, DRC is not a soft term.
5. **Topology optimization without a filter.** Rejected: produces sub-100 nm blobs that fail DRC and overfit the simulator.

## Process stack (lock these in the FDTD material file)

```
air or oxide   n = 1.000 or 1.444
------------------------------------------------------------  z = 220 nm
Si device      n = 3.476 @ 1550 nm, 220 nm, Palik/Li
------------------------------------------------------------  z = 0
BOX            n = 1.444, 2.00 µm
------------------------------------------------------------  z = -2.00 µm
Si handle      n = 3.476, 2 µm in the sim (or PML)
```

Partial etch: grooves go from z = 220 nm down to z = 150 nm. Unetched bars remain 220 nm.

Fiber: Gaussian, 10.4 µm 1/e² intensity diameter, injected at 8° from normal in the cladding, polarized Ey (TE). Offset along the grating is a free parameter (~3.6 µm from the first tooth in the analytic apodized design).

## Geometry parameterization

### v0 — linear fill (already implemented)

- Period from phase match at the mean fill, then chirp \(\Lambda(z)=\lambda/(n_B(f(z))-n_c\sin\theta)\) so the radiation angle stays 8°.
- \(f(z)=f_s+(f_e-f_s)(z/L)\), \(f_s=0.759\), \(f_e=0.241\), \(L=12\,\mu\mathrm{m}\) (analytic optimum).
- Focusing curves from the confocal formula. Width 14 µm.

### v1 — filtered density (FDTD)

- Design region 14 µm (y) × 16 µm (z), 20 nm pixels.
- Density \(\rho\in[0,1]\), conic filter radius 75 nm, Heaviside \(\beta\) ramped 1 → 32.
- Projection onto the 70 nm etch layer only (the 220 nm slab is not a free variable).
- Min CD enforced by the filter; run DRC on the 0.5 contour before GDS.

### v2 — spline (only if v1 beats v0 by < 0.1 dB, for foundry compactness)

- 8–12 control points on \(f_i, \Lambda_i\).
- A compact spline is a *compression of a legal FDTD design*, not a substitute for one.

## FDTD protocol (2-D, then 3-D)

**Grid.** 8 nm max, 4 nm in the grating. Courant 0.99. Run until the fiber monitor decays 40 dB from peak.

**Sources / monitors.**

- Forward: mode source in a 500 nm strip, 20 µm before the taper.
- Fiber monitor: 12 µm wide, 1.5 µm above the cladding, 8° tilted, overlap with SMF-28.
- Reflection: mode monitor on the strip.
- Transmission past the grating (loss into the slab): mode + power.
- Substrate power: power monitor in the handle.

**Sweeps, in this order.**

1. Uniform \(f=0.5\), \(\Lambda=622\) nm, 20 periods. Expect IL ≈ 2.7 dB if the model is right; Bozzola uniform was −2.7 dB at 80 nm etch. Record the delta and *recalibrate* `eta_2d` if it is > 0.3 dB off.
2. Analytic apodization of §v0. Expect ~2.3 dB.
3. Fiber offset ±4 µm, angle ±2°.
4. Etch ±10 nm, \(t_\mathrm{Si}\) ±6 nm (3σ).
5. Adjoint loop, 150–300 iterations, β continuation, 20-point process batch every 20 iterations for CVaR.
6. 3-D of the winner only (focusing), ~14 × 16 × 4 µm domain.

**Stop.** If 2-D adjoint cannot beat the analytic apodization by 0.15 dB, ship the apodization. Inverse design is not obligatory.

## Yield model (already in code)

`ProcessModel` in `yield_mc.py`. Do not invent new sigmas without a PCM citation. If the foundry gives a PCM report, replace the defaults and re-run `run_study.py`.

Chance constraint evaluation: 2500-draw Monte Carlo, Clopper–Pearson interval on \(k/n\).

## Layout (GDS)

Cell `GC_TE_C_8DEG` :

- Focusing grating, 25 lines, 14 µm width.
- Linear taper 500 nm strip → 14 µm over 150 µm (adiabatic; do not inverse-design the taper in v1).
- Loopback: GC → 100 µm strip → GC, two copies mirrored for fiber-array pitch 127 µm.
- Labels, alignment crosses, and a 1-D period ladder (600 to 640 nm, 5 nm steps) for angle calibration.

PDK reference: instance the foundry TE GC with the same loopback, same pitch, same die coordinates ±1 mm (to share SOI thickness).

## Observability / PCM

On every die: CD SEM target (line/space 310/310 nm), unpatterned Si thickness window, and a 1 mm spiral for waveguide loss. Without these, a 0.2 dB “win” is indistinguishable from a thickness gradient.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| 2-D model optimistic vs 3-D | High | Recalibrate before inverse design; 3-D the winner |
| Etch-depth mean shift (foundry bias) | High | Period ladder; design 3 periods around 622 nm |
| Fiber array angle not 8° | Medium | Angle PCM; report IL at the measured angle |
| Inverse design overfits the simulator | High | Process batch in the loop; min CD filter |
| MPW slip / PDK change | Medium | Freeze PDK version in the tapeout checklist |
| Claiming 0.5 dB anyway | Career | Do not |

## Open questions (need a human)

1. **Which MPKs?** AIM passive 220 nm vs Cornerstone 220 nm vs imec iSiPP. Recommendation: AIM if you want the 2.8 dB published PDK cell as a paired control; Cornerstone if you want 340 nm as a second split.
2. **Poly-Si overlay?** If the PDK has it, v1.1 should use it. That is the Roelkens/imec path to ~1.5 dB measured, and it is still foundry-legal.
3. **O-band instead of C-band?** Datacenter DR8 is O-band. The math is the same; the period shrinks. Decide before FDTD.

## Rollout (code / paper, not silicon)

See **PR Plan** below. Silicon rollout is the MPW protocol in `mpw-protocol.md`.

## PR Plan

### PR1 — Analytic kit (this repo, already started)

- Files: `analysis/photonic_coupler/*`, `analysis/run_study.py`
- No dependencies
- Slab solver, phase match, leaky-wave, thermal, Monte Carlo, Sobol, figures, `study.json`
- Merge when `python analysis/run_study.py` exits 0 and the sanity tests in `analysis/tests/test_sanity.py` pass

### PR2 — GDS emitter

- Files: `layout/gc_focusing.py` (gdstk), `layout/loopback.py`
- Depends on PR1 (period, fill samples, confocal curves)
- Emits `gc_te_c_8deg.gds` plus a PDK-placeholder cell
- Independently reviewable: open in KLayout, DRC with a 150 nm width/space deck

### PR3 — FDTD driver

- Files: `fdtd/tidy3d_gc.py` or `fdtd/meep_gc.py`, `fdtd/adjoint_loop.py`
- Depends on PR1
- Uniform / apodized / adjoint, writes spectra to `fdtd/results/`
- Merge when uniform IL is within 0.4 dB of 2.70 dB *or* a documented recalibration of `eta_2d` is committed

### PR4 — Tapeout deck

- Files: `tapeout/aim_25mm2/`  (or cornerstone), `tapeout/checklist.md`
- Depends on PR2, PR3
- Places 100+100 loopbacks, period ladder, PCM
- Merge when a second person has run DRC and density

### PR5 — Measurement notebook

- Files: `measure/osa_loopback.py`, `measure/stats.py`
- Depends on PR4 (device map)
- Paired t-test, Clopper–Pearson yield, die-level spatial plot
- No silicon dependency to merge; needs a dry-run on synthetic spectra
