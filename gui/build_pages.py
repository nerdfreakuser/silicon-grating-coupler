"""Build a static snapshot of the lab notebook for GitHub Pages.

    python gui/build_pages.py
writes photonic/docs/ with relative paths (no Flask).
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"
FIG = ROOT / "analysis" / "figures"
RES = ROOT / "analysis" / "results"
PAPER = ROOT / "paper"
DESIGN = ROOT / "design"
OUT = ROOT / "docs"

JSON_FILES = (
    "tidy3d_compare.json",
    "tidy3d_align.json",
    "tidy3d_converge.json",
    "fdtd_compare.json",
    "study.json",
)
PDF_FILES = (
    PAPER / "Photonic_Coupler_Technical_Report.pdf",
    PAPER / "FDTD_Comparison.pdf",
    PAPER / "manuscript.md",
    DESIGN / "Design_Specification.pdf",
    DESIGN / "design-spec.md",
    DESIGN / "mpw-protocol.md",
)

# Cookieless pageviews for the published notebook only (not localhost).
# Dashboard: https://silicon-grating-coupler.goatcounter.com
# Create the free site once at https://www.goatcounter.com/signup
# with code silicon-grating-coupler, then enable “public dashboard”.
GOATCOUNTER = "silicon-grating-coupler"

ANALYTICS = f"""
<script data-goatcounter="https://{GOATCOUNTER}.goatcounter.com/count"
        async src="https://gc.zgo.at/count.js"></script>
<noscript>
  <img src="https://{GOATCOUNTER}.goatcounter.com/count?p=/" alt=""
       width="1" height="1" style="border:0;position:absolute" />
</noscript>
"""

FOOTER = f"""
<footer class="pub">
  <p>
    Public source:
    <a href="https://github.com/nerdfreakuser/silicon-grating-coupler">github.com/nerdfreakuser/silicon-grating-coupler</a>.
    <a href="paper/Photonic_Coupler_Technical_Report.pdf">Technical report PDF</a>.
    <a href="paper/FDTD_Comparison.pdf">FDTD note PDF</a>.
    <a href="https://{GOATCOUNTER}.goatcounter.com">Traffic</a>.
  </p>
</footer>
"""

FOOTER_CSS = """
footer.pub {
  max-width: 48rem;
  margin: 2.4rem 0 0;
  padding-top: 1rem;
  border-top: 1px solid #2c343c;
  font-family: "IBM Plex Sans", sans-serif;
  font-size: 0.85rem;
  color: #9aa39a;
}
footer.pub a { color: var(--gold); }
"""


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "figures").mkdir(parents=True)
    (OUT / "data").mkdir()
    (OUT / "paper").mkdir()

    html = (STATIC / "index.html").read_text(encoding="utf-8")
    html = html.replace('href="/static/style.css"', 'href="style.css"')
    html = html.replace('src="/static/app.js"', 'src="app.js"')
    html = html.replace('src="/fig/', 'src="figures/')
    html = html.replace("</main>", FOOTER + "\n</main>")
    if "</body>" in html:
        html = html.replace("</body>", ANALYTICS + "\n</body>")
    else:
        html += ANALYTICS
    (OUT / "index.html").write_text(html, encoding="utf-8")

    css = (STATIC / "style.css").read_text(encoding="utf-8") + FOOTER_CSS
    (OUT / "style.css").write_text(css, encoding="utf-8")

    js = (STATIC / "app.js").read_text(encoding="utf-8")
    js = js.replace('fetch("/data/', 'fetch("data/')
    (OUT / "app.js").write_text(js, encoding="utf-8")

    for png in FIG.glob("*.png"):
        shutil.copy2(png, OUT / "figures" / png.name)
    for name in JSON_FILES:
        src = RES / name
        if src.is_file():
            shutil.copy2(src, OUT / "data" / name)
    for src in PDF_FILES:
        if src.is_file():
            shutil.copy2(src, OUT / "paper" / src.name)

    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
