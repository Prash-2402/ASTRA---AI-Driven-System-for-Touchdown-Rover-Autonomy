"""Runtime settings (environment variables, see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = "0.1.0"

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass


@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: os.environ.get(
        "ASTRA_DATABASE_URL", f"sqlite:///{ROOT / 'astra.db'}"))
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("ASTRA_DATA_DIR", ROOT / "data")))
    cors_origins: list[str] = field(default_factory=lambda: os.environ.get(
        "ASTRA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173").split(","))

    @property
    def telemetry_dir(self) -> Path:
        p = self.data_dir / "telemetry"; p.mkdir(parents=True, exist_ok=True); return p

    @property
    def reports_dir(self) -> Path:
        p = self.data_dir / "reports"; p.mkdir(parents=True, exist_ok=True); return p


settings = Settings()


def software_versions() -> dict:
    import platform

    import numpy
    import scipy
    out = {"astra": VERSION, "python": platform.python_version(), "numpy": numpy.__version__, "scipy": scipy.__version__}
    try:
        import pybullet
        out["pybullet_api"] = pybullet.getAPIVersion()
    except Exception:  # noqa: BLE001
        out["pybullet_api"] = None
    try:
        import subprocess
        out["git_commit"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                                           text=True, timeout=2).stdout.strip() or None
    except Exception:  # noqa: BLE001
        out["git_commit"] = None
    return out
