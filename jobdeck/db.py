"""One DuckDB instance per process (DuckDB allows a single writing process per file); use cursors per thread."""
import threading

import duckdb

from . import config

_con = None
_lock = threading.Lock()


def cur() -> duckdb.DuckDBPyConnection:
    global _con
    with _lock:
        if _con is None:
            config.DATA.mkdir(parents=True, exist_ok=True)
            _con = duckdb.connect(str(config.DB_PATH))
            _con.execute("INSTALL fts; LOAD fts;")
    c = _con.cursor()
    c.execute("SET TimeZone = 'UTC'")
    return c
