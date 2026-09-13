"""Load TIDY3D_API_KEY from the repo .env and authenticate. Do not print the key."""
from __future__ import annotations

import os
from pathlib import Path


def load_key() -> str:
    env = os.environ.get("TIDY3D_API_KEY", "").strip()
    if env:
        return env
    here = Path(__file__).resolve()
    candidates = [
        here.parents[1] / ".env",
        here.parents[2] / ".env",
        Path.home() / ".tidy3d" / ".env",
    ]
    for env_path in candidates:
        if not env_path.is_file():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "TIDY3D_API_KEY":
                return v.strip().strip('"').strip("'")
    raise RuntimeError("TIDY3D_API_KEY not found in the environment or a .env file")


def configure():
    key = load_key()
    os.environ["TIDY3D_API_KEY"] = key
    import tidy3d.web as web

    web.configure(key)
    return web


if __name__ == "__main__":
    web = configure()
    print("configured")
    web.test()
    print("auth ok")
    try:
        acc = web.account()
        print(type(acc).__name__, str(acc)[:400])
    except Exception as e:
        print("account:", type(e).__name__, str(e)[:300])
