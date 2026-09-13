# Silicon grating coupler — technical report and design kit

**Live lab notebook (GitHub Pages):** https://nerdfreakuser.github.io/silicon-grating-coupler/  
**Source:** https://github.com/nerdfreakuser/silicon-grating-coupler

C-band TE fibre-to-chip grating couplers on a public 220 nm SOI MPW stack. One device, one process, analytic ranking, in-house 2-D FDTD, independent Tidy3D, honest claims.

## Read this first

| Document | What it is |
|---|---|
| [`paper/manuscript.md`](paper/manuscript.md) | The technical report (canonical source) |
| [`paper/Photonic_Coupler_Technical_Report.pdf`](paper/Photonic_Coupler_Technical_Report.pdf) | Typeset 11-page report with figures |
| [`design/design-spec.md`](design/design-spec.md) | Implementation spec, FDTD protocol, PR plan |
| [`design/Design_Specification.pdf`](design/Design_Specification.pdf) | Typeset design spec |
| [`design/mpw-protocol.md`](design/mpw-protocol.md) | Device-level MPW experiment that can be bought |
| [`analysis/results/study.json`](analysis/results/study.json) | Analytic numbers |
| [`analysis/results/fdtd_compare.json`](analysis/results/fdtd_compare.json) | In-house 2-D FDTD head-to-head |
| [`analysis/results/tidy3d_compare.json`](analysis/results/tidy3d_compare.json) | Tidy3D 2-D, exact 1550.00 nm |
| [`paper/FDTD_Comparison.pdf`](paper/FDTD_Comparison.pdf) | FDTD results note with figures |
| [`analysis/figures/em07_verdict.png`](analysis/figures/em07_verdict.png) | One-page in-house FDTD verdict |
| [`analysis/figures/td00_spectra_etch.png`](analysis/figures/td00_spectra_etch.png) | Tidy3D spectra + etch (chirp included) |

## Headlines (from `python analysis/run_study.py`)

- 220 nm SOI, 70 nm shallow etch, 8°, SMF-28, min CD 150 nm.
- Phase-match period **622 nm**. DRC fill window **[0.24, 0.76]**.
- Uniform grating **2.70 dB** (calibrated to Bozzola 2015 2-D FDTD). Linear apodization **2.26 dB** nominal.
- Process Monte Carlo: mean **2.42 dB**, σ **0.15 dB**.
- **Tidy3D 2-D, aligned, waveguide through −x PML:** at 16 nm / 1550.00 nm uniform **2.66 dB**, proposed 2.76, chirp 2.84, Taillaert 2.85. Fill-only is the *worst* 58 nm cell (3.69 dB); chirp ≈ proposed under-etch. 16→8→4 nm: uniform stable (2.69 dB at 4 nm); proposed drifts 2.76→2.99 dB. Do not start adjoint.
- **In-house 2-D FDTD, on-grid 1550.00 nm:** uniform **2.63 dB**, proposed 2.74 dB, chirp 2.76 dB, Taillaert 2.94 dB. 1525 nm shoulder: proposed 4.37 vs uniform 5.30 dB. Under-etch 58 nm: proposed 3.52 / chirp 3.55 vs uniform 3.82 dB. Do not average with Tidy3D.
- **Yield at 0.5 dB: 0%** (uncapped leaky-wave mean 2.42 dB; Bozzola published ceiling 1.9 dB — not a 65% Python clamp). Yield at 2.5 dB: 79%.
- \(d\lambda/dT=0.067\) nm/K. Extra IL for a 20 K swing at fixed laser wavelength: **0.003 dB**, not 0.01 dB/°C.
- Coupler IL is worth ~**1 pJ/bit** on a 15 pJ/bit module, not a 70–90% energy cut versus copper.
- Powered experiment: **~90 devices per arm** on one AIM 25 mm² MPW (~$30k), not 100 wafers.

Sub-0.5 dB published couplers use a **back-reflector, overlay, 340 nm SOI, or topological UGRs**. That is a different process than this one.

## Run

```
cd photonic
python analysis/run_study.py
python analysis/run_em_compare.py          # uses cache; --rerun to recompute FDTD
python analysis/run_tidy3d_compare.py      # Flexcompute; needs TIDY3D_API_KEY in repo .env
python analysis/tests/test_sanity.py
python gui/app.py                          # http://127.0.0.1:8765
python gui/build_pages.py                  # static snapshot -> docs/ (GitHub Pages)
```

Requires numpy, scipy, matplotlib. `analysis/requirements.txt` lists them. Tidy3D is optional; the batch result is already in `analysis/results/tidy3d_compare.json`. Do not commit a Tidy3D API key; `.env` is gitignored.

## What this is not

It is not a fabricated device. It is not a 3-D FDTD inverse-design result. The independent 2-D ranking is Tidy3D (§9.1 of the manuscript). The remaining jobs are adjoint inverse design with under-etch samples, then one MPW of paired loopbacks against the PDK cell.
