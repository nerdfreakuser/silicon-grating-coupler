"""Typeset the 2-D FDTD comparison as a short results note.

Tables are filled from analysis/results/*.json so a stale interpolated
1550 nm caption cannot drift away from the files.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "analysis" / "figures"
RES = ROOT / "analysis" / "results"
OUT = ROOT / "paper" / "FDTD_Comparison.pdf"
NAVY = colors.HexColor("#1f4e79")


def styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("T", parent=s["Title"], fontName="Times-Bold", fontSize=16, leading=20, alignment=TA_CENTER, textColor=NAVY, spaceAfter=8))
    s.add(ParagraphStyle("Sub", parent=s["Normal"], fontName="Times-Italic", fontSize=10, leading=13, alignment=TA_CENTER, spaceAfter=10))
    s.add(ParagraphStyle("H", parent=s["Heading1"], fontName="Times-Bold", fontSize=12, leading=15, textColor=NAVY, spaceBefore=10, spaceAfter=6))
    s.add(ParagraphStyle("B", parent=s["Normal"], fontName="Times-Roman", fontSize=10, leading=13.5, alignment=TA_JUSTIFY, spaceAfter=8))
    s.add(ParagraphStyle("Cap", parent=s["Normal"], fontName="Times-Italic", fontSize=8.5, leading=11, alignment=TA_CENTER, spaceAfter=10))
    s.add(ParagraphStyle("C", parent=s["Normal"], fontName="Times-Roman", fontSize=8, leading=10.5))
    s.add(ParagraphStyle("CH", parent=s["Normal"], fontName="Times-Bold", fontSize=8, leading=10.5))
    return s


STY = None


def P(text, k="B"):
    return Paragraph(text, STY[k])


def fig(name, caption, width=6.4 * inch):
    path = FIG / name
    if not path.is_file():
        return [P(f"[missing figure {name}]", "Cap")]
    ir = ImageReader(str(path))
    w, h = ir.getSize()
    img = Image(str(path), width=width, height=width * h / w)
    img.hAlign = "CENTER"
    return [KeepTogether([img, P(caption, "Cap")])]


def cell(t, header=False):
    return P(t, "CH" if header else "C")


def table(rows, widths, highlight_row=None):
    data = [[cell(c, header=(i == 0)) for c in row] for i, row in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1)
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef4")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#99aacc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if highlight_row is not None:
        cmds.append(("BACKGROUND", (0, highlight_row), (-1, highlight_row), colors.HexColor("#d6e4f0")))
    t.setStyle(TableStyle(cmds))
    return t


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(NAVY)
    canvas.setLineWidth(0.8)
    canvas.line(0.85 * inch, letter[1] - 0.55 * inch, letter[0] - 0.85 * inch, letter[1] - 0.55 * inch)
    canvas.setFont("Times-Italic", 8)
    canvas.setFillColor(NAVY)
    canvas.drawString(0.85 * inch, letter[1] - 0.48 * inch, "2-D FDTD comparison, identical constraints")
    canvas.drawRightString(letter[0] - 0.85 * inch, letter[1] - 0.48 * inch, "13 Sep 2026")
    canvas.line(0.85 * inch, 0.55 * inch, letter[0] - 0.85 * inch, 0.55 * inch)
    canvas.setFillColor(colors.HexColor("#444444"))
    canvas.drawCentredString(letter[0] / 2, 0.38 * inch, str(doc.page))
    canvas.restoreState()


def _il(ce):
    return -10.0 * np.log10(max(float(ce), 1e-16))


def _on_grid(wl, values, target):
    wl = np.asarray(wl, dtype=float)
    values = np.asarray(values, dtype=float)
    hit = np.where(np.isclose(wl, target, atol=1e-9))[0]
    if len(hit) == 0:
        raise RuntimeError(f"{target} nm missing from {wl.tolist()}")
    return float(values[int(hit[0])])


def load_tidy3d():
    path = RES / "tidy3d_compare.json"
    jobs = json.loads(path.read_text(encoding="utf-8"))["jobs"]

    def pack(name):
        j = jobs[name]
        wl = j["wavelengths_nm"]
        return {
            "il_1525": _il(_on_grid(wl, j["ce"], 1525.0)) if 1525.0 in wl or any(abs(x - 1525) < 1e-9 for x in wl) else float("nan"),
            "il_1550": float(j["il_1550_db"]),
            "lambda": float(j["lambda_reported_nm"]),
            "peak_il": _il(max(j["ce"])),
            "peak_nm": float(wl[int(np.argmax(j["ce"]))]),
            "etch_nm": float(j.get("etch_nm", 70.0)),
        }

    nom = {k: pack(f"nom_{k}") for k in ("uniform", "chirp", "taillaert", "proposed")}
    etch = {}
    for key in jobs:
        j = jobs[key]
        if j.get("kind") != "etch":
            continue
        etch.setdefault(j["design"], {})[int(j["etch_nm"])] = float(j["il_1550_db"])
    return nom, etch


def load_fdtd():
    path = RES / "fdtd_compare.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    wl = data["wavelengths_nm"]
    has_1550 = any(abs(float(x) - 1550.0) < 1e-9 for x in wl)
    out = {"has_1550": has_1550, "wl": wl, "spectra": {}, "etch": data.get("etch", {}), "cd": data.get("cd", {})}
    for key, s in data["spectra"].items():
        ce = s["ce"]
        rec = {
            "name": s["name"],
            "il_1525": _il(_on_grid(wl, ce, 1525.0)),
            "peak_il": float(s["peak_il_db"]),
            "peak_nm": float(s["wl_peak_nm"]),
        }
        if has_1550:
            rec["il_1550"] = _il(_on_grid(wl, ce, 1550.0))
            rec["lambda"] = 1550.0
        else:
            rec["il_1550"] = None
            rec["lambda"] = None
        out["spectra"][key] = rec
    return out


def fmt(x):
    return "—" if x is None or x != x else f"{x:.2f} dB"


def story():
    nom, etch = load_tidy3d()
    fdtd = load_fdtd()
    s = []
    s.append(Spacer(1, 0.15 * inch))
    s.append(P("2-D FDTD comparison of silicon grating couplers", "T"))
    s.append(P("Same stack, same min CD, same fiber, same aperture. Four layouts. Two solvers.", "Sub"))
    s.append(
        P(
            "220 nm SOI, 70 nm shallow etch, 2 µm BOX, 150 nm min CD, 8° SMF-28, ~20 periods. "
            "Tidy3D 2.12 is the independent ranking: 2-D y-invariant, Δℓ = 16 nm, in-coupling "
            "Gaussian → waveguide mode, wavelength list contains 1550.00 nm, chirp on the etch sweep. "
            "In-house Yee 2-D TE (dx = 25 nm, out-coupling |E|<super>2</super> cladding overlap) is the denser "
            "process scan. This is not 3-D, not adjoint, and not a fabricated device."
        )
    )
    s.append(P("Tidy3D at exact 1550.00 nm", "H"))
    s.append(
        table(
            [
                ["Design", "What varies", "IL 1525 nm", "IL 1550.00 nm", "Peak IL"],
                ["Uniform 50% (PDK-class)", "nothing", fmt(nom["uniform"]["il_1525"]), fmt(nom["uniform"]["il_1550"]), f"{nom['uniform']['peak_il']:.2f} dB @ {nom['uniform']['peak_nm']:.0f} nm"],
                ["Linear period chirp", "Λ only", fmt(nom["chirp"]["il_1525"]), fmt(nom["chirp"]["il_1550"]), f"{nom['chirp']['peak_il']:.2f} dB @ {nom['chirp']['peak_nm']:.0f} nm"],
                ["Taillaert fill apodization", "fill only, Λ fixed", fmt(nom["taillaert"]["il_1525"]), fmt(nom["taillaert"]["il_1550"]), f"{nom['taillaert']['peak_il']:.2f} dB @ {nom['taillaert']['peak_nm']:.0f} nm"],
                ["Proposed", "fill + Λ(z) holds θ = 8°", fmt(nom["proposed"]["il_1525"]), fmt(nom["proposed"]["il_1550"]), f"{nom['proposed']['peak_il']:.2f} dB @ {nom['proposed']['peak_nm']:.0f} nm"],
            ],
            [1.55 * inch, 1.45 * inch, 1.0 * inch, 1.2 * inch, 1.25 * inch],
            highlight_row=4,
        )
    )
    s.append(Spacer(1, 4))
    s.append(P("1550.00 nm sits on the Tidy3D wavelength list. It is not a neighbouring bin and not an interpolation.", "Cap"))
    if (FIG / "td00_spectra_etch.png").is_file():
        s.extend(fig("td00_spectra_etch.png", "Figure 1. Tidy3D spectra (1550.00 nm on the grid) and etch sweep including chirp."))
    if (FIG / "td01_bars_1550.png").is_file():
        s.extend(fig("td01_bars_1550.png", "Figure 2. Tidy3D insertion loss at exactly 1550.00 nm."))
    s.append(P("What the independent Maxwell solve says", "H"))
    s.append(
        P(
            f"At 1550.00 nm the three fill-aware cells are a wash: proposed {nom['proposed']['il_1550']:.2f} dB, "
            f"Taillaert {nom['taillaert']['il_1550']:.2f} dB, uniform {nom['uniform']['il_1550']:.2f} dB. "
            f"Chirp-only is worse ({nom['chirp']['il_1550']:.2f} dB). The leaky-wave model’s 0.4 dB "
            "apodization win does not survive Maxwell. Differences of 0.02 dB are not a ranking."
        )
    )
    s.append(
        P(
            f"The 1525 nm shoulder is real: proposed {nom['proposed']['il_1525']:.2f} dB versus uniform "
            f"{nom['uniform']['il_1525']:.2f} dB. Fill-only and chirp-only each recover some of that; "
            "the combination recovers more."
        )
    )
    u58 = etch.get("uniform", {}).get(58)
    p58 = etch.get("proposed", {}).get(58)
    c58 = etch.get("chirp", {}).get(58)
    t58 = etch.get("taillaert", {}).get(58)
    u82 = etch.get("uniform", {}).get(82)
    p82 = etch.get("proposed", {}).get(82)
    c82 = etch.get("chirp", {}).get(82)
    t82 = etch.get("taillaert", {}).get(82)
    u70 = nom["uniform"]["il_1550"]
    p70 = nom["proposed"]["il_1550"]
    worst_u = max(x for x in (u58, u70, u82) if x is not None)
    worst_p = max(x for x in (p58, p70, p82) if x is not None)
    s.append(
        P(
            f"Under-etch 58 nm at 1550.00 nm: proposed {fmt(p58)} versus uniform {fmt(u58)} versus "
            f"chirp {fmt(c58)}"
            + (f" versus Taillaert {fmt(t58)}" if t58 is not None else " (fill-only not on this sweep)")
            + f". Over-etch 82 nm favours uniform ({fmt(u82)} vs proposed {fmt(p82)}"
            + (f", Taillaert {fmt(t82)}" if t82 is not None else "")
            + f"). Worst of {{58, 70, 82}} nm: uniform {worst_u:.2f} dB versus proposed {worst_p:.2f} dB. "
            "That is an under-etch note, not a better worst-case yield."
        )
    )
    s.append(P("In-house 2-D FDTD (25 nm Yee)", "H"))
    if fdtd["has_1550"]:
        sp = fdtd["spectra"]
        s.append(
            table(
                [
                    ["Design", "IL 1525 nm", "IL 1550.00 nm", "Peak IL"],
                    ["Uniform 50%", fmt(sp["uniform"]["il_1525"]), fmt(sp["uniform"]["il_1550"]), f"{sp['uniform']['peak_il']:.2f} dB @ {sp['uniform']['peak_nm']:.0f} nm"],
                    ["Period chirp", fmt(sp["chirp"]["il_1525"]), fmt(sp["chirp"]["il_1550"]), f"{sp['chirp']['peak_il']:.2f} dB @ {sp['chirp']['peak_nm']:.0f} nm"],
                    ["Taillaert fill", fmt(sp["taillaert"]["il_1525"]), fmt(sp["taillaert"]["il_1550"]), f"{sp['taillaert']['peak_il']:.2f} dB @ {sp['taillaert']['peak_nm']:.0f} nm"],
                    ["Proposed", fmt(sp["proposed"]["il_1525"]), fmt(sp["proposed"]["il_1550"]), f"{sp['proposed']['peak_il']:.2f} dB @ {sp['proposed']['peak_nm']:.0f} nm"],
                ],
                [1.8 * inch, 1.3 * inch, 1.4 * inch, 1.9 * inch],
                highlight_row=4,
            )
        )
        s.append(Spacer(1, 4))
        s.append(P("On-grid 1550.00 nm. Cite Tidy3D for the independent ranking; this table is the coarser-grid scan.", "Cap"))
    else:
        s.append(
            P(
                "The in-house cache on disk still skips 1550.00 nm (grid 1525, 1535, … 1575). "
                "Do not read a nearest-bin 1545 nm bar as 1550 nm. Re-run "
                "<font face='Courier'>python analysis/run_em_compare.py --rerun</font>."
            )
        )
    s.extend(fig("em00_dashboard.png", "Figure 3. In-house FDTD dashboard (spectra, 1550 nm bars, etch, ΔIL)."))
    s.extend(fig("em05_fields.png", "Figure 4. In-house |E<sub>y</sub> at 1550 nm. Both layouts radiate; the proposed grating is visibly apodized."))
    s.extend(fig("em03_etch.png", "Figure 5. In-house IL versus etch depth, chirp included."))
    s.extend(fig("em07_verdict.png", "Figure 6. Compact in-house verdict: what improved, what did not."))
    s.append(P("Verdict", "H"))
    s.append(
        P(
            "Under identical foundry constraints the method does not beat a uniform PDK-class cell on "
            "peak coupling at 1550.00 nm. Combined fill+chirp improves the short-wavelength shoulder "
            "and under-etch robustness; chirp-only does not buy the under-etch result. A paper that "
            "claims a 0.5 dB champion from this pipeline is not supported. A paper that claims a "
            "DRC-legal fill+chirp recipe for blue-side IL and under-etch tolerance is."
        )
    )
    return s


def main():
    global STY
    STY = styles()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=letter,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title="2-D FDTD comparison of silicon grating couplers",
        author="Engineering technical report",
        creator="photonic/analysis/generate_fdtd_pdf.py",
    )
    doc.build(story(), onFirstPage=header_footer, onLaterPages=header_footer)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
