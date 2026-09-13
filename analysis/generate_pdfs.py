"""Typeset the technical report and design spec. Numbers come from study.json."""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "analysis" / "figures"
RES = json.loads((ROOT / "analysis" / "results" / "study.json").read_text(encoding="utf-8"))
OUT = ROOT / "paper"


NAVY = colors.HexColor("#1f4e79")
RULE = colors.HexColor("#c45911")


def styles():
    s = getSampleStyleSheet()
    s.add(
        ParagraphStyle(
            "CoverTitle",
            parent=s["Title"],
            fontName="Times-Bold",
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            spaceAfter=12,
            textColor=NAVY,
        )
    )
    s.add(
        ParagraphStyle(
            "CoverSub",
            parent=s["Normal"],
            fontName="Times-Italic",
            fontSize=11,
            leading=14,
            alignment=TA_CENTER,
            spaceAfter=6,
        )
    )
    s.add(
        ParagraphStyle(
            "Meta",
            parent=s["Normal"],
            fontName="Times-Roman",
            fontSize=10,
            leading=13,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#333333"),
            spaceAfter=4,
        )
    )
    s.add(
        ParagraphStyle(
            "Body",
            parent=s["Normal"],
            fontName="Times-Roman",
            fontSize=10,
            leading=13.5,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
        )
    )
    s.add(
        ParagraphStyle(
            "H1",
            parent=s["Heading1"],
            fontName="Times-Bold",
            fontSize=13,
            leading=16,
            textColor=NAVY,
            spaceBefore=14,
            spaceAfter=8,
        )
    )
    s.add(
        ParagraphStyle(
            "H2",
            parent=s["Heading2"],
            fontName="Times-Bold",
            fontSize=11,
            leading=14,
            textColor=NAVY,
            spaceBefore=10,
            spaceAfter=6,
        )
    )
    s.add(
        ParagraphStyle(
            "Caption",
            parent=s["Normal"],
            fontName="Times-Italic",
            fontSize=8.5,
            leading=11,
            alignment=TA_CENTER,
            spaceAfter=10,
            spaceBefore=2,
        )
    )
    s.add(
        ParagraphStyle(
            "Cell",
            parent=s["Normal"],
            fontName="Times-Roman",
            fontSize=8,
            leading=10.5,
        )
    )
    s.add(
        ParagraphStyle(
            "CellH",
            parent=s["Normal"],
            fontName="Times-Bold",
            fontSize=8,
            leading=10.5,
        )
    )
    s.add(
        ParagraphStyle(
            "Foot",
            parent=s["Normal"],
            fontName="Times-Roman",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#444444"),
        )
    )
    s.add(
        ParagraphStyle(
            "Warn",
            parent=s["Normal"],
            fontName="Times-Bold",
            fontSize=9.5,
            leading=12.5,
            textColor=RULE,
            alignment=TA_JUSTIFY,
            spaceAfter=10,
            spaceBefore=4,
        )
    )
    return s


def P(text, st="Body"):
    return Paragraph(text, STY[st])


def fig(name, caption, width=6.3 * inch):
    path = FIG / name
    if not path.exists():
        return [P(f"[missing figure {name}]", "Caption")]
    img = Image(str(path), width=width, height=width * 0.52)
    img.hAlign = "CENTER"
    # keep aspect: override using real ratio
    from reportlab.lib.utils import ImageReader

    ir = ImageReader(str(path))
    w, h = ir.getSize()
    height = width * h / w
    img = Image(str(path), width=width, height=height)
    img.hAlign = "CENTER"
    return [KeepTogether([img, P(caption, "Caption")])]


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(NAVY)
    canvas.setLineWidth(0.8)
    canvas.line(0.85 * inch, letter[1] - 0.55 * inch, letter[0] - 0.85 * inch, letter[1] - 0.55 * inch)
    canvas.setFont("Times-Italic", 8)
    canvas.setFillColor(NAVY)
    canvas.drawString(0.85 * inch, letter[1] - 0.48 * inch, "Foundry-constrained silicon grating coupler")
    canvas.drawRightString(letter[0] - 0.85 * inch, letter[1] - 0.48 * inch, "Technical report  ·  13 Sep 2026")
    canvas.line(0.85 * inch, 0.55 * inch, letter[0] - 0.85 * inch, 0.55 * inch)
    canvas.setFillColor(colors.HexColor("#444444"))
    canvas.drawCentredString(letter[0] / 2, 0.38 * inch, f"{doc.page}")
    canvas.restoreState()


def cell(text, header=False):
    return P(text, "CellH" if header else "Cell")


def table(rows, col_widths):
    data = []
    for i, row in enumerate(rows):
        data.append([cell(c, header=(i == 0)) for c in row])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef4")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#99aacc")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return t


STY = None  # set in main


def report_story():
    d = RES["design"]
    th = RES["thermal"]
    mc = RES["monte_carlo"]
    en = RES["energy"]
    st = RES["stats"]
    sl = RES["slab"]

    story = []
    story.append(Spacer(1, 0.6 * inch))
    story.append(P("Foundry-Constrained Yield-Aware Design of Silicon Grating Couplers", "CoverTitle"))
    story.append(
        P(
            "A technical report replacing an LLM-generated “validated framework.” "
            "One device, one process, derived math, runnable code.",
            "CoverSub",
        )
    )
    story.append(P("13 September 2026", "Meta"))
    story.append(
        P(
            "No devices have been fabricated. No 3-D FDTD inverse-design loop has been run. "
            "Those are the next experiments, not claims of this document. Every number below "
            "is produced by <font face='Courier'>analysis/run_study.py</font> and stored in "
            "<font face='Courier'>analysis/results/study.json</font>.",
            "Warn",
        )
    )

    story.append(P("Abstract", "H1"))
    story.append(
        P(
            "We reformulate C-band TE fiber-to-chip grating-coupler design as a foundry-constrained, "
            "chance-constrained electromagnetic problem on a single public process: 220 nm SOI, "
            "70 nm shallow etch, 2 µm BOX, 150 nm minimum CD, 8° SMF-28 in oxide. The Maxwell "
            "problem is non-convex. PDK rules are hard constraints. Yield is the probability that "
            "insertion loss at 1550 nm stays below a specification under published within-wafer "
            "variation, not a 50-wafer binomial at two logic nodes."
        )
    )
    story.append(
        P(
            f"A 1-D slab plus leaky-wave model, calibrated so a uniform grating matches Bozzola et al. "
            f"(2015) at 53.7% 2-D FDTD, gives period Λ = {d['period_nm']:.0f} nm at 50% fill "
            f"(n<sub>eff</sub> = {d['n_eff']:.3f}); DRC fill window "
            f"[{d['ff_min']:.3f}, {d['ff_max']:.3f}]; linear fill apodization to "
            f"<b>{d['il_apodized_db']:.2f} dB</b> nominal (uniform {d['il_uniform_db']:.2f} dB); "
            f"process Monte Carlo mean <b>{mc['mean_il_db']:.2f} dB</b>, σ = {mc['std_il_db']:.2f} dB; "
            f"<b>yield at IL ≤ 0.5 dB is zero</b>; yield at 2.5 dB is "
            f"{100*mc['yields']['y_le_2.5dB']:.1f}%. "
            f"Thermo-optic walk dλ/dT = {th['dlambda_dT_nm_per_K']:.3f} nm/K; extra IL after a 20 K "
            f"swing at fixed laser wavelength is {th['extra_il_20K_db']:.3f} dB, not 0.01 dB/°C. "
            f"On a 15 pJ/bit module with 25% laser share, beating a 2.8 dB PDK cell by 0.54 dB at "
            f"both ends saves {100*en['pdk_to_model']['module_fraction_saved']:.1f}% of module energy."
        )
    )
    story.append(
        P(
            "The archived draft’s 0.3 dB / 70% yield target sits below the published −1.9 dB physics "
            "floor for 220 nm SOI without a back-reflector. That 65% figure is Bozzola’s published "
            "2-D FDTD result, not a min() applied to this model. Tidy3D 2-D at exact 1550.00 nm, "
            "waveguide through the −x PML, fiber aligned, 16→8→4 nm: uniform still wins "
            "(2.66 dB at 16 nm, 2.69 dB at 4 nm). Proposed drifts 2.76→2.99 dB under refinement. "
            "Fill-only is the worst 58 nm cell (3.69 dB). Sub-0.5 dB "
            "literature results use a metal mirror, a poly-Si overlay, unidirectional guided resonances, "
            "or thicker SOI. The honest production target on this stack is to beat a ~2.8 dB PDK "
            "grating toward the ~1.9–2.3 dB DRC-limited floor, with a 2.5 dB yield spec, on one MPW "
            "of paired loopbacks."
        )
    )

    story.append(P("1.  Why this document exists", "H1"))
    story.append(
        P(
            "The three PDFs previously in this folder (now <font face='Courier'>archive-llm-drafts/</font>, "
            "PDF Author = “ChatGPT Canvas”) described a validated multi-foundry AI coupler framework "
            "targeting &lt;0.5 dB at ≥70% yield, with a 2×2 factorial on TSMC 7 nm versus Intel 45 nm, "
            "50 wafers per fab, and a $500k budget. They contained no geometry, no Maxwell solve, and "
            "no original data. Several citations were attached to the wrong papers. That draft is a list "
            "of topics. This report picks one device, writes the optimization problem with the right "
            "objects, computes what can be computed without an FDTD licence, and sizes an experiment "
            "that exists on a price list."
        )
    )

    story.append(P("2.  Device and process", "H1"))
    story.append(
        P(
            "220 nm SOI with a ~70 nm shallow etch is the default of AIM Photonics, imec iSiPP, AMF, "
            "and Cornerstone. It is not TSMC N7 and not Intel 45 nm CMOS. TSMC’s silicon-photonics "
            "offering is a 65 nm-class photonics flow plus COUPE packaging. Shipping the same coupler "
            "mask to “TSMC 7 nm and Intel 45 nm” is not a generalization study."
        )
    )
    story.append(
        table(
            [
                ["Quantity", "Value", "Note"],
                ["Si device / BOX / etch", "220 nm / 2.0 µm / 70 nm", "photonics-grade SOI"],
                ["Cladding", "SiO<sub>2</sub>, n = 1.444", "1550 nm"],
                ["Fiber", "SMF-28, MFD 10.4 µm, 8°", "angle in the cladding"],
                ["Polarization / λ", "TE / 1550 nm", "PDK TE vertical coupler class"],
                ["Min CD / space", "150 nm", "193 nm DUV, conservative"],
                ["AIM PDK TE GC", "~2.8 dB, ~30 nm 1 dB BW", "Fahrenkopf / Analog Photonics"],
                ["imec iSiPP200 GC", "&lt; 2 dB (platform note)", "different PDK, same idea"],
            ],
            [1.7 * inch, 2.1 * inch, 2.6 * inch],
        )
    )
    story.append(Spacer(1, 8))
    story.append(P("2.1  What “&lt; 0.5 dB” actually requires", "H2"))
    story.append(
        P(
            "Bozzola et al., Opt. Express 23, 16289 (2015), put the 2-D FDTD ceiling for an apodized "
            "grating on <b>220 nm SOI with no back-reflector at 65% (−1.9 dB)</b>. The same paper "
            "reaches −0.5 dB only by moving to 340 nm SOI. Measured sub-decibel devices use a backside "
            "metal (Benedikovic 2015, −0.69 dB), topological unidirectional resonances on 340 nm SOI "
            "(Wang, Sci. Adv. 2024, −0.34 dB), a three-wave-interaction foundry coupler (Valdez 2025, "
            "−0.69 dB), or a simulated inverse design with a bottom reflector (Huang &amp; Barz 2025, "
            "−0.35 dB). A production spec of 0.3 dB on standard 220 nm SOI, no mirror, is not ambitious. "
            "It is forbidden by the stack."
        )
    )
    story.extend(fig("fig11_sota.png", "Figure 1.  Selected coupler results. Orange bars use a back-reflector."))

    story.append(P("3.  Electromagnetic model", "H1"))
    story.append(
        P(
            "Unetched (220 nm) and shallow-etched (150 nm) sections are symmetric oxide/Si/oxide slabs. "
            "Even TE modes satisfy κ sin(κd/2) − γ cos(κd/2) = 0, with "
            "κ = k<sub>0</sub>√(n<sub>Si</sub><sup>2</sup> − n<sub>eff</sub><sup>2</sup>) and "
            "γ = k<sub>0</sub>√(n<sub>eff</sub><sup>2</sup> − n<sub>ox</sub><sup>2</sup>). "
            f"n<sub>Si</sub> = 3.476, n<sub>ox</sub> = 1.444 at 1550 nm. Unetched: "
            f"n<sub>eff</sub> = {sl['unetched']['n_eff']:.3f}, n<sub>g</sub> = {sl['unetched']['n_g']:.3f}, "
            f"Γ<sub>Si</sub> = {sl['unetched']['Gamma']:.3f}. Etched: "
            f"n<sub>eff</sub> = {sl['etched']['n_eff']:.3f}, n<sub>g</sub> = {sl['etched']['n_g']:.3f}, "
            f"Γ<sub>Si</sub> = {sl['etched']['Gamma']:.3f}."
        )
    )
    story.append(
        P(
            "The Bloch index is the duty-cycle average n<sub>B</sub>(f) = f n<sub>unetch</sub> + "
            f"(1−f) n<sub>etch</sub> = {d['n_eff']:.3f} at f = 0.5. First-order phase match "
            "Λ = λ / (n<sub>B</sub> − n<sub>c</sub> sin θ) gives "
            f"<b>Λ = {d['period_nm']:.0f} nm</b> at 8°. Tooth and groove both ≥ 150 nm force "
            f"f ∈ [{d['ff_min']:.3f}, {d['ff_max']:.3f}]. Apodization that asks for f = 0.05 is not a "
            "PDK-legal design."
        )
    )
    story.extend(fig("fig01_slab_neff.png", "Figure 2.  TE slab n<sub>eff</sub> and n<sub>g</sub> versus Si thickness."))
    story.extend(fig("fig02_period.png", "Figure 3.  Phase-match period versus fill and fiber angle."))

    story.append(P("3.1  Coupling budget", "H2"))
    story.append(
        P(
            "Following Taillaert / Roelkens / Benedikovic, η = D · η<sub>∥</sub> · η<sub>2D</sub> · "
            "(1−R) · η<sub>taper</sub>. D is upward directionality from a two-beam BOX/handle "
            f"reflection model: D = {d['directionality']:.3f} at 2.0 µm BOX. η<sub>∥</sub> is the "
            "overlap of the radiated near-field with the SMF-28 Gaussian (w<sub>0</sub> = 5.2 µm). "
            f"Uniform overlap {d['overlap_uniform']:.3f}; linear fill apodization "
            f"{d['ff_start']:.3f} → {d['ff_end']:.3f} over {d['length_um']:.0f} µm raises it to "
            f"{d['overlap_apodized']:.3f}. η<sub>2D</sub> = {d['eta_2d']:.3f} is a single calibration "
            "constant that puts the <i>uniform</i> device on Bozzola’s 53.7% 2-D FDTD point. "
            f"Second-order Bragg reflection is {100*d['reflection']:.2f}% at 8° (the reason the fiber "
            "is tilted). η<sub>taper</sub> = 0.98."
        )
    )
    story.append(
        table(
            [
                ["Design", "η", "IL"],
                ["Uniform, 50% fill (calibrated)", "53.7%", f"{d['il_uniform_db']:.2f} dB"],
                ["Linear apodization, DRC-legal", f"{100*d['eta_apodized']:.1f}%", f"{d['il_apodized_db']:.2f} dB"],
                ["Bozzola unconstrained 220 nm FDTD ceiling", "65%", "1.90 dB"],
                ["AIM PDK TE GC (measured)", "~52%", "~2.8 dB"],
            ],
            [3.2 * inch, 1.5 * inch, 1.7 * inch],
        )
    )
    story.append(Spacer(1, 6))
    story.extend(
        fig("fig03_overlap.png", "Figure 4.  Uniform leakage overlap and radiated near-field versus SMF-28.")
    )
    story.extend(
        fig("fig04_directionality.png", "Figure 5.  Upward directionality versus BOX thickness (two-beam model).")
    )
    story.extend(
        fig("fig12_focusing.png", "Figure 6.  Focusing grating from the confocal construction. This is the GDS, not a 1-D bar array.")
    )
    story.append(
        P(
            "This model is not a substitute for 2-D/3-D FDTD. It does not capture the exact radiation "
            "angle versus etch or substrate higher-order reflections. It is enough to size the period "
            "and DRC window, show that 0.5 dB is impossible on this stack, propagate process error "
            "into yield, and write a correct optimization problem for the FDTD loop."
        )
    )

    story.append(P("4.  The optimization problem, written correctly", "H1"))
    story.append(
        P(
            "Let x be the design (fill samples, spline controls, or a filtered density), p the process "
            "vector, and η(x, p; λ) the fiber overlap of the Maxwell field. IL = −10 log<sub>10</sub> η. "
            "The problem we actually want is: minimize E<sub>p</sub>[IL(x, p; λ<sub>0</sub>)] subject to "
            "P<sub>p</sub>(IL ≤ IL<sub>spec</sub>) ≥ Y<sub>spec</sub>, BW<sub>1dB</sub> ≥ 25 nm, "
            "R<sub>back</sub> ≤ 10<sup>−1.5</sup>, and DRC(x) = true. Recommended on this stack: "
            "IL<sub>spec</sub> = 2.5 dB, Y<sub>spec</sub> = 0.80. Not 0.3 dB and 70%."
        )
    )
    story.append(
        P(
            "The archived scalarization f = ω<sub>1</sub>L − ω<sub>2</sub>Y + ω<sub>3</sub>T + ω<sub>4</sub>P "
            "with KKT conditions, “bandgap invariants,” and Sobol indices in the same paragraph is not a "
            "formulation. L, Y, T, P have different units. FDTD coupler loss is non-convex, so KKT is "
            "not a solution method. Yield is a discontinuous functional of process. PDK rules are "
            "indicators, not a soft fourth term. Bandgap invariants are a topological-photonics tool, "
            "not a general coupler certificate."
        )
    )
    story.append(
        P(
            "A tractable surrogate (in <font face='Courier'>optimize.py</font>) is sample-average "
            "approximation plus CVaR on the upper tail of IL, with x = (f<sub>start</sub>, f<sub>end</sub>, L) "
            "inside the DRC box. A Nelder–Mead pass moved mean IL from 2.42 dB to 2.35 dB and 2.5 dB "
            "yield from 79% to 86%. That is a real, small gain. The FDTD loop should solve the same "
            "problem with x a filtered density. Adjoint gradients "
            "(Lalau-Keraly et al., Opt. Express 21, 21693, 2013) give ∂J/∂ε(r) from one forward and "
            "one adjoint Maxwell solve. Min CD enters by a 75 nm conic filter plus Heaviside projection "
            "(Piggott, fabrication-constrained inverse design, 2017). We have not run that loop. The "
            "design spec says how."
        )
    )

    story.append(P("5.  Thermal behaviour, derived rather than asserted", "H1"))
    story.append(
        P(
            "Differentiating the phase-match condition at fixed angle, with "
            "n<sub>g</sub> = n<sub>eff</sub> − λ ∂n<sub>eff</sub>/∂λ, gives "
            "dλ/dT = λ (∂n<sub>eff</sub>/∂T + n<sub>eff</sub> α<sub>Si</sub>) / "
            "(n<sub>g</sub> − n<sub>c</sub> sin θ). Using Komma et al., Appl. Phys. Lett. 101, 041905 "
            f"(2012), dn<sub>Si</sub>/dT = 1.80×10<sup>−4</sup> /K: "
            f"<b>dλ/dT = {th['dlambda_dT_nm_per_K']:.3f} nm/K</b>. "
            "A grating coupler is broadband. Extra IL at the design wavelength after a peak walk δλ "
            "on a Gaussian spectrum is 12.04 (δλ/FWHM)<sup>2</sup> dB. A 20 K swing walks the peak by "
            f"{20*th['dlambda_dT_nm_per_K']:.2f} nm and costs <b>{th['extra_il_20K_db']:.3f} dB</b>. "
            "The linear coefficient “0.01 dB/°C” is the wrong functional form (detuning loss is "
            "quadratic in ΔT) and is two orders of magnitude too large on this device class."
        )
    )
    story.extend(
        fig(
            "fig05_thermal.png",
            "Figure 7.  Extra IL at 1550 nm versus temperature. The archived 0.01 dB/°C × 20°C line is 0.20 dB.",
        )
    )

    story.append(P("6.  Yield", "H1"))
    story.append(
        P(
            "Within-wafer 1-sigma values from 193 nm DUV silicon photonics (ACS Photonics 10, 928, 2023) "
            "and Chrostowski’s grating-coupler wavelength sensitivities (Silicon Photonics Design, Ch. 11): "
            "σ(t<sub>Si</sub>) = 2.0 nm (1.82 nm/nm), σ(etch) = 3.0 nm (1.90 nm/nm), "
            "σ(CD) = 2.6 nm (0.215 nm/nm), σ(θ) = 0.4°, σ(offset) = 0.8 µm. "
            "IL at 1550 nm is peak IL of the perturbed geometry plus detuning plus a small angular penalty. "
            "This is within-wafer scatter, not wafer-to-wafer mean shift."
        )
    )
    story.append(
        table(
            [
                ["Statistic", "Value"],
                ["Nominal apodized IL", f"{mc['nominal_apodized_il_db']:.2f} dB"],
                ["Monte Carlo mean / median / σ", f"{mc['mean_il_db']:.2f} / {mc['median_il_db']:.2f} / {mc['std_il_db']:.2f} dB"],
                ["5th / 95th percentile", f"{mc['p05_il_db']:.2f} / {mc['p95_il_db']:.2f} dB"],
                ["P(IL ≤ 0.5 dB)", "0"],
                ["P(IL ≤ 2.0 dB)", "0"],
                [
                    "P(IL ≤ 2.5 dB)",
                    f"{100*mc['yields']['y_le_2.5dB']:.1f}%  "
                    f"(95% CI {100*st['mc_yield_2p5dB_clopper_pearson']['lo']:.1f}–"
                    f"{100*st['mc_yield_2p5dB_clopper_pearson']['hi']:.1f}%)",
                ],
                ["P(IL ≤ 3.0 dB)", f"{100*mc['yields']['y_le_3.0dB']:.1f}%"],
            ],
            [3.4 * inch, 3.0 * inch],
        )
    )
    story.append(Spacer(1, 8))
    story.extend(
        fig(
            "fig06_yield_hist.png",
            "Figure 8.  Process Monte Carlo of IL at 1550 nm. The 0.5 dB target is empty.",
        )
    )
    story.extend(fig("fig07_yield_curve.png", "Figure 9.  Yield versus IL specification."))
    story.extend(
        fig("fig08_sobol.png", "Figure 10.  Jansen first-order Sobol indices of IL. Alignment and etch dominate.")
    )
    story.append(
        P(
            "The 0.5 dB target has yield zero because the <i>uncapped</i> leaky-wave mean is 2.42 dB "
            "and Bozzola’s published 2-D FDTD ceiling on this stack is 1.9 dB. Neither is a Python "
            "min() that copies 65% into the Monte Carlo. A 2.5 dB specification — 0.3 dB better than the "
            "AIM PDK cell, 0.25 dB worse than our mean — is the spec that has a chance of being real. "
            f"Jansen first-order Sobol indices: fiber offset {RES['sobol']['offset']:.2f}, etch "
            f"{RES['sobol']['etch']:.2f}, angle {RES['sobol']['theta']:.2f}, t<sub>Si</sub> "
            f"{RES['sobol']['t_si']:.2f}, CD {RES['sobol']['cd']:.2f} (sum {RES['sobol']['sum_first_order']:.2f})."
        )
    )

    story.append(P("7.  Energy, without the category error", "H1"))
    story.append(
        P(
            "An 800G pluggable is ~15 pJ/bit, of which the laser electrical share is ~20–30%. Copper DAC "
            "energy is a reach comparison. Coupler IL does not convert copper into photonics. Laser "
            "optical power scales as 10^(n<sub>c</sub>·ΔIL/10) for n<sub>c</sub> couplers in "
            "the laser-to-PD path. For a packaged TX+RX pair, n<sub>c</sub> = 2."
        )
    )
    story.append(
        table(
            [
                ["Change", "Laser scale", "% of 15 pJ/bit module", "Saved"],
                [
                    "PDK 2.8 → this 2.26 dB",
                    f"{en['pdk_to_model']['laser_optical_scale']:.2f}×",
                    f"{100*en['pdk_to_model']['module_fraction_saved']:.1f}%",
                    f"{en['pdk_to_model']['pj_saved']:.2f} pJ/bit",
                ],
                [
                    "PDK 2.8 → 0.5 dB (if it existed)",
                    f"{en['pdk_to_0p5dB']['laser_optical_scale']:.2f}×",
                    f"{100*en['pdk_to_0p5dB']['module_fraction_saved']:.1f}%",
                    f"{en['pdk_to_0p5dB']['pj_saved']:.2f} pJ/bit",
                ],
                [
                    "3.0 → 0.3 dB (draft setup)",
                    f"{en['from3p0_to_0p3']['laser_optical_scale']:.2f}×",
                    f"{100*en['from3p0_to_0p3']['module_fraction_saved']:.1f}%",
                    f"{en['from3p0_to_0p3']['pj_saved']:.2f} pJ/bit",
                ],
            ],
            [2.3 * inch, 1.3 * inch, 1.7 * inch, 1.2 * inch],
        )
    )
    story.append(Spacer(1, 6))
    story.extend(
        fig(
            "fig09_energy.png",
            "Figure 11.  Module-energy fraction saved versus improved coupler IL. The 70% line is the archived claim.",
        )
    )
    story.append(
        P(
            "The archived “70–90% reduction versus copper, 5–10 pJ/bit → &lt;0.5 pJ/bit” does not follow "
            "from a coupler. Sub-pJ/bit transmitters exist; they get there by killing SERDES and DSP. "
            "A coupler improvement is worth about one pJ/bit on a pluggable."
        )
    )

    story.append(P("8.  An experiment that can be purchased", "H1"))
    story.append(
        P(
            "The archived protocol used G*Power to get n = 46 <i>wafers</i> to detect 70% versus 50% yield. "
            "Yield of a coupler is measured on devices. A 25 mm² AIM die holds hundreds of 40 µm × 40 µm "
            "focusing couplers. Textbook sizes, α = 0.05, 80% power:"
        )
    )
    story.append(
        table(
            [
                ["Test", "Effect", "n per arm"],
                ["Two-proportion yield 50% vs 70%", "20 points", f"{st['n_per_arm_yield_50_vs_70']} devices"],
                ["Two-sample t, ΔIL = 0.30 dB, σ = 0.30 dB", "mean IL", f"{st['n_per_arm_mean_il_0p3dB_sigma_0p3']} devices"],
                ["Paired t, σ_diff = 0.20 dB", "0.30 dB", f"{st['n_paired_0p3dB_sigma_diff_0p2']} pairs"],
                ["Archived draft", "50 wafers × 2 fabs", "not a test"],
            ],
            [2.6 * inch, 1.8 * inch, 2.0 * inch],
        )
    )
    story.append(Spacer(1, 6))
    story.extend(fig("fig10_sample_size.png", "Figure 12.  Device-level sample size. Fifty wafers is not the answer."))
    story.append(
        P(
            "Put 100 PDK loopbacks and 100 candidate loopbacks on one reticle, plus a period/fill ladder "
            "and PCM. AIM Photonics member price for 20 chips of a 25 mm² passive PIC is $28,600 at the "
            "published volume table (accessed 2026-09-13). Masks are in the MPW price. This is the "
            "$30k experiment, not $500k, and it does not require a TSMC N7 NDA. Falsification: if the "
            "candidate’s paired mean IL is not ≥ 0.20 dB better than the PDK cell with a 95% interval "
            "excluding zero, the design claim is false on this process — and that is publishable."
        )
    )

    story.append(P("9.  Errata of the archived draft", "H1"))
    story.append(
        table(
            [
                ["Draft claim", "Fact"],
                ["“Validated framework,” Green = multi-fab", "No data, no geometry, no fab"],
                ["TSMC 7 nm vs Intel 45 nm", "Wrong objects. Use AIM / imec / Cornerstone 220 nm SOI"],
                ["50 wafers × 2, $500k", "~100 devices on one MPW, ~$30k"],
                ["IL ≤ 0.3 dB at ≥70% yield", "Below the −1.9 dB 220 nm no-mirror floor; yield 0 here"],
                ["ω<sub>1</sub>L − ω<sub>2</sub>Y + ω<sub>3</sub>T + ω<sub>4</sub>P, KKT", "Non-convex Maxwell + chance constraint + DRC"],
                ["0.01 dB/°C", f"{th['dlambda_dT_nm_per_K']:.3f} nm/K walk; {th['extra_il_20K_db']:.3f} dB extra in 20 K"],
                ["70–90% energy vs copper from the coupler", f"~{100*en['from3p0_to_0p3']['module_fraction_saved']:.0f}% of a 15 pJ/bit module, laser share only"],
                ["PMC7407772 for −0.81 dB on 300 mm wafers", "That PMC is a 2019 review; the number is Sci. Rep. 14, 53975, 10 devices on one SiN chip"],
                ["Piggott 2015 “inverse tapers, Luxtera”", "A 2.8 µm wavelength demultiplexer"],
                ["PDF Author: ChatGPT Canvas", "File properties"],
            ],
            [2.6 * inch, 3.8 * inch],
        )
    )

    story.append(P("10.  What to do next, in order", "H1"))
    story.append(
        P(
            "1. Done: Tidy3D re-run with waveguide through the −x PML, matched x_fib, fill-only "
            "on the etch sweep, 16→8→4 nm. Uniform 2.69 dB at 4 nm; proposed drifts to 2.99 dB. "
            "Fill-only is the worst 58 nm cell. Do not start adjoint on the 16 nm apodized ranking."
        )
    )
    story.append(
        P(
            "2. Adjoint inverse design with a 75 nm filter, 150 nm projection, 8° fiber, CVaR on a "
            "20-point process batch. Compare to the linear apodization. That is a paper if you beat "
            "the PDK cell in FDTD and on the MPW."
        )
    )
    story.append(
        P(
            "3. One MPW, paired loopbacks, as in <font face='Courier'>design/mpw-protocol.md</font>. "
            "That is the only “Green” that means anything."
        )
    )
    story.append(
        P(
            "4. Only then: poly-Si overlay or a foundry-legal backside mirror, if the PDK has them, "
            "if you want sub-1 dB. Do not write a second framework paper in the meantime."
        )
    )

    story.append(P("Selected references", "H1"))
    refs = [
        "A. Bozzola et al., Opt. Express 23, 16289 (2015). 220 nm no-mirror ceiling −1.9 dB; 340 nm −0.5 dB.",
        "D. Benedikovic et al., Opt. Express 23, 22628 (2015). SWG + backside metal, −0.69 dB measured.",
        "H. Wang et al., Sci. Adv. 10, eadn4372 (2024). Topological UGR, −0.34 dB on 340 nm SOI.",
        "S.-Y. Huang, S. Barz, Sci. Rep. 15, 2925 (2025). Inverse vertical coupler + mirror, −0.35 dB sim.",
        "C. M. Lalau-Keraly et al., Opt. Express 21, 21693 (2013). Adjoint shape optimization.",
        "A. Y. Piggott et al., Sci. Rep. 7, 1786 (2017). Fabrication-constrained inverse design.",
        "J. Komma et al., Appl. Phys. Lett. 101, 041905 (2012). dn<sub>Si</sub>/dT at 1550 nm.",
        "L. Chrostowski, M. Hochberg, Silicon Photonics Design, CUP (2015), Ch. 11. GC wavelength sensitivities.",
        "N. M. Fahrenkopf et al. / Analog Photonics, AIM Photonics MPW: TE GC ~2.8 dB, 30 nm 1 dB BW.",
        "AIM Photonics MPW volume pricing, https://www.aimphotonics.com/mpw-volume-pricing (accessed 2026-09-13).",
        "D. Taillaert, P. Bienstman, R. Baets, Opt. Lett. 29, 2749 (2004). Compact SOI grating coupler.",
        "Full citation list: paper/manuscript.md.",
    ]
    for r in refs:
        story.append(P(r, "Foot"))

    story.append(Spacer(1, 12))
    story.append(
        P(
            "Canonical source: paper/manuscript.md. Design spec: design/design-spec.md. "
            "MPW protocol: design/mpw-protocol.md. Reproduce: python analysis/run_study.py.",
            "Foot",
        )
    )
    return story


def spec_story():
    story = []
    story.append(Spacer(1, 0.3 * inch))
    story.append(P("Design specification: yield-aware grating coupler on 220 nm SOI", "CoverTitle"))
    story.append(P("Implementation spec for the FDTD loop, GDS, and MPW. 13 September 2026.", "CoverSub"))
    story.append(
        P(
            "This is the engineering document. Physics and claims live in the technical report. "
            "An engineer should be able to build the next three artefacts from these pages: a 2-D "
            "FDTD ranking check, a focusing-coupler GDS, and a 25 mm² MPW reticle of paired loopbacks.",
            "Body",
        )
    )
    story.append(P("Goals", "H1"))
    story.append(
        P(
            "Beat the AIM PDK TE vertical coupler (~2.8 dB) by ≥ 0.20 dB in paired on-wafer loopbacks. "
            "Hold P(IL(1550 nm) ≤ 2.5 dB) ≥ 0.80 in the process model, then confirm empirically. "
            "1 dB bandwidth ≥ 25 nm, on-chip reflection &lt; −12 dB. Stay inside 150 nm min CD, "
            "single shallow etch, no back-reflector unless the PDK already has an overlay."
        )
    )
    story.append(P("Non-goals", "H1"))
    story.append(
        P(
            "Sub-0.5 dB on this stack; TSMC N7 / Intel 45 nm “generalization”; quantum, cryogenic, "
            "256-channel, TCO, or dual-use write-ups; claiming validation before FDTD and MPW exist."
        )
    )
    story.append(P("Key decisions", "H1"))
    story.append(
        table(
            [
                ["Decision", "Choice", "Why"],
                ["Device", "Focusing GC, TE, 1550 nm, 8°", "Wafer-probeable; PDK baseline exists"],
                ["Stack", "220 nm / 2 µm BOX / 70 nm etch", "Public MPW"],
                ["Min CD", "150 nm", "193 nm DUV, conservative"],
                ["Objective", "E[IL] + 0.35 CVaR<sub>0.9</sub>", "Chance constraint without fake convexity"],
                ["Spec", "2.5 dB @ 80% yield", "Above model mean 2.42 dB; below PDK"],
                ["v0 geometry", "Linear fill apodization", "Already computed; ship if FDTD agrees"],
                ["v1 geometry", "Filtered density, r<sub>min</sub> = 75 nm", "Adjoint inverse design"],
                ["Experiment", "One MPW, paired loopbacks", "91 devices/arm powers 50 vs 70% yield"],
            ],
            [1.4 * inch, 2.3 * inch, 2.7 * inch],
        )
    )
    story.append(P("Locked FDTD stack", "H1"))
    story.append(
        P(
            "Si n = 3.476 at 1550 nm, 220 nm device, 70 nm partial etch (150 nm remaining), "
            "2.00 µm BOX n = 1.444, Si handle. Fiber: Gaussian, 10.4 µm 1/e<sup>2</sup> intensity "
            "diameter, 8° from normal in the cladding, TE. Offset along z is free (~3.6 µm from the "
            "first tooth in the analytic apodized design)."
        )
    )
    story.append(P("FDTD protocol (stop conditions)", "H1"))
    story.append(
        P(
            "Grid 8 nm max, 4 nm in the grating. Forward: strip mode 20 µm before the taper. Fiber "
            "monitor 12 µm wide, 1.5 µm above the cladding, 8° tilt, SMF-28 overlap. Also record "
            "on-chip reflection and substrate power."
        )
    )
    story.append(
        P(
            "Sweep order: (1) uniform f = 0.5, Λ = 622 nm — expect ~2.7 dB; if off by &gt; 0.3 dB, "
            "recalibrate η<sub>2D</sub> before anything else. (2) Analytic apodization — expect ~2.3 dB. "
            "(3) Fiber offset ±4 µm, angle ±2°. (4) Etch ±10 nm, t<sub>Si</sub> ±6 nm. "
            "(5) Adjoint loop 150–300 iterations with β continuation and a 20-point process batch "
            "every 20 iterations for CVaR. (6) 3-D of the winner only. If 2-D adjoint cannot beat "
            "the analytic apodization by 0.15 dB, ship the apodization. Inverse design is not obligatory."
        )
    )
    story.append(P("GDS cell GC_TE_C_8DEG", "H1"))
    story.append(
        P(
            "Focusing grating, 25 lines, 14 µm width; linear taper 500 nm → 14 µm over 150 µm; "
            "loopback GC–strip–GC at 127 µm fiber-array pitch; period ladder 600–640 nm step 5 nm; "
            "PDK TE GC loopbacks paired on the same die ±1 mm. PCM: CD SEM 310/310 nm, unpatterned "
            "Si thickness, 1 mm spiral."
        )
    )
    story.append(P("PR plan", "H1"))
    story.append(
        P(
            "PR1 analytic kit (this repo). PR2 GDS emitter (gdstk). PR3 FDTD driver (Tidy3D or Meep). "
            "PR4 tapeout deck (100+100 loopbacks). PR5 measurement notebook (paired t, Clopper–Pearson). "
            "Details and open questions (which MPW, poly-Si overlay, O-band vs C-band) are in "
            "design/design-spec.md. The MPW statistical protocol is design/mpw-protocol.md."
        )
    )
    story.append(P("Risks", "H1"))
    story.append(
        table(
            [
                ["Risk", "Mitigation"],
                ["2-D model optimistic vs 3-D", "Recalibrate before inverse design; 3-D the winner"],
                ["Etch-depth mean shift", "Period ladder; three periods around 622 nm"],
                ["Inverse design overfits the simulator", "Process batch in the loop; min-CD filter"],
                ["Claiming 0.5 dB anyway", "Do not"],
            ],
            [2.6 * inch, 3.8 * inch],
        )
    )
    story.append(P("MPW in one page", "H1"))
    story.append(
        P(
            "Primary hypothesis: paired same-die mean IL of (PDK − candidate) ≥ 0.20 dB, 95% CI "
            "excludes 0. Secondary: Clopper–Pearson interval on P(IL_cand ≤ 2.5 dB) lies above 0.70; "
            "median 1 dB BW ≥ 25 nm. Experimental unit is a loopback, not a wafer. 100 PDK + 100 "
            "candidate loopbacks, period ladder, PCM, on one AIM 25 mm² passive MPW "
            "(member list price $28,600 for 20 chips). Analysis locked before data: paired t on H1, "
            "Clopper–Pearson on H2. Do not pre-register 0.3 dB or 70% yield at 0.5 dB — that hypothesis "
            "is already false in simulation. Full protocol: design/mpw-protocol.md."
        )
    )
    return story


def build(path: Path, story_fn, title: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title=title,
        author="Engineering technical report (not ChatGPT Canvas)",
        creator="photonic/analysis/generate_pdfs.py",
        subject="Foundry-constrained silicon grating coupler",
    )
    doc.build(story_fn(), onFirstPage=header_footer, onLaterPages=header_footer)
    print("wrote", path)


def main():
    global STY
    STY = styles()
    build(
        OUT / "Photonic_Coupler_Technical_Report.pdf",
        report_story,
        "Foundry-Constrained Yield-Aware Design of Silicon Grating Couplers",
    )
    build(
        ROOT / "design" / "Design_Specification.pdf",
        spec_story,
        "Design specification: yield-aware grating coupler on 220 nm SOI",
    )


if __name__ == "__main__":
    main()
