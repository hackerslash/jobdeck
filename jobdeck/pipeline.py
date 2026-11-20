"""Raw Stapply parquet -> cleaned, enriched `jobs` table in DuckDB (all SQL, runs in parallel)."""
import sys
import time

from . import config, db, taxonomy as T


def q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def case_first(pairs, expr, default="NULL") -> str:
    return "CASE " + " ".join(f"WHEN regexp_matches({expr}, {q(rx)}) THEN {q(name)}" for name, rx in pairs) + f" ELSE {default} END"


def alias_map() -> str:
    pairs = {}
    for canon, (_, aliases) in T.SKILLS.items():
        for a in aliases.split():
            pairs[a] = canon
    return "MAP {" + ", ".join(f"{q(k)}: {q(v)}" for k, v in pairs.items()) + "}"


def phrases(expr: str) -> str:
    for rx, rep in T.PHRASES:
        expr = f"regexp_replace({expr}, {q(rx)}, {q(rep)}, 'g')"
    return expr


def lang_req(lang: str, words: str) -> str:
    rx = (rf"(fluent|fluency|proficien\w*|native|business[- ]level|professional|excellent|strong|working) (command of |knowledge of |skills in )?(in )?({words})"
          rf"|({words}) (\(?c1|\(?c2|fluency|native|speaking|language skills|is (a )?(must|required))")
    return f"CASE WHEN regexp_matches(dl, {q(rx)}) THEN [{q(lang)}] ELSE [] END"


def sql_list(xs) -> str:
    return "[" + ", ".join(q(x) for x in sorted(xs)) + "]"


def place_country() -> str:
    """Country from free-text location parts (`lparts`), for rows the source left without one."""
    places = "MAP {" + ", ".join(f"{q(k)}: {q(v)}" for k, v in T.PLACES.items()) + "}"
    states, iso2 = sql_list(T.US_STATES), sql_list(x.lower() for x in T.ISO2)
    return f"""coalesce(
        list_filter(list_transform(lparts, lambda p: {places}[p]), lambda x: x IS NOT NULL)[1],
        CASE WHEN len(lparts) = 2 AND list_contains({states}, lparts[2]) THEN 'US' END,
        CASE WHEN (len(lparts) >= 3 OR len(lparts) = 1) AND list_contains({iso2}, lparts[-1]) THEN upper(lparts[-1]) END,
        CASE WHEN list_contains({states}, lparts[-1]) THEN 'US' END)"""


def build(log=lambda m: print(m, file=sys.stderr)) -> int:
    cfg = config.load()
    files = [str(config.RAW / f"{s}.parquet") for s in cfg["sources"] if (config.RAW / f"{s}.parquet").exists()]
    if not files:
        raise SystemExit("no raw files; run sync first")
    t0 = time.time()
    con = db.cur()
    con.execute("SET preserve_insertion_order=false")
    fx = "MAP {" + ", ".join(f"{q(k)}: {v}" for k, v in T.FX.items()) + "}"
    period = "MAP {" + ", ".join(f"{q(k)}: {v}" for k, v in T.PERIOD.items()) + "}"
    agg = "MAP {" + ", ".join(f"{q(k)}: {v}" for k, v in T.AGGREGATORS.items()) + "}"
    ctx = "[" + ", ".join(f"CASE WHEN regexp_matches(orig, {q(rx)}) THEN {q(name)} END" for name, rx in T.CONTEXT_SKILLS.items()) + "]"
    filter_tech = "WHERE role IS NOT NULL" if cfg.get("role_filter", "tech") == "tech" else ""

    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE base AS
    WITH src AS (
      SELECT *, coalesce(try_cast(posted_at AS TIMESTAMPTZ), try_cast(source_created_at AS TIMESTAMPTZ)) AS posted
      FROM read_parquet({files}, union_by_name = true)
      WHERE NOT coalesce(is_stale, false) AND title IS NOT NULL AND coalesce(apply_url, url) IS NOT NULL
    ), cls AS (
      SELECT *, lower(trim(regexp_replace(title, '\\s*\\((m|f|w|d|x|h|all genders?)(/(m|f|w|d|x|h|div))+\\)\\s*', ' ', 'gi'))) AS lt
      FROM src WHERE posted >= now() - INTERVAL {int(cfg.get('max_age_days', 180))} DAY
    )
    SELECT *,
      CASE WHEN regexp_matches(lt, {q(T.NOT_TECH)}) THEN NULL ELSE {case_first(T.ROLES, 'lt')} END AS role,
      {case_first(T.SENIORITY, 'lt', q('mid'))} AS seniority
    FROM cls
    """)
    n_all = con.execute("SELECT count(*) FROM base").fetchone()[0]
    log(f"  {n_all:,} fresh rows from {len(files)} sources ({time.time()-t0:.0f}s)")

    con.execute(f"""
    CREATE OR REPLACE TEMP TABLE enriched AS
    WITH t AS (
      SELECT *, left(coalesce(description, ''), 12000) AS d,
             title || ' ' || left(coalesce(description, ''), 12000) AS orig
      FROM base {filter_tech}
    ), t2 AS (
      SELECT *, {phrases("lower(orig)")} AS dl FROM t
    ), t3 AS (
      SELECT *,
        list_filter(json_extract_string(locations, '$[*].country_iso'), lambda x: x IS NOT NULL AND x <> '') AS loc_cc,
        list_transform(string_split(lower(coalesce(location, '')), ','), lambda x: trim(x)) AS lparts,
        regexp_extract_all(dl, '[a-z0-9#+]+(?:[._-][a-z0-9#+]+)*') AS tokens,
        [len(regexp_extract_all(left(dl, 3000), '\\b(the|and|with|you|our|will|for|are)\\b')), len(regexp_extract_all(left(dl, 3000), '\\b(und|der|die|das|mit|wir|sie|für|ist)\\b')), len(regexp_extract_all(left(dl, 3000), '\\b(et|les|des|vous|nous|pour|une|est)\\b')), len(regexp_extract_all(left(dl, 3000), '\\b(y|los|las|para|con|una|por|del)\\b')), len(regexp_extract_all(left(dl, 3000), '\\b(het|van|wij|je|een|voor|zijn|naar)\\b')), len(regexp_extract_all(left(dl, 3000), '\\b(os|com|uma|você|não|são|para|seu)\\b'))] AS lc
      FROM t2
    )
    SELECT
      global_id AS id, ats_type AS source, trim(company) AS company, trim(title) AS title,
      role, seniority, posted,
      coalesce(apply_url, url) AS apply_url, url,
      location,
      coalesce(nullif(list_distinct(list_concat(loc_cc, CASE WHEN coalesce(country_iso, '') <> '' THEN [country_iso] ELSE [] END)), []),
               list_filter([{place_country()}], lambda x: x IS NOT NULL)) AS countries,
      CASE workplace_type WHEN 'remote' THEN 'remote' WHEN 'onsite_or_remote' THEN 'remote' WHEN 'hybrid' THEN 'hybrid'
           WHEN 'onsite' THEN 'onsite' ELSE CASE WHEN is_remote OR lt LIKE '%remote%' THEN 'remote' END END AS remote,
      CASE WHEN NOT coalesce(workplace_type IN ('remote', 'onsite_or_remote') OR is_remote OR lt LIKE '%remote%', false) THEN NULL
           WHEN regexp_matches(lower(title || ' ' || coalesce(location, '')), 'anywhere|worldwide|global|work from anywhere|fully distributed') THEN 'global'
           WHEN regexp_matches(lower(title || ' ' || coalesce(location, '')), 'emea|europe|\\beu\\b|\\bcet\\b') THEN 'europe'
           WHEN regexp_matches(lower(title || ' ' || coalesce(location, '')), 'latam|latin america|south america') THEN 'latam'
           WHEN regexp_matches(lower(title || ' ' || coalesce(location, '')), 'apac|asia') THEN 'apac'
           WHEN regexp_matches(lower(title || ' ' || coalesce(location, '')), 'north america|americas|\\bus\\b|\\busa\\b|united states|canada') THEN 'americas'
      END AS remote_region,
      CASE employment_type WHEN 'FULL_TIME' THEN 'full_time' WHEN 'PART_TIME' THEN 'part_time' WHEN 'CONTRACT' THEN 'contract'
           WHEN 'INTERN' THEN 'internship' WHEN 'TEMPORARY' THEN 'temporary' ELSE
           CASE WHEN seniority = 'intern' THEN 'internship' WHEN regexp_matches(lt, 'contract|freelance') THEN 'contract' ELSE 'full_time' END END AS employment,
      department, team,
      salary_min, salary_max, salary_currency, salary_period, salary_summary,
      list_sort(list_distinct(list_concat(
        list_transform(list_filter(tokens, lambda x: {alias_map()}[x] IS NOT NULL), lambda x: {alias_map()}[x]),
        list_filter({ctx}, lambda x: x IS NOT NULL)))) AS skills,
      coalesce(experience::INT, try_cast(regexp_extract(lower(d), '(\\d{{1,2}})\\s*\\+?\\s*(?:-|–|to)?\\s*(?:\\d{{1,2}}\\s*\\+?\\s*)?(?:years|yrs)(?:\\s+of)?(?:\\s+[a-z/+&-]+){{0,4}}\\s+(?:experience|exp\\b)|(\\d{{1,2}})\\s*\\+?\\s*jahre\\s+(?:berufs)?erfahrung', 1) AS INT)) AS years_raw,
      CASE WHEN regexp_matches(dl, '(no|not|unable to|cannot|can''t|will not|won''t|do not|does not|is not able to)\\s+(currently\\s+)?(provide |offer |be able to |able to )?(visa |immigration )?sponsor')
                THEN false
           WHEN regexp_matches(dl, 'visa sponsorship (is )?(available|provided|offered)|(offer|provide|support|sponsor)s? (visa|work permit|h-?1b|immigration)|sponsorship (is )?(available|offered)|relocation (and|&) visa')
                THEN true END AS visa,
      coalesce(compensation_components ILIKE '%equity%', false) OR regexp_matches(dl, '\\b(equity|stock options|rsus?|esop|employee stock)\\b') AS equity,
      regexp_matches(dl, 'relocation (assistance|support|package|bonus|stipend)|(help|support) (you )?(with )?relocat') AS relocation,
      list_concat({lang_req('de', 'german|deutsch')}, {lang_req('fr', 'french|français')}, {lang_req('nl', 'dutch')},
                  {lang_req('es', 'spanish|español')}, {lang_req('pt', 'portuguese')}, {lang_req('it', 'italian')},
                  {lang_req('ja', 'japanese')}, {lang_req('zh', 'mandarin|chinese')}) AS lang_required,
      ['en', 'de', 'fr', 'es', 'nl', 'pt'][list_position(lc, list_max(lc))] AS lang,
      description
    FROM t3
    """)
    log(f"  enriched {con.execute('SELECT count(*) FROM enriched').fetchone()[0]:,} tech rows ({time.time()-t0:.0f}s)")

    con.execute(f"""
    CREATE OR REPLACE TABLE jobs_new AS
    WITH s AS (
      SELECT *,
        CASE WHEN salary_currency IS NULL OR coalesce(salary_min, salary_max) IS NULL THEN NULL
             ELSE {period}[coalesce(salary_period, 'YEAR')] * {fx}[salary_currency] END AS k
      FROM enriched
    ), s2 AS (
      SELECT *, round(coalesce(salary_min, salary_max) * k) AS smin, round(coalesce(salary_max, salary_min) * k) AS smax FROM s
    ), d AS (
      SELECT *, row_number() OVER (
        PARTITION BY lower(regexp_replace(company, '[^A-Za-z0-9]', '', 'g')), lower(regexp_replace(title, '[^A-Za-z0-9]', '', 'g')), coalesce(countries[1], '')
        ORDER BY coalesce({agg}[source], 0), posted DESC) AS dup
      FROM s2
    )
    SELECT id, source, company, title, role, seniority, posted, apply_url, url, location, countries, remote, remote_region,
      employment, department, team,
      CASE WHEN smin BETWEEN 8000 AND 1500000 THEN smin END AS salary_usd_min,
      CASE WHEN smax BETWEEN 8000 AND 1500000 THEN smax END AS salary_usd_max,
      salary_summary, salary_currency,
      skills, CASE WHEN years_raw BETWEEN 0 AND 20 THEN years_raw END AS years_min,
      visa, equity, relocation, lang, lang_required, description,
      title || ' | ' || coalesce(role, '') || ' | ' || seniority || ' | ' || array_to_string(skills, ', ') || ' | '
        || left(regexp_replace(coalesce(description, ''), '[#*_>`\\[\\]()]+|\\s+', ' ', 'g'), 1500) AS embed_text
    FROM d WHERE dup = 1
    QUALIFY row_number() OVER (PARTITION BY id ORDER BY posted DESC) = 1  -- some sources repeat an id per country
    """)
    con.execute("ALTER TABLE jobs_new ADD COLUMN content_hash VARCHAR")
    con.execute("UPDATE jobs_new SET content_hash = md5(embed_text)")
    n = con.execute("SELECT count(*) FROM jobs_new").fetchone()[0]
    log(f"  deduped -> {n:,} jobs ({time.time()-t0:.0f}s)")

    con.execute("BEGIN")
    con.execute("DROP TABLE IF EXISTS jobs")
    con.execute("ALTER TABLE jobs_new RENAME TO jobs")
    con.execute("COMMIT")
    # the fts index is bound to the table name, so build it after the swap
    con.execute("PRAGMA create_fts_index('jobs', 'id', 'title', 'company', 'description', stemmer = 'english', overwrite = 1)")
    log(f"  fts index ({time.time()-t0:.0f}s)")
    log(f"build done: {n:,} jobs in {time.time()-t0:.0f}s")
    return n


if __name__ == "__main__":
    build()
