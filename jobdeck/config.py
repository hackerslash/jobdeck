import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
DB_PATH = DATA / "jobs.duckdb"
STATE_PATH = DATA / "state.json"


def load() -> dict:
    return tomllib.loads((ROOT / "config.toml").read_text())


def rules() -> list[dict]:
    p = ROOT / "rules.toml"
    return tomllib.loads(p.read_text()).get("tag", []) if p.exists() else []
