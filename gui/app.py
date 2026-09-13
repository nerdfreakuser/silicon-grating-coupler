"""Local lab-notebook GUI for the photonic coupler work.

    python photonic/gui/app.py
then open http://127.0.0.1:8765
"""

from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, Response, abort, send_from_directory

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"
RESULTS = ROOT / "analysis" / "results"
FIGURES = ROOT / "analysis" / "figures"

app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static")


@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.get("/fig/<path:name>")
def fig(name: str):
    if ".." in name or not (FIGURES / name).is_file():
        abort(404)
    return send_from_directory(FIGURES, name)


@app.get("/data/<name>")
def data(name: str):
    allowed = {
        "study.json",
        "fdtd_compare.json",
        "tidy3d_compare.json",
        "tidy3d_smoke.json",
    }
    if name not in allowed:
        abort(404)
    path = RESULTS / name
    if not path.is_file():
        return Response(json.dumps({"missing": True, "name": name}), mimetype="application/json")
    return send_from_directory(RESULTS, name)


def main():
    print("Photonic coupler notebook  ->  http://127.0.0.1:8765")
    app.run(host="127.0.0.1", port=8765, debug=False)


if __name__ == "__main__":
    main()
