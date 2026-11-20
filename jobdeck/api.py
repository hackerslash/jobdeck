import threading
import time
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import config, db, embed, nlq, pipeline, resume, sync

WEB = config.ROOT / "web" / "build"
STATUS = {"state": "idle", "last_run": None, "last_error": None, "log": []}
_update_lock = threading.Lock()

# ---------- tag rules -> view ----------

_rules = {"mtime": None, "errors": []}


def refresh_view(force=False):
    p = config.ROOT / "rules.toml"
    mtime = p.stat().st_mtime if p.exists() else 0
    if not force and mtime == _rules["mtime"]:
        return
    c = db.cur()
    if not c.execute("SELECT count(*) FROM duckdb_tables() WHERE table_name = 'jobs'").fetchone()[0]:
        return
    resume.schema()
    c.execute("""CREATE OR REPLACE VIEW jobs_m AS
                 SELECT j.*, m.pct AS match_pct, m.resume AS match_resume FROM jobs j LEFT JOIN best_match m USING (id)""")
    good, errors = [], []
    for r in config.rules():
        try:  # validate each rule on its own so one typo doesn't hide every tag
            c.execute(f"SELECT count(*) FROM (SELECT * FROM jobs_m LIMIT 1) WHERE ({r['where']})")
            good.append(r)
        except Exception as e:
            errors.append(f"{r.get('name')}: {str(e).splitlines()[0]}")
    cases = ", ".join(f"CASE WHEN ({r['where']}) THEN {pipeline.q(r['name'])} END" for r in good)
    tags = f"list_filter([{cases}], lambda x: x IS NOT NULL)" if good else "[]::VARCHAR[]"
    c.execute(f"CREATE OR REPLACE VIEW jobs_v AS SELECT *, {tags} AS tags FROM jobs_m")
    _rules.update(mtime=mtime, errors=errors)


# ---------- background updater ----------

def log(msg):
    STATUS["log"] = (STATUS["log"] + [f"{time.strftime('%H:%M:%S')} {msg}"])[-60:]


def run_update(force=False):
    if not _update_lock.acquire(blocking=False):
        return False
    try:
        STATUS.update(state="syncing", last_error=None)
        changed = sync.sync(log)
        has_jobs = db.cur().execute("SELECT count(*) FROM duckdb_tables() WHERE table_name = 'jobs'").fetchone()[0]
        if changed or force or not has_jobs:
            STATUS["state"] = "building"
            pipeline.build(log)
            db.cur().execute("DROP TABLE IF EXISTS qcache")
            refresh_view(force=True)
            _facet_cache.clear()
        STATUS["state"] = "embedding"
        embed.embed(log)
        resume.recompute()
    except Exception as e:
        STATUS["last_error"] = str(e)
        log("ERROR " + traceback.format_exc(limit=2))
    finally:
        STATUS.update(state="idle", last_run=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        _update_lock.release()
    return True


def scheduler():
    while True:
        run_update()
        time.sleep(config.load().get("sync_interval_minutes", 60) * 60)


@asynccontextmanager
async def lifespan(_):
    refresh_view(force=True)
    threading.Thread(target=scheduler, daemon=True).start()
    yield


app = FastAPI(lifespan=lifespan)

# ---------- search ----------

LIST_COLS = ("id, source, company, title, role, seniority, posted, location, countries, remote, remote_region, employment, "
             "salary_usd_min, salary_usd_max, salary_summary, skills, years_min, visa, equity, relocation, lang, tags, apply_url, "
             "match_pct, match_resume")
MULTI = {"role": "role", "seniority": "seniority", "remote": "remote", "region": "remote_region",
         "employment": "employment", "source": "source", "lang": "lang"}
SORTS = {"newest": "posted DESC", "salary": "salary_usd_max DESC NULLS LAST, posted DESC",
         "company": "company, posted DESC", "relevance": "score DESC, posted DESC",
         "match": "match_pct DESC NULLS LAST, posted DESC"}


class F:
    """Parsed filter params shared by /jobs and /facets."""

    def __init__(self, q, role, seniority, remote, region, employment, source, lang, country, skill, tag,
                 salary_min, days, years_max, visa, company, exclude_tag):
        self.q = (q or "").strip()
        self.multi = {"role": role, "seniority": seniority, "remote": remote, "region": region,
                      "employment": employment, "source": source, "lang": lang}
        self.country, self.skill, self.tag, self.exclude_tag = country, skill, tag, exclude_tag
        self.salary_min, self.days, self.years_max, self.visa, self.company = salary_min, days, years_max, visa, company

    def where(self, skip: str | None = None):
        w, a = [], []
        for k, vals in self.multi.items():
            if vals and k != skip:
                w.append(f"{MULTI[k]} IN ({', '.join('?' * len(vals))})"); a += vals
        if self.country and skip != "country":
            w.append("list_has_any(countries, ?)"); a.append(self.country)
        if self.skill and skip != "skill":
            w.append("list_has_all(skills, ?)"); a.append(self.skill)
        if self.tag and skip != "tag":
            w.append("list_has_all(tags, ?)"); a.append(self.tag)
        if self.exclude_tag:
            w.append("NOT list_has_any(tags, ?)"); a.append(self.exclude_tag)
        if self.company:
            w.append("company = ?"); a.append(self.company)
        if self.salary_min:
            w.append("salary_usd_max >= ?"); a.append(self.salary_min)
        if self.days:
            w.append(f"posted >= now() - INTERVAL {int(self.days)} DAY")
        if self.years_max is not None:
            w.append("coalesce(years_min, 0) <= ?"); a.append(self.years_max)
        if self.eligible:  # remote roles open to these countries: anywhere, their region, or listing them
            regions = sorted({nlq.region_of(c) for c in self.eligible} | {"global"})
            w.append(f"remote = 'remote' AND (remote_region IN ({', '.join('?' * len(regions))}) OR list_has_any(countries, ?))")
            a += regions + [self.eligible]
        if self.match_min:
            w.append("match_pct >= ?"); a.append(self.match_min)
        if self.visa:
            w.append("visa")
        if self.q:
            w.append("score IS NOT NULL")
        return ("WHERE " + " AND ".join(w)) if w else "", a

    def source_sql(self):
        if not self.q:
            return "(SELECT *, NULL::DOUBLE AS score FROM jobs_v)", []
        scored(self.q)
        return "(SELECT j.*, s.score FROM jobs_v j JOIN qcache s ON s.id = j.id AND s.q = ?)", [self.q]


_qlock = threading.Lock()


def scored(q: str):
    """BM25 (all terms must match, title hits boosted) computed once per query and kept until the next build."""
    with _qlock:
        c = db.cur()
        c.execute("CREATE TABLE IF NOT EXISTS qcache (q VARCHAR, id VARCHAR, score DOUBLE)")
        if c.execute("SELECT 1 FROM qcache WHERE q = ? LIMIT 1", [q]).fetchone():
            return
        if c.execute("SELECT count(DISTINCT q) FROM qcache").fetchone()[0] > 500:
            c.execute("DELETE FROM qcache")
        c.execute("""INSERT INTO qcache SELECT ?, id, score FROM (
                       SELECT id, fts_main_jobs.match_bm25(id, ?, conjunctive := 1)
                                  + CASE WHEN title ILIKE ? THEN 5 ELSE 0 END AS score FROM jobs) WHERE score IS NOT NULL""",
                  [q, q, f"%{q}%"])


def filters(q: str | None = None, role: list[str] = Query(None), seniority: list[str] = Query(None),
            remote: list[str] = Query(None), region: list[str] = Query(None), employment: list[str] = Query(None),
            source: list[str] = Query(None), lang: list[str] = Query(None), country: list[str] = Query(None),
            skill: list[str] = Query(None), tag: list[str] = Query(None), exclude_tag: list[str] = Query(None),
            salary_min: int | None = None, days: int | None = None, years_max: int | None = None,
            visa: bool = False, company: str | None = None, eligible: list[str] = Query(None),
            match_min: int | None = None) -> F:
    f = F(q, role, seniority, remote, region, employment, source, lang, country, skill, tag,
          salary_min, days, years_max, visa, company, exclude_tag)
    f.eligible, f.match_min = eligible, match_min
    return f


def ready():
    refresh_view()
    c = db.cur()
    if not c.execute("SELECT count(*) FROM duckdb_views() WHERE view_name = 'jobs_v'").fetchone()[0]:
        raise HTTPException(503, "no data yet: first sync/build is still running")
    return c


Filters = Annotated[F, Depends(filters)]


@app.get("/api/jobs")
def jobs(f: Filters, sort: str = "newest", offset: int = 0, limit: int = Query(50, le=200)):
    t0 = time.time()
    c = ready()
    src, sa = f.source_sql()
    w, wa = f.where()
    order = SORTS.get(sort if (sort != "relevance" or f.q) else "newest", SORTS["newest"])
    total = c.execute(f"SELECT count(*) FROM {src} {w}", sa + wa).fetchone()[0]
    cur = c.execute(f"SELECT {LIST_COLS} FROM {src} {w} ORDER BY {order} LIMIT ? OFFSET ?", sa + wa + [limit, offset])
    cols = [d[0] for d in cur.description]
    return {"total": total, "took_ms": round((time.time() - t0) * 1000), "jobs": [dict(zip(cols, r)) for r in cur.fetchall()]}


@app.get("/api/export")
def export(f: Filters, sort: str = "newest"):
    """Every job matching the current filters as CSV, apply links included."""
    import csv, io
    c = ready()
    src, sa = f.source_sql()
    w, wa = f.where()
    order = SORTS.get(sort if (sort != "relevance" or f.q) else "newest", SORTS["newest"])
    rows = c.execute(f"""SELECT title, company, location, remote, match_pct, match_resume, salary_usd_min, salary_usd_max,
                                strftime(posted, '%Y-%m-%d'), apply_url FROM {src} {w} ORDER BY {order} LIMIT 10000""", sa + wa).fetchall()
    buf = io.StringIO()
    out = csv.writer(buf)
    out.writerow(["title", "company", "location", "remote", "match_pct", "best_resume", "pay_usd_min", "pay_usd_max", "posted", "apply_url"])
    out.writerows(rows)
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="jobdeck-{time.strftime("%Y%m%d")}.csv"'})


_facet_cache: dict = {}
FACETS = {"role": "role", "seniority": "seniority", "remote": "remote", "region": "remote_region",
          "employment": "employment", "source": "source", "lang": "lang"}


@app.get("/api/facets")
def facets(f: Filters):
    """Counts per facet value, each computed with every *other* active filter applied."""
    c = ready()
    src, sa = f.source_sql()
    out = {}
    for name, col in FACETS.items():
        w, wa = f.where(skip=name)
        out[name] = c.execute(f"SELECT {col}, count(*) n FROM {src} {w} GROUP BY 1 HAVING {col} IS NOT NULL ORDER BY n DESC",
                              sa + wa).fetchall()
    for name, col, lim in (("country", "countries", 80), ("skill", "skills", 200), ("tag", "tags", 100)):
        w, wa = f.where(skip=name)
        out[name] = c.execute(f"SELECT x, count(*) n FROM (SELECT unnest({col}) x FROM {src} {w}) GROUP BY 1 ORDER BY n DESC LIMIT {lim}",
                              sa + wa).fetchall()
    return out


@app.get("/api/job/{job_id:path}/similar")
def similar(job_id: str, limit: int = Query(8, le=30)):
    c = ready()
    cur = c.execute(f"""
      WITH me AS (SELECT e.v, j.company FROM jobs j JOIN emb e ON e.hash = j.content_hash WHERE j.id = ?)
      SELECT j.id, j.title, j.company, j.role, j.seniority, j.location, j.salary_usd_min, j.salary_usd_max, j.posted,
             round(array_cosine_similarity(e.v, me.v), 3) AS sim
      FROM jobs j JOIN emb e ON e.hash = j.content_hash, me
      WHERE j.id <> ?
      QUALIFY row_number() OVER (PARTITION BY j.company ORDER BY sim DESC) <= 2  -- keep one employer from filling the list
      ORDER BY sim DESC LIMIT ?""", [job_id, job_id, limit])
    return [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]


def local_only(request: Request):
    """Resume data and sync stay on this machine: requests through the public tunnel carry cf-connecting-ip."""
    if "cf-connecting-ip" in request.headers:
        raise HTTPException(403, "Only available on the machine running jobdeck")


@app.get("/api/parse")
def parse(q: str):
    return nlq.parse(q)


@app.get("/api/resumes", dependencies=[Depends(local_only)])
def resumes():
    return resume.listing()


@app.post("/api/resumes", dependencies=[Depends(local_only)])
async def add_resume(file: UploadFile = File(...), name: str = Form("")):
    data = await file.read()
    if len(data) > 5_000_000:
        raise HTTPException(413, "Resume files are limited to 5 MB")
    try:
        return resume.add(name.strip(), file.filename or "resume.txt", data)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.delete("/api/resumes/{rid}", dependencies=[Depends(local_only)])
def delete_resume(rid: int):
    resume.delete(rid)
    return {"ok": True}


@app.get("/api/job/{job_id:path}/match")
def job_match(job_id: str):
    return resume.breakdown(job_id)


@app.get("/api/status")
def status():
    c = db.cur()
    has = c.execute("SELECT count(*) FROM duckdb_tables() WHERE table_name = 'jobs'").fetchone()[0]
    stats = c.execute("SELECT count(*), count(DISTINCT company), max(posted) FROM jobs").fetchone() if has else (0, 0, None)
    embedded = c.execute("SELECT count(*) FROM jobs j JOIN emb e ON e.hash = j.content_hash").fetchone()[0] \
        if has and c.execute("SELECT count(*) FROM duckdb_tables() WHERE table_name = 'emb'").fetchone()[0] else 0
    st = sync.read_state()
    return {**STATUS, "jobs": stats[0], "companies": stats[1], "newest": stats[2], "embedded": embedded,
            "snapshot": st.get("_snapshot"), "sources": len(config.load()["sources"]), "rule_errors": _rules["errors"]}


@app.post("/api/update")
def update(request: Request, force: bool = False):
    if "cf-connecting-ip" in request.headers:  # came through the public tunnel: sync stays a local-only action
        raise HTTPException(403, "sync can only be triggered locally")
    started = threading.Thread(target=run_update, kwargs={"force": force}, daemon=True)
    if _update_lock.locked():
        return {"started": False, "state": STATUS["state"]}
    started.start()
    return {"started": True}


@app.get("/api/job/{job_id:path}")  # ids can contain "/" (workday)
def job(job_id: str):
    c = ready()
    cur = c.execute("SELECT * EXCLUDE (embed_text, content_hash) FROM jobs_v WHERE id = ?", [job_id])
    row = cur.fetchone()
    if not row:
        raise HTTPException(404)
    return dict(zip([d[0] for d in cur.description], row))


# ---------- frontend ----------

if WEB.exists():
    app.mount("/_app", StaticFiles(directory=WEB / "_app"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Unknown API route")
        f = (WEB / path).resolve()
        if path and f.is_file() and WEB in f.parents:
            return FileResponse(f)
        return FileResponse(WEB / "index.html")
