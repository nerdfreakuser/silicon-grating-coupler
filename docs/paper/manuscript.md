# Foundry-Constrained Yield-Aware Design of Silicon Grating Couplers

**A technical report replacing an LLM-generated “validated framework”**

13 September 2026  
Source: `F:\Repos\Engineering\photonic`  
Status: analytic study, in-house 2-D FDTD, and an independent Tidy3D 2-D check at exact 1550.00 nm. **No devices have been fabricated. No adjoint inverse-design loop has been run.**

---

## Abstract

We reformulate the design of a C-band TE fiber-to-chip grating coupler as a **foundry-constrained, chance-constrained** electromagnetic problem on a single, public process: 220 nm silicon-on-insulator (SOI), 70 nm shallow etch, 2 µm buried oxide, 150 nm minimum critical dimension, 8° fiber in an oxide cladding, SMF-28. The Maxwell problem is non-convex. PDK rules are hard constraints, not a fourth term in a weighted sum. Yield is the probability that insertion loss (IL) at 1550 nm stays below a specification under published within-wafer variation, not a wafer-level binomial of 50 production lots.

A 1-D slab-mode plus leaky-wave model, calibrated so a uniform grating matches the 53.7% 2-D FDTD result of Bozzola et al. (2015), gives:

- phase-match period **Λ = 622 nm** at 50% fill (\(n_\mathrm{eff}=2.694\));
- DRC-legal fill window **[0.241, 0.759]**;
- linear fill apodization to **2.26 dB** nominal IL (59.4% coupling), versus **2.70 dB** uniform;
- process Monte Carlo (\(n=2500\)): mean IL **2.42 dB**, \(\sigma=0.15\) dB;
- **yield at IL ≤ 0.5 dB is zero.** Yield at IL ≤ 2.5 dB is 78.7% (Clopper–Pearson 95% CI 77.0–80.3%);
- thermo-optic walk \(d\lambda/dT = 0.067\,\mathrm{nm/K}\). Extra IL at a fixed laser wavelength after a 20 K swing is **0.003 dB**, not 0.01 dB/°C;
- taking a 15 pJ/bit 800G module with 25% laser share, improving both couplers from a 2.8 dB PDK cell to 2.26 dB saves **5.5% of module energy** (0.83 pJ/bit). Even the counterfactual 3.0 dB → 0.3 dB saves 18%, not 70–90%.

The 0.3 dB / 70% yield target of the earlier draft is below the published physics floor of **−1.9 dB (65%)** for 220 nm SOI *without* a back-reflector. That 65% figure is Bozzola’s published 2-D FDTD result; it is not a `min()` applied to this model. Uncapped leaky-wave sits at 2.26 dB apodized. Independent Tidy3D 2-D FDTD (§10.1), with the waveguide continued through the −x PML and the fiber aligned at 1550.00 nm, finds **uniform still best** (2.66 dB at 16 nm, 2.69 dB at 4 nm). Proposed is 2.76 dB at 16 nm and **drifts to 2.99 dB at 4 nm**. Fill-only is the worst 58 nm cell (3.69 dB); chirp-only matches proposed under-etch. This is not a 0.5 dB champion and not a uniqueness proof for fill+chirp. Adjoint inverse design is not next.

An MPW experiment that can actually be bought is ~100 loopback copies of a candidate versus the PDK cell on **one AIM Photonics 25 mm² reticle** (member list price on the order of $30k for 20 chips), not 100 wafers at two logic nodes. The experimental unit is a device, not a wafer.

Analytic numbers come from `analysis/run_study.py`. In-house FDTD from `analysis/run_em_compare.py`. Tidy3D from `analysis/run_tidy3d_compare.py`. The code, not the prose, is the claim.

---

## 1. Scope

The previous documents in this folder (archived under `archive-llm-drafts/`, PDF metadata: Author = “ChatGPT Canvas”) described a “validated, multi-foundry, AI-driven coupler framework” targeting <0.5 dB at ≥70% yield, with a 2×2 factorial on TSMC 7 nm versus Intel 45 nm, 50 wafers per fab, and a $500k budget. They contained no geometry, no Maxwell solve, no process model, and no original data. Several citations were attached to the wrong papers. That draft is not a starting point for a paper; it is a list of *topics* that a paper might address.

This report does four things the draft did not:

1. Pick **one** device and **one** process that a graduate student or a small lab can design to.
2. Write the optimization problem with the right objects (fields, chance constraints, DRC).
3. Compute everything that can be computed without a 3-D FDTD licence, and say so.
4. Size an experiment that exists on a price list.

Non-goals: quantum modulators, cryogenic loops, 256-channel thermal crosstalk, datacenter TCO, export-control essays, and any statement that this pipeline has been “validated at scale.”

---

## 2. Device and process

### 2.1 Why a grating coupler, and why 220 nm SOI

Fiber-to-chip coupling is the loss term that shows up twice in every packaged link and once in every wafer-scale test. Edge couplers can be better (and are the right choice for some products) but they do not allow wafer-level probing. Grating couplers do. That is why PDKs ship them and why inverse-design papers keep returning to them.

220 nm SOI with a ~70 nm shallow etch is the default of AIM Photonics, imec iSiPP, AMF, and Cornerstone. It is **not** TSMC N7 and **not** Intel 45 nm CMOS. TSMC’s silicon-photonics offering is a 65 nm-class photonics flow plus COUPE packaging. Intel’s is a dedicated 300 mm photonics line. GlobalFoundries has used a 45 nm SOI *electronics* node for monolithic photonics; that is a different sentence. Shipping the same coupler mask to “TSMC 7 nm and Intel 45 nm” is not a generalization study.

### 2.2 Fixed stack

| Quantity | Value | Source |
|---|---|---|
| Si device | 220 nm | photonics-grade SOI |
| BOX | 2.0 µm | typical |
| Shallow etch | 70 nm (150 nm remaining) | standard GC etch |
| Cladding | SiO₂, \(n=1.444\) at 1550 nm | |
| Fiber | SMF-28, MFD 10.4 µm at 1550 nm | |
| Angle | 8° in the cladding | detunes 2nd-order Bragg |
| Polarization | TE | PDK TE vertical coupler |
| Min CD / min space | 150 nm | 193 nm DUV, conservative |
| Wavelength | 1550 nm | C-band |

AIM Photonics’ TE vertical coupler is specified at **~2.8 dB/facet** to SMF-28e with a **~30 nm** 1 dB bandwidth (Analog Photonics / Fahrenkopf, OFC 2018 and the 2022 MPW description). imec iSiPP200 quotes SMF grating couplers **< 2 dB**. Those are the baselines to beat, not 0.3 dB.

### 2.3 What “< 0.5 dB” actually requires

Published coupling efficiencies, with the process trick named:

| Result | IL | Process trick | Status |
|---|---|---|---|
| AIM PDK TE GC | ~2.8 dB | standard 220 nm, no mirror | measured |
| Bozzola et al., Opt. Express 23, 16289 (2015) | **−1.9 dB (65%)** | 220 nm, apodized, **no** mirror | 2-D FDTD ceiling |
| Same paper | −0.5 dB | **340 nm** SOI, no mirror | 2-D FDTD |
| Benedikovic et al., Opt. Express 23, 22628 (2015) | −0.69 dB | SWG + **backside metal** | measured |
| Wang et al., Sci. Adv. 10, eadn4372 (2024) | −0.34 dB | topological unidirectional resonances on **340 nm** SOI | measured |
| Huang & Barz, Sci. Rep. 15, 2925 (2025) | −0.35 dB | inverse design + **bottom reflector**, 220 nm | simulated |
| Valdez et al., arXiv:2506.19242 | −0.69 dB | three-wave interaction, foundry 220 nm | measured |

The 220 nm, no-reflector, DUV-legal ceiling is **about −1.9 dB in 2-D FDTD**, and worse once 3-D, min-CD, and fiber mismatch are included. A production spec of 0.3 dB on this stack is not ambitious. It is forbidden by the stack.

---

## 3. Electromagnetic model

### 3.1 Slab modes of the two grating sections

The unetched (220 nm) and shallow-etched (150 nm) sections are symmetric oxide/Si/oxide slabs. Even TE modes satisfy

\[
\kappa\sin(\kappa d/2)-\gamma\cos(\kappa d/2)=0,
\]

with \(\kappa=k_0\sqrt{n_\mathrm{Si}^2-n_\mathrm{eff}^2}\) and \(\gamma=k_0\sqrt{n_\mathrm{eff}^2-n_\mathrm{ox}^2}\). Using \(n_\mathrm{Si}=3.476\) and \(n_\mathrm{ox}=1.444\) at 1550 nm:

| Section | \(d\) | \(n_\mathrm{eff}\) | \(n_g\) | \(\Gamma_\mathrm{Si}\) |
|---|---|---|---|---|
| Unetched | 220 nm | 2.848 | 3.577 | 0.810 |
| Etched | 150 nm | 2.539 | 3.401 | 0.655 |

The Bloch index of a rectangular grating is the duty-cycle average (standard first-order design formula)

\[
n_\mathrm{B}(f)=f\,n_\mathrm{unetch}+(1-f)\,n_\mathrm{etch}.
\]

At \(f=0.5\), \(n_\mathrm{B}=2.694\).

### 3.2 Phase matching

First-order diffraction into the cladding at angle \(\theta\) requires

\[
\Lambda=\frac{\lambda}{n_\mathrm{B}-n_\mathrm{c}\sin\theta}.
\]

At \(\theta=8^\circ\), \(\Lambda=622\,\mathrm{nm}\). Tooth and groove must both be ≥ 150 nm, so

\[
f\in[150/\Lambda,\,1-150/\Lambda]=[0.241,\,0.759].
\]

Apodization that asks for \(f=0.05\) is not a PDK-legal design; it is a drawing.

Focusing (in-plane) grating lines that share a focus at the waveguide end obey the confocal construction

\[
m\lambda=n_\mathrm{B}\sqrt{x^2+y^2}-x\,n_\mathrm{c}\sin\theta.
\]

That geometry is generated by `focusing_grating_curves` and is the layout that should go to GDS, not a 1-D bar array.

### 3.3 Coupling budget

Following Taillaert / Roelkens / Benedikovic we factor

\[
\eta=D\cdot\eta_\parallel\cdot\eta_{2\mathrm{D}}\cdot(1-R)\cdot\eta_\mathrm{taper}.
\]

- \(D\) is upward directionality. A two-beam model of the BOX/handle reflection, with intrinsic up-fraction 0.62 for a 70 nm partial etch, gives **\(D=0.725\)** at 2.0 µm BOX. \(D\) oscillates with BOX thickness on a ~0.54 µm period; 2.0 µm is not a magic number, it is the wafer we are given.
- \(\eta_\parallel\) is the overlap of the radiated near-field along \(z\) with the SMF-28 Gaussian (\(w_0=\mathrm{MFD}/2=5.2\,\mu\mathrm{m}\)). A uniform grating radiates \(\propto e^{-\alpha z}\) with \(\alpha\approx 0.11\,\mu\mathrm{m}^{-1}\) at 70 nm etch and 50% fill; the 1-D overlap is 0.87. A linear fill apodization from 0.759 → 0.241 over 12 µm raises it to **0.963**.
- \(\eta_{2\mathrm{D}}=0.871\) is a single calibration constant that puts the *uniform* device on Bozzola’s 53.7% 2-D FDTD point. It accounts for the y-overlap and the fact that the 2-D wavefront is not a perfect Gaussian. It is not a free parameter per design.
- \(R\) is second-order Bragg reflection, ~18% at \(\theta=0\) and **0.33% at 8°**. That is why the fiber is tilted.
- \(\eta_\mathrm{taper}=0.98\) is a long adiabatic taper, not a result.

This produces:

| Design | \(\eta\) | IL |
|---|---|---|
| Uniform, 50% fill | 53.7% | **2.70 dB** |
| Linear apodization, DRC-legal | 59.4% | **2.26 dB** |
| Bozzola unconstrained 220 nm FDTD ceiling | 65% | 1.90 dB |
| AIM PDK TE GC (measured) | ~52% | ~2.8 dB |

The model is anchored, not fitted, at the uniform point. The apodized 2.26 dB sits between the PDK cell and Bozzola’s unconstrained ceiling, which is where a DRC-limited 1-D apodization *should* sit. A 2-D adjoint inverse design can still pick up the remaining ~0.3 dB by shaping individual teeth, and that is the actual job of FDTD.

### 3.4 What this model is not

It is not a substitute for 2-D/3-D FDTD or RCWA. It does not capture the exact radiation angle versus etch, the poly-Si overlay degree of freedom, or substrate higher-order reflections. It *is* enough to (i) size the period and DRC window, (ii) show that 0.5 dB is impossible on this stack **without clamping the model to Bozzola’s 65%** (uncapped leaky-wave is 2.26 dB; Bozzola’s published 2-D FDTD ceiling is 1.9 dB; Tidy3D peaks sit near 3.1 dB), (iii) propagate process error into yield, and (iv) write a correct optimization problem for the FDTD loop.

---

## 4. The optimization problem, written correctly

Let \(x\) be the design variables (fill samples, spline controls, or a filtered density), \(p\) the process vector, \(E\) the Maxwell field at \((x,p,\lambda)\), and

\[
\eta(x,p;\lambda)=\frac{\bigl|\langle E_\mathrm{out}(x,p,\lambda),\,E_\mathrm{fiber}(\lambda,\theta)\rangle\bigr|^2}{P_\mathrm{in}}.
\]

Insertion loss \(\mathrm{IL}=-10\log_{10}\eta\). The problem we actually want is

\begin{align*}
\underset{x}{\mathrm{minimize}}\quad
&\mathbb{E}_p\bigl[\mathrm{IL}(x,p;\lambda_0)\bigr] \\
\mathrm{subject\ to}\quad
&\mathbb{P}_p\bigl(\mathrm{IL}(x,p;\lambda_0)\le \mathrm{IL}_\mathrm{spec}\bigr)\ge Y_\mathrm{spec}, \\
&\mathrm{BW}_{1\mathrm{dB}}(x,p_\mathrm{nom})\ge 25\,\mathrm{nm}, \\
&R_\mathrm{back}(x,p_\mathrm{nom};\lambda_0)\le 10^{-1.5}, \\
&\mathrm{DRC}(x)=\mathrm{true}.
\end{align*}

Recommended numbers on this stack: \(\mathrm{IL}_\mathrm{spec}=2.5\,\mathrm{dB}\), \(Y_\mathrm{spec}=0.80\). Not 0.3 dB and 70%.

### 4.1 Why the original scalarization is not a formulation

The draft minimized

\[
f(x)=\omega_1 L(x)-\omega_2 Y(x)+\omega_3 T(x)+\omega_4 P(x),\qquad x\in\mathbb{R}^{10\text{–}20}
\]

and invoked KKT conditions, “bandgap invariants,” and Sobol indices in the same paragraph.

- \(L\), \(Y\), \(T\), \(P\) have different units. Without a stated normalization the weights are meaningless.
- FDTD coupler loss is **non-convex**. KKT is a stationarity condition for problems you have already shown are convex. This one is not.
- Yield is a discontinuous functional of process. Subtracting \(\omega_2 Y\) does not make it differentiable.
- PDK rules (min CD, allowed etches, no acute jogs) are **indicators**. They belong in \(\mathrm{DRC}(x)=\mathrm{true}\), or in a density filter plus Heaviside projection (Sigmund / Guest), not in a soft \(\omega_4 P\).
- Bandgap invariants are a topological-photonics tool. They are not a general coupler-stability certificate.

A tractable surrogate, used in `optimize.py`, is sample-average approximation plus CVaR on the upper tail:

\[
\min_x\ \mathrm{IL}(x,p_\mathrm{nom})+\kappa\,\mathrm{CVaR}_{0.9}\bigl[\mathrm{IL}(x,p)\bigr],
\]

with \(x\) the three apodization parameters \((f_\mathrm{start},f_\mathrm{end},L)\) inside the DRC box. A Nelder–Mead pass on that surrogate moved mean IL from 2.42 dB to 2.35 dB and 2.5 dB yield from 79% to 86%. That is a real, small gain. It is not a paper by itself. It is the reduced problem the FDTD loop should also be solving, with \(x\) then the filtered density.

### 4.2 Adjoint gradients, when FDTD is available

For a figure of merit \(J(E,\varepsilon)\) the permittivity derivative at every pixel is available from one forward and one adjoint Maxwell solve (Lalau-Keraly, Bhargava, Miller, Yablonovitch, Opt. Express 21, 21693, 2013):

\[
\frac{\partial J}{\partial\varepsilon(r)}\propto \mathrm{Re}\bigl\{E_\mathrm{fwd}(r)\cdot E_\mathrm{adj}(r)\bigr\}.
\]

The adjoint source is the time-reversed fiber mode at the monitor. Fabrication constraints enter by filtering the density with a conic kernel of radius \(r_\mathrm{min}=75\,\mathrm{nm}\) and projecting with a Heaviside of controllable steepness (Piggott, Opt. Express 2017, fabrication-constrained inverse design). That is the compressed parameterization: after projection the design is a 10–20 number spline *or* a filtered field whose independent degrees of freedom are of order \((\mathrm{area})/(\pi r_\mathrm{min}^2)\), not a 10⁵-pixel blob.

We have not run this loop. The design document specifies it so that it can be run in Tidy3D, Meep, or Lumerical without inventing a new theory.

---

## 5. Thermal behaviour, derived rather than asserted

Phase match at fixed angle and (almost) fixed period:

\[
n_\mathrm{eff}(\lambda,T)-n_\mathrm{c}\sin\theta=\frac{\lambda}{\Lambda}.
\]

Differentiating, and using \(n_g=n_\mathrm{eff}-\lambda\,\partial n_\mathrm{eff}/\partial\lambda\),

\[
\frac{d\lambda}{dT}=\frac{\lambda\bigl(\partial n_\mathrm{eff}/\partial T+n_\mathrm{eff}\,\alpha_\mathrm{Si}\bigr)}{n_g-n_\mathrm{c}\sin\theta}.
\]

With \(\partial n_\mathrm{Si}/\partial T=1.80\times 10^{-4}\,\mathrm{K}^{-1}\) (Komma et al., Appl. Phys. Lett. 101, 041905, 2012), \(\partial n_\mathrm{ox}/\partial T=1.0\times 10^{-5}\,\mathrm{K}^{-1}\), \(\Gamma_\mathrm{Si}=0.733\), \(n_g=3.489\):

\[
\frac{d\lambda}{dT}=0.067\,\mathrm{nm/K}.
\]

That is the same order as a silicon ring (typically 70–80 pm/K). It is **not** a 0.01 dB/°C coupler spec.

A Gaussian-like coupling spectrum of 1 dB full-width \(\Delta_{1\mathrm{dB}}\) has FWHM \(\Delta_{1\mathrm{dB}}/\sqrt{0.1\ln 10/\ln 2}\). Extra IL at the *design* wavelength after a peak walk \(\delta\lambda\) is

\[
\Delta\mathrm{IL}(\mathrm{dB})=\frac{40\ln 2}{\ln 10}\left(\frac{\delta\lambda}{\mathrm{FWHM}}\right)^2
=12.04\left(\frac{\delta\lambda}{\mathrm{FWHM}}\right)^2.
\]

Our 1-D bandwidth estimate is 47 nm (the AIM PDK cell is closer to 30 nm; the 0.07 empirical prefactor is the weak part of the model). Even on a 30 nm 1 dB band, a 20 K swing walks the peak by 1.33 nm and costs **~0.01 dB**. On our 47 nm band it costs **0.003 dB**.

A grating coupler is broadband. Thermal drift of the *peak* is a WDM-alignment problem, not a 0.01 dB/°C IL problem. The linear coefficient “0.01 dB/°C” is the wrong functional form: detuning loss is quadratic in \(\Delta T\).

---

## 6. Yield

### 6.1 Process model

Within-wafer 1-sigma values compiled from 193 nm DUV silicon photonics (ACS Photonics 10, 928, 2023, IMEC/AMF rows) and Chrostowski’s grating-coupler wavelength sensitivities (*Silicon Photonics Design*, CUP 2015, Ch. 11):

| Factor | \(\sigma\) | \(d\lambda/d(\cdot)\) |
|---|---|---|
| Si thickness | 2.0 nm | 1.82 nm/nm |
| Etch depth | 3.0 nm | 1.90 nm/nm |
| CD bias | 2.6 nm | 0.215 nm/nm |
| Fiber angle | 0.4° | (overlap + 0.15 dB/deg²) |
| Fiber offset | 0.8 µm | (overlap) |

IL at 1550 nm is peak IL of the perturbed geometry, plus detuning from wavelength walk, plus a small angular penalty. This is a model of **within-wafer** scatter, not a 3-sigma datasheet limit, and not wafer-to-wafer mean shift (which a foundry will try to bias out).

### 6.2 Monte Carlo (\(n=2500\))

| Statistic | Value |
|---|---|
| Nominal apodized IL | 2.26 dB |
| Mean / median | 2.42 / 2.38 dB |
| \(\sigma\) | 0.15 dB |
| 5th / 95th percentile | 2.27 / 2.74 dB |
| \(P(\mathrm{IL}\le 0.5\,\mathrm{dB})\) | **0** |
| \(P(\mathrm{IL}\le 1.5\,\mathrm{dB})\) | **0** |
| \(P(\mathrm{IL}\le 2.0\,\mathrm{dB})\) | **0** |
| \(P(\mathrm{IL}\le 2.5\,\mathrm{dB})\) | 78.7% (95% CI 77.0–80.3%) |
| \(P(\mathrm{IL}\le 3.0\,\mathrm{dB})\) | 99.4% |

The 0.5 dB target has yield zero because the **uncapped** leaky-wave mean is 2.42 dB, and because Bozzola’s published 2-D FDTD ceiling on this stack is 1.9 dB. Neither number is a Python `min()` that copies 65% into the Monte Carlo. A 2.5 dB specification — 0.3 dB better than the AIM PDK cell, 0.25 dB worse than our mean — is the spec that has a chance of being real.

Jansen first-order Sobol indices of IL: fiber offset 0.37, etch depth 0.26, fiber angle 0.18, \(t_\mathrm{Si}\) 0.11, CD 0.06 (sum 0.98). Alignment and partial-etch depth dominate. That is a measurement-protocol fact (active fiber alignment, etch-depth PCM) as much as a design fact.

---

## 7. Energy, without the category error

An 800G pluggable is ~15 pJ/bit, of which the laser electrical share is ~20–30% (the rest is DSP, drivers, TIA, control). Copper DAC energy (5–10 pJ/bit, short reach) is a *reach* comparison. Coupler IL does not convert copper into photonics.

Laser optical power scales as \(10^{n_c\Delta\mathrm{IL}/10}\) for \(n_c\) couplers in the laser-to-PD path. For a packaged TX+RX pair, \(n_c=2\).

| Change | Laser scale | Fraction of 15 pJ/bit module | Saved |
|---|---|---|---|
| PDK 2.8 dB → this 2.26 dB | 1.28× | **5.5%** | 0.83 pJ/bit |
| PDK 2.8 dB → 0.5 dB (if it existed) | 2.88× | 16% | 2.45 pJ/bit |
| 3.0 dB → 0.3 dB (draft’s setup) | 3.47× | **18%** | 2.67 pJ/bit |

The draft’s “70–90% reduction versus copper, 5–10 pJ/bit → <0.5 pJ/bit” does not follow from a coupler. Sub-pJ/bit transmitters exist (slow-light MZM plus current-mode driver, ring/CPO research) and they get there by killing SERDES and DSP, not by 0.3 dB of grating. A coupler improvement is worth doing. It is worth about **one pJ/bit** on a pluggable, on the numbers above.

---

## 8. An experiment that can be purchased

### 8.1 The unit is a device

The draft used G*Power to get \(n=46\) *wafers* to detect 70% versus 50% yield, rounded to 50 wafers per foundry. Yield of a coupler is measured on devices. A 25 mm² AIM die holds hundreds of 40 µm × 40 µm focusing couplers.

Textbook sizes, \(\alpha=0.05\), 80% power:

| Test | Effect | \(n\) per arm |
|---|---|---|
| Two-proportion, yield 50% vs 70% | 20 points | **91 devices** |
| Two-proportion, 70% vs 90% | 20 points | 59 devices |
| Two-sample \(t\), \(\Delta\mathrm{IL}=0.30\) dB, \(\sigma=0.30\) dB | | **16 devices** |
| Paired \(t\) (same-die PDK vs candidate), \(\sigma_\mathrm{diff}=0.20\) dB | 0.30 dB | **4 pairs** |
| Draft | 50 wafers × 2 fabs | not a test |

Put 100 PDK loopbacks and 100 candidate loopbacks on one reticle, plus a 10-point fill/period sweep of 20 copies each, plus PCM (SEM CD, ellipsometric thickness). That is a powered experiment. It fits in 25 mm².

### 8.2 Budget

AIM Photonics member price for 20 chips of a 25 mm² **passive** PIC is $28,600 at the published volume table (aimphotonics.com/mpw-volume-pricing). Non-member $34,320. Active 25 mm² is about 2.5× that. Masks are in the MPW price. This is the $30k–$80k experiment, not $500k, and it does not require a TSMC N7 NDA.

Falsification: if the candidate’s paired mean IL is not ≥ 0.20 dB better than the PDK cell with a 95% interval excluding zero, the inverse-design claim is false on this process, and that is a publishable negative.

---

## 9. Errata of the archived draft

| Draft claim | Fact |
|---|---|
| “Validated framework,” Green = multi-fab | No data, no geometry, no fab |
| TSMC 7 nm vs Intel 45 nm | Wrong objects. Use AIM / imec / Cornerstone 220 nm SOI |
| 50 wafers × 2, $500k, 6 months | ~100 devices on one MPW, ~$30k |
| IL ≤ 0.3 dB at ≥70% yield | Below the −1.9 dB 220 nm no-mirror floor; yield 0 in this model |
| \(f=\omega_1 L-\omega_2 Y+\omega_3 T+\omega_4 P\), KKT, bandgaps | Non-convex Maxwell + chance constraint + DRC |
| 0.01 dB/°C | 0.067 nm/K walk; 0.003 dB extra IL in 20 K |
| 70–90% energy vs copper from the coupler | ~5–18% of a 15 pJ/bit module, laser share only |
| PMC7407772 for −0.81±0.16 dB on 300 mm wafers | PMC7407772 is a 2019 *review*. The number is Sci. Rep. 14, 53975 (2024), 10 devices on one SiN chip |
| Piggott 2015 “inverse tapers, Luxtera packaging” | A 2.8 µm wavelength demultiplexer |
| Molesky 2018 “5–10 Fourier modes, >95% retention” | A Nature Photonics *review* of inverse design |
| “Vücković” | Vučković |
| arXiv:2404.06117 as a wafer-scale *coupler* | An imec bent **directional coupler / 2×2 splitter** |
| Self-review appendix, “85% publication-ready” | The generator grading itself |
| PDF Author: ChatGPT Canvas | File properties |

The *topic* (fab-aware, compressed, yield-aware inverse design of couplers) remains a good thesis. The draft was not a paper on that topic.

---

## 10. 2-D FDTD: proposed vs strong baselines, identical constraints

The leaky-wave model in §3 is a ranking tool, not a Maxwell solve. This section is the Maxwell solve. Four layouts share the **same** 220 nm / 70 nm / 2 µm stack, the **same** 150 nm min CD, the **same** 8° SMF-28 fiber, and the **same** ~20-period aperture.

| Name | What varies | Role |
|---|---|---|
| Uniform 50% | nothing | PDK-class baseline |
| Linear period chirp | Λ only, fill = 50% | industrial bandwidth design |
| Taillaert fill apodization | fill 0.76 → 0.24, Λ fixed | textbook strong design, DRC-clamped |
| **Proposed** | fill 0.76 → 0.24 **and** Λ(z) so θ stays 8° | this work |

Two solvers:

- In-house Yee 2-D TE FDTD (`analysis/photonic_coupler/fdtd2d.py`), dx = 25 nm, volume-weighted permittivity, out-coupling |E|² cladding overlap with SMF-28. Raw data: `analysis/results/fdtd_compare.json`.
- Flexcompute Tidy3D 2.12, 2-D (y-invariant), Δℓ = 16 nm, subpixel averaging, **in-coupling** GaussianBeam → waveguide ModeMonitor. Wavelength list **contains 1550.00 nm**. Chirp is on the etch sweep. Raw data: `analysis/results/tidy3d_compare.json`.

An earlier write-up labelled tolerance bars “1550 nm” while the in-house grid was 1525, 1535, … 1575 and the code took the nearest bin (1545). Putting 1550.00 on the grid is not enough: `numpy.isclose` with default `atol=1e-8` on a *metre*-valued wavelength array also matches 1545 nm (5×10⁻⁹ m). Indexing now requires a unique hit within 0.01 nm, and a cache whose 70 nm etch row disagrees with the on-grid 1550 sample is refused. Tidy3D numbers below are at exact 1550.00 nm. In-house numbers in `fdtd_compare.json` are regenerated with that indexer.

### 10.1 Tidy3D (independent solver)

In-coupling Gaussian (SMF-28 waist, 8°, S-pol / \(E_y\)) into a silicon-strip mode. Full-height input waveguide continues through the −x PML (`wg_extra` from −5.5 µm to the first tooth; domain starts at −2.5 µm). Fiber \(x\) is maximised at 1550.00 nm on the 16 nm grid (best offset = −2.0 µm from the grating midpoint for all four layouts) and then **frozen** for spectra, etch, and the mesh series. Fill-only is on the etch sweep. Raw data: `analysis/results/tidy3d_compare.json`, `tidy3d_align.json`, `tidy3d_converge.json`.

The first batch parked the beam at the midpoint and stopped the waveguide at x = 0. Midpoint IL was ~3.13–3.20 dB; the same cells at −2.0 µm are ~2.66–2.85 dB. That 0.5 dB is alignment, not Maxwell ranking. Do not mix the two files.

Insertion loss at **1550.00 nm**, Δℓ = 16 nm, aligned, waveguide continued:

| Design | 1525 nm | **1550.00 nm** | Peak (λ) |
|---|---|---|---|
| Uniform 50% | 4.28 dB | **2.66 dB** | **2.61 dB (1555 nm)** |
| Period chirp | 3.59 dB | 2.84 dB | 2.83 dB (1545 nm) |
| Taillaert fill | 4.48 dB | 2.85 dB | 2.83 dB (1555 nm) |
| Proposed | **3.53 dB** | 2.76 dB | 2.72 dB (1545 nm) |

Etch sweep at **1550.00 nm**, same frozen \(x_\mathrm{fib}\), **including fill-only**:

| Design | 58 nm | 70 nm | 82 nm | Worst of three |
|---|---|---|---|---|
| Uniform | 3.50 dB | **2.66 dB** | **2.81 dB** | 3.50 dB |
| Chirp | 3.24 dB | 2.84 dB | 3.42 dB | 3.42 dB |
| Taillaert fill | 3.69 dB | 2.85 dB | 2.87 dB | 3.69 dB |
| Proposed | **3.22 dB** | 2.76 dB | 3.29 dB | **3.29 dB** |

Mesh series at 1550.00 nm, frozen geometry and frozen \(x_\mathrm{fib}\):

| Design | 16 nm | 8 nm | 4 nm |
|---|---|---|---|
| Uniform | 2.66 dB | 2.66 dB | **2.69 dB** |
| Taillaert fill | 2.85 dB | 2.88 dB | 2.92 dB |
| Proposed | 2.76 dB | 2.87 dB | 2.99 dB |
| Chirp | 2.84 dB | 2.94 dB | 3.04 dB |

What this supports, and what it does not:

1. **Uniform still wins at 1550.00 nm.** Aligned 16 nm: uniform 2.66 dB, proposed 2.76 dB, Taillaert 2.85 dB, chirp 2.84 dB. The leaky-wave 0.4 dB apodization win does not survive Maxwell. At 4 nm the gap grows: uniform 2.69 dB, proposed 2.99 dB.
2. **The 1525 nm shoulder is real at 16 nm.** Proposed 3.53 dB vs uniform 4.28 dB (0.75 dB). Chirp-only is almost as good (3.59 dB). Fill-only is not (4.48 dB). This was not repeated at 8 or 4 nm.
3. **Fill-only is the worst under-etch, not a hidden champion.** At 58 nm: proposed 3.22 dB ≈ chirp 3.24 dB, uniform 3.50 dB, Taillaert **3.69 dB**. Under-etch help is the chirp (angle tracking as \(n_B\) changes), not the fill apodization. Calling it a unique fill+chirp result was premature.
4. **Over-etch still favours the uniform / fill-only pair.** At 82 nm: uniform 2.81 dB, Taillaert 2.87 dB, proposed 3.29 dB, chirp 3.42 dB.
5. **Worst-case of these three etch points** is proposed 3.29 dB vs uniform 3.50 dB vs chirp 3.42 dB vs Taillaert 3.69 dB. That is a 0.21 dB three-point min-max note, not a yield. A process that is biased over-etch still wants the uniform cell.
6. **16 nm is not a converged ranking for the apodized cells.** Uniform moves 0.03 dB from 16→4 nm. Proposed moves 0.23 dB (2.76→2.99) and chirp 0.20 dB; both are still drifting at 4 nm. The 40 nm smoke job changed period count and source, so it was never a convergence point.
7. **0.5 dB is not available.** Finest-grid peaks sit near 2.7 dB (uniform) to 3.0 dB (proposed) in 2-D in-coupling. Bozzola’s −1.9 dB is an unconstrained 2-D FDTD ceiling, not this DRC-legal 20-period cell.

Adjoint inverse design is **not** the next button. The cost function would be fitting 16 nm noise on the apodized cells. A 2 nm point, or a 3-D focusing cell, comes first.

Caveats that remain: 2-D (infinite width), no 3-D focusing, no adjoint, no fabricated devices, etch sampled at three depths only, fiber offset frozen from the 16 nm scan (not re-optimised at 8/4 nm). Meep is not installed on this Windows host.

### 10.2 In-house FDTD (25 nm Yee, on-grid 1550.00 nm)

Same four layouts, same constraints, coarser grid, out-coupling |E|² overlap. Wavelength list is 1525, 1535, 1545, **1550**, 1555, 1565, 1575 nm. Chirp is on the etch / \(t_\mathrm{Si}\) / CD sweeps. Figures: `analysis/figures/em00_dashboard.png`, `em07_verdict.png`.

| Design | 1525 nm | **1550.00 nm** | Peak (λ) |
|---|---|---|---|
| Uniform 50% | 5.30 dB | **2.63 dB** | **2.59 dB (1555 nm)** |
| Period chirp | 4.40 dB | 2.76 dB | 2.76 dB (1550 nm) |
| Taillaert fill | 5.34 dB | 2.94 dB | 2.92 dB (1555 nm) |
| Proposed | **4.37 dB** | 2.74 dB | 2.74 dB (1550 nm) |

Etch sweep at **1550.00 nm**:

| Design | 58 nm | 70 nm | 82 nm |
|---|---|---|---|
| Uniform | 3.82 dB | **2.63 dB** | **2.69 dB** |
| Chirp | 3.55 dB | 2.76 dB | 3.33 dB |
| Proposed | **3.52 dB** | 2.74 dB | 3.19 dB |

The earlier “1550 nm interpolated = 3.00 dB uniform” number was a 1545/1555 interpolation of a peaked spectrum; the on-grid 1550.00 nm sample is 2.63 dB. A second bug: `numpy.isclose` default `atol` then labelled the 1545 nm *sweep* samples as 1550.00, so an older under-etch table (uniform 4.95 dB at “1550 nm”) was 1545 nm. The table above is the on-grid 1550.00 nm sample.

After the Tidy3D re-run (aligned, waveguide continued), the two solvers agree on the shape of the argument even though the absolute IL still differs (in-house is out-coupling |E|²; Tidy3D is in-coupling mode overlap): uniform wins at 1550.00 nm; proposed helps the 1525 nm shoulder; over-etch favours uniform; under-etch is shared by chirp and proposed, not unique to fill+chirp. Fill-only is the *worst* 58 nm cell in Tidy3D (3.69 dB). Do not average the two solvers into a fake consensus. CD ±5 nm is essentially flat for all three in-house cells (uniform 2.61–2.66 dB); the older “proposed is CD-robust, uniform is not” line was the 1545 nm alias.

This is not a peak-efficiency paper. Fill apodization without a period chirp is a net loss under-etch (Tidy3D Taillaert 3.69 dB at 58 nm). Combining fill with an angle-preserving chirp does not beat a uniform cell at 1550.00 nm, and the apodized ranking is not mesh-converged at 16 nm. The 0.5 dB champion is not on this stack.

## 11. What to do next, in order

1. **Done, and it changed the story:** waveguide through the −x PML, matched \(x_\mathrm{fib}\), Taillaert on the etch sweep, 16→8→4 nm at frozen alignment. Uniform is stable under refinement; proposed is not. Fill-only is the worst 58 nm cell. Do not start adjoint on the 16 nm apodized ranking.
2. **If anything:** a 2 nm 2-D point on uniform vs proposed vs Taillaert, or a 3-D focusing cell of the uniform layout. Adjoint inverse design with a 75 nm filter only after the grid has stopped moving, and the cost must include under-etch *and* over-etch. A paper exists if that cell beats *uniform* at 1550.00 nm *and* on worst-case etch.
3. **One MPW**, paired loopbacks, as in §8. That is the only “Green” that means anything.
4. Only then: poly-Si overlay or a foundry-legal backside mirror, if the PDK has them, if you want sub-1 dB.

Do not write a second framework paper in the meantime.

---

## References

1. A. Bozzola, L. Carroll, D. Gerace, I. Cristiani, L. C. Andreani, “Optimising apodized grating couplers in a pure SOI platform to −0.5 dB coupling efficiency,” *Opt. Express* **23**, 16289 (2015).
2. D. Benedikovic et al., “Subwavelength index engineered surface grating coupler with sub-decibel efficiency for 220-nm SOI,” *Opt. Express* **23**, 22628 (2015).
3. H. Wang et al., “Ultralow-loss optical interconnect enabled by topological unidirectional guided resonance,” *Sci. Adv.* **10**, eadn4372 (2024).
4. S.-Y. Huang, S. Barz, “Compact inversely-designed vertical coupler with bottom reflector,” *Sci. Rep.* **15**, 2925 (2025); arXiv:2409.10660.
5. C. Valdez, J. E. Castro, J. Witzens, et al., “Three-wave interaction grating coupler with sub-decibel insertion loss at normal incidence,” arXiv:2506.19242 (2025).
6. A. Y. Piggott et al., “Inverse design and demonstration of a compact and broadband on-chip wavelength demultiplexer,” *Nat. Photon.* **9**, 374 (2015).
7. A. Y. Piggott et al., “Fabrication-constrained nanophotonic inverse design,” *Sci. Rep.* **7**, 1786 (2017); arXiv:1612.03222.
8. S. Molesky et al., “Inverse design in nanophotonics,” *Nat. Photon.* **12**, 659 (2018).
9. C. M. Lalau-Keraly, S. Bhargava, O. D. Miller, E. Yablonovitch, “Adjoint shape optimization applied to electromagnetic design,” *Opt. Express* **21**, 21693 (2013).
10. A. Michaels, E. Yablonovitch, “Inverse design of near unity efficiency perfectly vertical grating couplers,” *Opt. Express* **26**, 4766 (2018).
11. J. Komma, C. Schwarz, G. Hofmann, D. Heinert, R. Nawrodt, “Thermo-optic coefficient of silicon at 1550 nm and cryogenic temperatures,” *Appl. Phys. Lett.* **101**, 041905 (2012).
12. L. Chrostowski, M. Hochberg, *Silicon Photonics Design*, Cambridge University Press (2015), Ch. 11.
13. Y. Xing, D. Spina, A. Li, T. Dhaene, W. Bogaerts, and related; variation compilation in A. Cem et al. / ACS Photonics **10**, 928 (2023).
14. E. Timurdogan, Z. Su, C. V. Poulton, et al. (Analog Photonics), AIM Photonics PDK, OFC 2018; N. M. Fahrenkopf et al., “The AIM Photonics MPW,” *IEEE J. Sel. Top. Quantum Electron.* (2022): TE vertical coupler ~2.8 dB, 30 nm 1 dB BW.
15. imec IC-Link, iSiPP200 platform note: SMF grating couplers < 2 dB.
16. AIM Photonics, “Silicon Photonics MPW Bulk Pricing,” https://www.aimphotonics.com/mpw-volume-pricing (accessed 2026-09-13).
17. D. Taillaert, P. Bienstman, R. Baets, “Compact efficient broadband grating coupler for silicon-on-insulator waveguides,” *Opt. Lett.* **29**, 2749 (2004).
18. G. Roelkens, D. Vermeulen, D. Van Thourhout, et al., high-directionality overlay grating couplers, *Appl. Phys. Lett.* **92**, 131101 (2008).
19. R. E. Christiansen, O. Sigmund, “Inverse design in photonics by topology optimization: tutorial,” *J. Opt. Soc. Am. B* **38**, 496 (2021).
20. A. H. El-Saeed et al., “Low-loss silicon directional coupler … on a 300 mm wafer,” arXiv:2404.06117 (2024). Different device class; cited as an example of *actual* wafer-scale passives.

Numbers in the tables that are not attributed to these papers were produced by `python analysis/run_study.py` (analytic), `python analysis/run_em_compare.py` (in-house FDTD), and `python analysis/run_tidy3d_compare.py` (Tidy3D) on 2026-09-13, stored in `analysis/results/`.
