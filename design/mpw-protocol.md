# MPW pilot protocol (device-level, one foundry)

**Status:** Draft, 13 September 2026

Device-level protocol for one 220 nm SOI MPW. The experimental unit is a coupler, not a wafer.

---

## Objective

On **one** 220 nm SOI MPW, test whether a DRC-legal focusing grating coupler designed by this repo is at least 0.20 dB better in mean IL at 1550 nm than the foundry PDK TE grating coupler, in a **paired, same-die** comparison, and estimate yield at a 2.5 dB specification.

## Hypotheses (pre-registered)

- **H1 (primary, mean IL).** Paired difference \(\Delta = \mathrm{IL}_\mathrm{PDK}-\mathrm{IL}_\mathrm{cand}\) has mean ≥ 0.20 dB. Two-sided 95% CI excludes 0.
- **H2 (yield).** Clopper–Pearson 95% interval on \(P(\mathrm{IL}_\mathrm{cand}\le 2.5\,\mathrm{dB})\) lies entirely above 0.70.
- **H3 (bandwidth).** Median 1 dB bandwidth of the candidate ≥ 25 nm.

**Falsification.** Fail H1: do not claim an inverse-design or apodization win. Fail H2 with a mean that still beats the PDK: report the device as a mean-IL improvement with a yield problem. Fail both: the analytic model was optimistic; publish the negative.

Do **not** pre-register 0.3 dB IL or 70% yield at 0.5 dB. That hypothesis is already false in simulation.

## Experimental unit

A **loopback** (GC → short strip → GC) on a die. IL per coupler = (fiber-to-fiber − waveguide loss)/2, waveguide loss from the PCM spiral on the same die.

Not a wafer. Not a foundry.

## Factors (this is not a 2×2 on logic nodes)

- **Design:** PDK TE GC vs candidate (analytic apodization and/or inverse-designed).
- **Nuisance:** die coordinate (SOI thickness gradient). Pairing by die removes it from H1.

Optional split, only if the MPW offers it: 220 nm vs 340 nm (Cornerstone). That is a second primary analysis, not a “fab” factor.

## Sample size

From `stats_design.py`, \(\alpha=0.05\), 80% power:

- Paired t, \(\Delta=0.30\) dB, \(\sigma_\mathrm{diff}=0.20\) dB: **n = 4 pairs.** We will still put **100 pairs** on the reticle because dies fall out and because H2 (yield) needs ~90 devices.
- Two-proportion, 50% vs 70%: **n = 91 per arm.**
- Two-sample t on unpaired IL, \(\Delta=0.30\) dB, \(\sigma=0.30\) dB: n = 16 per arm.

**Reticle content (25 mm² budget).**

| Block | Copies | Purpose |
|---|---|---|
| PDK loopback | 100 | Control |
| Candidate v0 (analytic apodization) | 100 | Primary |
| Candidate v1 (inverse design), if ready | 80 | Secondary |
| Period ladder 600–640 nm step 5 nm, 20 copies each | 180 | Angle / thickness PCM |
| Fill ladder at Λ=622 nm, f=0.35–0.70 step 0.05 | 160 | DRC / leakage |
| Waveguide spirals, CD SEM, thickness windows | ~10 | Loss and metrology |
| **Total coupler-class devices** | **~630** | fits |

## Randomization, blinding, covariates

- Die map is fixed by the reticle; there is no wafer-assignment randomization because there is one lot.
- **Blinding:** analysis scripts take a CSV of `{die, site, design_id, spectrum}`. `design_id` is hashed until data lock. The person aligning the fiber does not see the hash table.
- **Covariates:** die (x, y), measured SOI thickness if the foundry provides it, measured fiber angle from the period ladder.
- **Controlled:** same fiber array, same 8° mount, same input power (−10 dBm, well below TPA), temperature 25±1 °C.

## Measurement

1. Fiber array, 127 µm pitch, index-matched, 8° mechanical.
2. Tune (x, y, z) for max at 1550 nm on a sacrificial alignment GC; do not re-optimize per device beyond a 2 µm local search (otherwise you bake alignment skill into IL).
3. OSA or swept laser 1520–1580 nm, 10 pm step, two polarizations; keep TE.
4. De-embed: \(\mathrm{IL}_\mathrm{GC}=(\mathrm{IL}_{f2f}-\alpha L)/2\).
5. Peak IL, peak wavelength, 1 dB BW, 3 dB BW.

## Analysis (locked before data arrive)

- H1: paired t-test on per-die mean of (PDK − candidate), plus a linear mixed model with die as random intercept.
- H2: Clopper–Pearson on the candidate devices that pass a fiber-presence check (peak > −15 dB, otherwise the fiber missed).
- H3: Wilcoxon on 1 dB BW versus 25 nm.
- Spatial: plot peak λ vs die (x, y); if the gradient exceeds 5 nm across the reticle, report thickness-limited yield separately from random yield.
- Multiple testing: H1 is primary. H2 and H3 are secondary. No Bonferroni across 17 metrics.

**Do not** mix ANOVA, Bayesian hierarchical models, and KL-divergence on the same three endpoints unless a statistician adds them *after* H1–H3 are reported.

## Timeline and cost (order of magnitude)

| Phase | Time | Cost |
|---|---|---|
| FDTD + GDS + DRC | 4–8 weeks | compute |
| AIM 25 mm² passive MPW, 20 chips, member | foundry queue (often 3–6 months) | **$28,600** list |
| Non-member | | $34,320 list |
| Probe / OSA (internal) | 2 weeks | existing kit |
| **Total cash** | | **~$30k–$40k**, not $500k |

Masks are in the MPW price. There is no 7 nm mask set. If AIM is the wrong foundry, Cornerstone and imec MPW prices are in the same band.

## Success

- **Ship a paper** if H1 holds, even if H2 misses 80% and hits 60%. That is a mean-IL paper with a yield discussion.
- **Ship a methods note** if FDTD ranking matches the analytic model and the MPW is pending.
- **Do not** call the design Green, validated, or multi-fab on the basis of this protocol.
