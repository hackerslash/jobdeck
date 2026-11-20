"""Download changed per-source parquet files from the Stapply snapshot.

A source is re-downloaded only when the manifest's parquet_sha256 differs from the one we hold.
"""
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import httpx

from . import config

UA = {"User-Agent": "jobdeck/0.1"}


def manifest() -> dict:
    r = httpx.get(config.load()["manifest_url"], headers=UA, timeout=60, follow_redirects=True)
    r.raise_for_status()
    return r.json()


def read_state() -> dict:
    return json.loads(config.STATE_PATH.read_text()) if config.STATE_PATH.exists() else {}


def write_state(state: dict) -> None:
    tmp = config.STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1))
    tmp.replace(config.STATE_PATH)


def download(source: str, meta: dict) -> str:
    dest = config.RAW / f"{source}.parquet"
    part = dest.with_suffix(".part")
    h = hashlib.sha256()
    with httpx.stream("GET", meta["parquet"], headers=UA, timeout=httpx.Timeout(60, read=300),
                      follow_redirects=True) as r:
        r.raise_for_status()
        with part.open("wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
                h.update(chunk)
    if h.hexdigest() != meta["parquet_sha256"]:
        part.unlink(missing_ok=True)
        raise ValueError(f"{source}: sha256 mismatch")
    part.replace(dest)
    return meta["parquet_sha256"]


def sync(log=lambda m: print(m, file=sys.stderr)) -> list[str]:
    """Returns the sources whose file changed (empty list: nothing to do)."""
    config.RAW.mkdir(parents=True, exist_ok=True)
    m = manifest()
    state = read_state()
    wanted = config.load()["sources"]
    by_ats = m["by_ats"]
    missing = [s for s in wanted if s not in by_ats]
    if missing:
        log(f"not in manifest, skipped: {', '.join(missing)}")
    todo = [s for s in wanted if s in by_ats and
            (state.get(s) != by_ats[s]["parquet_sha256"] or not (config.RAW / f"{s}.parquet").exists())]
    if not todo:
        log(f"snapshot {m['generated_at']}: up to date")
        return []
    mb = sum(by_ats[s]["parquet_size_bytes"] for s in todo) / 1e6
    log(f"snapshot {m['generated_at']}: downloading {len(todo)} sources ({mb:.0f} MB)")
    changed = []
    with ThreadPoolExecutor(4) as ex:
        futs = {s: ex.submit(download, s, by_ats[s]) for s in todo}
        for s, fut in futs.items():
            try:
                state[s] = fut.result()
                changed.append(s)
                write_state(state)
                log(f"  {s}: {by_ats[s]['rows']:,} rows")
            except Exception as e:
                log(f"  {s}: FAILED {e}")
    state["_snapshot"] = m["generated_at"]
    write_state(state)
    return changed


if __name__ == "__main__":
    sync()
