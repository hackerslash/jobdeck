"""Resumes: local text extraction, parsing, embedding, and the job match score."""
import io
import re
import time
from datetime import date

import pyarrow as pa

from . import db, embed, pipeline, taxonomy as T

LEVEL = {"intern": 0, "junior": 1, "mid": 2, "senior": 3, "staff": 4, "lead": 4, "manager": 4, "principal": 5, "director": 6}
GROUP = {**dict.fromkeys(["software", "backend", "fullstack", "frontend", "mobile", "architect", "gamedev", "blockchain"], "swe"),
         **dict.fromkeys(["data_eng", "data_analytics", "ml_ai"], "data"),
         **dict.fromkeys(["devops", "security", "it_ops", "support_eng", "embedded", "qa"], "infra"),
         **dict.fromkeys(["product", "design", "eng_mgmt", "solutions", "devrel", "tech_writing"], "adjacent")}
W = {"sem": 0.45, "skill": 0.30, "exp": 0.15, "role": 0.10}


def schema():
    c = db.cur()
    c.execute("CREATE SEQUENCE IF NOT EXISTS resume_seq")
    c.execute(f"""CREATE TABLE IF NOT EXISTS resumes (id INTEGER PRIMARY KEY DEFAULT nextval('resume_seq'), name VARCHAR,
                  filename VARCHAR, created TIMESTAMP, text VARCHAR, skills VARCHAR[], roles VARCHAR[], years DOUBLE,
                  seniority VARCHAR, vec FLOAT[{embed.DIM}])""")
    c.execute("ALTER TABLE resumes ADD COLUMN IF NOT EXISTS cos_lo DOUBLE")
    c.execute("ALTER TABLE resumes ADD COLUMN IF NOT EXISTS cos_hi DOUBLE")
    c.execute("CREATE TABLE IF NOT EXISTS best_match (id VARCHAR, pct DOUBLE, resume VARCHAR)")
    return c


# ---------- extraction ----------

def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
    if name.endswith(".docx"):
        import docx
        d = docx.Document(io.BytesIO(data))
        cells = [c.text for t in d.tables for r in t.rows for c in r.cells]
        return "\n".join([p.text for p in d.paragraphs] + cells)
    return data.decode("utf-8", "replace")


# ---------- parsing ----------

MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
RANGE = re.compile(rf"(?:{MON}\s+|(\d{{1,2}})\s*[/.-]\s*)?((?:19|20)\d{{2}})\s*(?:-|–|—|to|until)\s*"
                   rf"(?:{MON}\s+|(\d{{1,2}})\s*[/.-]\s*)?((?:19|20)\d{{2}}|present|current|now|today|date)", re.I)
EDU = re.compile(r"universit|college|bachelor|master|b\.?tech|m\.?tech|b\.?sc|m\.?sc|degree|school|education|phd|diploma", re.I)
MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()


def years_of_experience(text: str) -> float | None:
    """Union of dated work ranges (education lines skipped) so overlapping jobs aren't double counted."""
    now = date.today().year * 12 + date.today().month - 1
    spans = []
    for line in text.splitlines():
        if EDU.search(line):
            continue
        for m in RANGE.finditer(line):
            m1, n1, y1, m2, n2, y2 = m.groups()
            a = int(y1) * 12 + (MONTHS.index(m1[:3].lower()) if m1 else int(n1) - 1 if n1 and 0 < int(n1) <= 12 else 0)
            b = now if not y2[0].isdigit() else int(y2) * 12 + (MONTHS.index(m2[:3].lower()) if m2 else int(n2) - 1 if n2 and 0 < int(n2) <= 12 else 11)
            if 0 <= b - a <= 50 * 12 and a <= now:
                spans.append((a, min(b, now)))
    total, end = 0, -1
    for a, b in sorted(spans):
        if b > end:
            total += b - max(a, end)
            end = b
    if total:
        return round(total / 12, 1)
    m = re.search(r"(\d{1,2})\+?\s*(?:years|yrs)(?:\s+of)?(?:\s+\w+){0,3}\s+experience", text, re.I)
    return float(m.group(1)) if m else None


def skills_of(text: str) -> list[str]:
    amap = pipeline.alias_map()
    ctx = "[" + ", ".join(f"CASE WHEN regexp_matches(orig, {pipeline.q(rx)}) THEN {pipeline.q(n)} END" for n, rx in T.CONTEXT_SKILLS.items()) + "]"
    return db.cur().execute(f"""
      SELECT list_sort(list_distinct(list_concat(
        list_transform(list_filter(regexp_extract_all(dl, '[a-z0-9#+]+(?:[._-][a-z0-9#+]+)*'), lambda x: {amap}[x] IS NOT NULL), lambda x: {amap}[x]),
        list_filter({ctx}, lambda x: x IS NOT NULL))))
      FROM (SELECT orig, {pipeline.phrases('lower(orig)')} AS dl FROM (SELECT ?::VARCHAR AS orig))""", [text]).fetchone()[0]


def roles_of(text: str) -> list[str]:
    """Role families from title-like lines (short lines), most frequent first."""
    counts: dict[str, int] = {}
    for line in text.lower().splitlines():
        line = line.strip()
        if 3 < len(line) < 90 and not re.search(T.NOT_TECH, line):
            r = next((n for n, rx in T.ROLES if re.search(rx, line)), None)
            if r:
                counts[r] = counts.get(r, 0) + 1
    return [r for r, _ in sorted(counts.items(), key=lambda x: -x[1])][:3]


def seniority_of(text: str, years: float | None) -> str:
    head = "\n".join(text.lower().splitlines()[:25])
    for level in ("principal", "staff", "lead", "senior"):
        if re.search(dict(T.SENIORITY)[level], head):
            return level
    if years is None:
        return "mid"
    return "intern" if years < 0.5 else "junior" if years < 2.5 else "mid" if years < 5.5 else "senior" if years < 9 else "staff"


def add(name: str, filename: str, data: bytes) -> dict:
    text = re.sub(r"[ \t\u00a0\u2007\u202f]+", " ", extract_text(filename, data)).strip()  # some fonts export spaces as NBSP
    if len(text) < 200:
        raise ValueError("Couldn't read enough text from this file. Scanned-image PDFs need OCR first; try a text PDF, DOCX or TXT.")
    years = years_of_experience(text)
    skills, roles = skills_of(text), roles_of(text)
    level = seniority_of(text, years)
    summary = f"{', '.join(roles)} | {level} | {', '.join(skills)} | {text[:1800]}"
    vec = embed.encode([embed.QUERY_PREFIX + summary])[0]
    c = schema()
    c.register("v", pa.table({"v": pa.FixedSizeListArray.from_arrays(pa.array(vec, pa.float32()), embed.DIM)}))
    rid = c.execute(f"""INSERT INTO resumes (name, filename, created, text, skills, roles, years, seniority, vec)
                        SELECT ?, ?, now(), ?, ?, ?, ?, ?, v::FLOAT[{embed.DIM}] FROM v RETURNING id""",
                    [name or filename, filename, text, skills, roles, years, level]).fetchone()[0]
    c.unregister("v")
    recompute()
    return get(rid)


def listing() -> list[dict]:
    cur = schema().execute("""SELECT r.id, r.name, r.filename, r.created, r.skills, r.roles, r.years, r.seniority, length(r.text) AS chars,
                                     (SELECT count(*) FROM best_match m WHERE m.resume = r.name) AS best_for
                              FROM resumes r ORDER BY r.created DESC""")
    return [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]


def get(rid: int) -> dict:
    return next((r for r in listing() if r["id"] == rid), {})


def delete(rid: int):
    schema().execute("DELETE FROM resumes WHERE id = ?", [rid])
    recompute()


# ---------- match score ----------

def score_sql(where: str = "") -> str:
    """Per (job, resume) score components; every weight and curve is local and inspectable."""
    lv = "MAP {" + ", ".join(f"'{k}': {v}" for k, v in LEVEL.items()) + "}"
    grp = "MAP {" + ", ".join(f"'{k}': '{v}'" for k, v in GROUP.items()) + "}"
    return f"""
    SELECT j.id, r.id AS rid, r.name AS resume,
      -- calibrated per resume against the whole corpus: its median job -> 0, its top 0.01% -> 1
      greatest(0, least(1, (array_cosine_similarity(e.v, r.vec) - r.cos_lo) / (r.cos_hi - r.cos_lo))) AS sem,
      -- smoothed coverage: a job listing 1-2 skills can't hand out a perfect score
      (len(list_intersect(j.skills, r.skills)) + 0.5) / (len(j.skills) + 1) AS skill,
      0.5 * CASE WHEN j.years_min IS NULL OR r.years IS NULL THEN 0.8
                 WHEN r.years >= j.years_min THEN CASE WHEN r.years - j.years_min > 8 THEN 0.8 ELSE 1 END
                 ELSE greatest(0, 1 - (j.years_min - r.years) / 4) END
        + 0.5 * greatest(0, 1 - 0.3 * abs({lv}[j.seniority] - {lv}[r.seniority])) AS exp,
      CASE WHEN j.role IS NULL OR len(r.roles) = 0 THEN 0.6 WHEN list_contains(r.roles, j.role) THEN 1
           WHEN list_contains(list_transform(r.roles, lambda x: {grp}[x]), {grp}[j.role]) THEN 0.75 ELSE 0.3 END AS role,
      list_intersect(j.skills, r.skills) AS matched,
      list_filter(j.skills, lambda x: NOT list_contains(r.skills, x)) AS missing
    FROM jobs j JOIN emb e ON e.hash = j.content_hash CROSS JOIN resumes r {where}"""


PCT = f"round(100 * ({W['sem']} * sem + {W['skill']} * skill + {W['exp']} * exp + {W['role']} * role))"


def recompute():
    t0 = time.time()
    c = schema()
    has = c.execute("SELECT count(*) FROM resumes").fetchone()[0] and \
        c.execute("SELECT count(*) FROM duckdb_tables() WHERE table_name IN ('jobs', 'emb')").fetchone()[0] == 2
    if not has:
        c.execute("DELETE FROM best_match")
        return
    c.execute("""UPDATE resumes SET cos_lo = s.lo, cos_hi = s.hi FROM (
                   SELECT r.id, quantile_cont(array_cosine_similarity(e.v, r.vec), 0.5) AS lo,
                          quantile_cont(array_cosine_similarity(e.v, r.vec), 0.9999) AS hi
                   FROM emb e CROSS JOIN resumes r GROUP BY r.id) s WHERE resumes.id = s.id""")
    c.execute(f"""CREATE OR REPLACE TABLE best_match AS
                  SELECT id, max(pct) AS pct, arg_max(resume, pct) AS resume
                  FROM (SELECT id, resume, {PCT} AS pct FROM ({score_sql()})) GROUP BY id""")
    print(f"match scores recomputed in {time.time() - t0:.1f}s")


def breakdown(job_id: str) -> list[dict]:
    cur = schema().execute(f"SELECT resume, {PCT} AS pct, sem, skill, exp, role, matched, missing FROM ({score_sql('WHERE j.id = ?')}) ORDER BY pct DESC",
                           [job_id])
    return [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
