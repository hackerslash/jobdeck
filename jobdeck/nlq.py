"""Plain-language query -> structured filters, with local rules only.

"backend engineer remote eligible from india 2-4 years exp"
  -> role=backend, remote=remote, eligible=IN, years_max=4, q=""
"""
import re

from . import taxonomy as T

LEVELS = [("intern", r"\binterns?(hip)?\b"), ("junior", r"\b(junior|jr|entry[- ]level|graduate|new grad)\b"),
          ("mid", r"\bmid([- ]level)?\b"), ("senior", r"\b(senior|sr)\b"), ("staff", r"\bstaff\b"),
          ("principal", r"\bprincipal\b"), ("lead", r"\b(tech )?lead\b"), ("manager", r"\b(engineering )?manager\b")]
EMPLOYMENT = [("internship", r"\binternships?\b"), ("contract", r"\b(contract|freelance|contractor)\b"), ("part_time", r"\bpart[- ]time\b")]
DAYS = [(1, r"\b(today|last 24 ?h(ours)?|past day)\b"), (7, r"\b(this|last|past) week\b"), (30, r"\b(this|last|past) month\b"),
        (3, r"\b(new|fresh|latest|recent)\b")]
TAGS = [("big-tech", r"\b(big[- ]tech|faang|maang)\b"), ("equity", r"\bequity\b"), ("relocation", r"\brelocat\w*\b")]
FILLER = set("""a an the and or with for in at on of to from based located eligible open jobs job role roles position positions opening
openings work working remote hybrid onsite exp experience years year yrs yoe looking want need find show me i any role as who
engineer engineers developer developers dev""".split())
REGION_OF = {**dict.fromkeys("US CA".split(), "americas"),
             **dict.fromkeys("MX BR AR CL CO PE UY CR".split(), "latam"),
             **dict.fromkeys("IN SG JP CN HK TW KR AU NZ PH VN ID MY TH PK".split(), "apac")}
# Safe in a short query, too ambiguous to match in job descriptions
QUERY_ALIASES = {"react": "React", "go": "Golang", "node": "Node.js", "ts": "TypeScript", "js": "JavaScript", "rust": "Rust",
                 "swift": "Swift", "c": "C", "r": "R", "spring": "Spring", "k8s": "Kubernetes", "postgres": "PostgreSQL"}
PLACE_KEYS = sorted((k for k in T.PLACES if len(k) >= 4 or k in {"usa", "uk", "uae", "nyc"}), key=len, reverse=True)


def region_of(cc: str) -> str:
    return REGION_OF.get(cc, "europe")  # remote_region 'europe' covers EMEA


def parse(q: str) -> dict:
    s = " " + q.lower().strip() + " "
    f: dict = {}
    said: list[str] = []

    def take(rx):  # consume the matched span so leftover words become the text query
        nonlocal s
        m = re.search(rx, s)
        if m:
            s = s[:m.start()] + " " + s[m.end():]
        return m

    m = take(r"\$?\s?(\d{2,3})\s?k\+?\b|\$\s?(\d{2,3}),000\+?")
    if m:
        f["salary_min"] = int(m.group(1) or m.group(2)) * 1000
        said.append(f"pay ≥ ${f['salary_min'] // 1000}k")
    m = take(r"(\d{1,2})\s*(?:-|–|to)\s*(\d{1,2})\s*\+?\s*(?:years?|yrs?|yoe)\b") or take(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?|yoe)\b()")
    if m:
        f["years_max"] = int(m.group(2) or m.group(1))
        said.append(f"asks ≤ {f['years_max']} yrs")
    if take(r"\b(visa|sponsor\w*)\b"):
        f["visa"] = True
        said.append("sponsors visa")
    for d, rx in DAYS:
        if take(rx):
            f["days"] = d
            said.append(f"posted ≤ {d}d")
            break
    remote = bool(take(r"\b(remote|wfh|work from home|distributed)\b"))
    if take(r"\bhybrid\b"):
        f["remote"] = ["hybrid"]
    elif take(r"\b(on-?site|in[- ]office)\b"):
        f["remote"] = ["onsite"]
    elif remote:
        f["remote"] = ["remote"]
    regions = [name for name, rx in (("global", r"\b(anywhere|worldwide|global(ly)?)\b"), ("europe", r"\b(europe|emea|eu)\b"),
                                     ("apac", r"\b(apac|asia)\b"), ("latam", r"\b(latam|latin america|south america)\b"),
                                     ("americas", r"\b(americas|north america)\b")) if take(rx)]
    if regions:
        f["region"] = regions
        if not f.get("remote"):
            f["remote"] = ["remote"]
        said.append("remote from " + ", ".join(regions))
    places = []
    for key in PLACE_KEYS:
        if re.search(rf"\b{re.escape(key)}\b", s):
            take(rf"\b{re.escape(key)}\b")
            if T.PLACES[key] not in places:
                places.append(T.PLACES[key])
    if places:
        if remote:  # "remote from india": remote roles open to that country
            f["eligible"] = places
            said.append("remote, open to " + ", ".join(places))
        else:
            f["country"] = places
            said.append("in " + ", ".join(places))
    elif remote:
        said.append("remote")
    for key, opts in (("employment", EMPLOYMENT), ("tag", TAGS)):
        hit = [v for v, rx in opts if take(rx)]
        if hit:
            f[key] = hit
            said += hit
    lv = [v for v, rx in LEVELS if take(rx)]
    if lv:
        f["seniority"] = lv
        said += lv
    # stack first: in a short query a named technology is the sharpest signal
    for rx, rep in T.PHRASES:
        s = re.sub(rx, rep, s)
    aliases = {a: canon for canon, (_, al) in T.SKILLS.items() for a in al.split()} | QUERY_ALIASES
    skills = []
    for w in re.findall(r"[a-z0-9#+]+(?:[._-][a-z0-9#+]+)*", s):
        if w in aliases and aliases[w] not in skills and w not in FILLER:
            skills.append(aliases[w])
            take(rf"(?<![\w#+.]){re.escape(w)}(?![\w#+])")
    if skills:
        f["skill"] = skills
        said.append("stack " + " + ".join(skills))
    # role (generic "software" only when written out)
    for name, rx in T.ROLES:
        if name == "software" and not re.search(r"software|swe\b", s):
            continue
        m = re.search(rx, s)
        if m:
            f["role"] = [name]
            said.append(f"role {name}")
            take(re.escape(m.group(0)))
            break
    rest = [w for w in re.findall(r"[\w#+.-]+", s) if w not in FILLER]
    f["q"] = " ".join(rest)
    return {"filters": f, "understood": said}


if __name__ == "__main__":
    for q, want in {
        "backend engineer remote eligible from india 2-4 years exp": {"role": ["backend"], "remote": ["remote"], "eligible": ["IN"], "years_max": 4, "q": ""},
        "senior rust jobs in berlin $150k": {"seniority": ["senior"], "skill": ["Rust"], "country": ["DE"], "salary_min": 150000, "q": ""},
        "ml engineer remote anywhere visa": {"role": ["ml_ai"], "remote": ["remote"], "region": ["global"], "visa": True, "q": ""},
        "react native contract this week": {"skill": ["React Native"], "employment": ["contract"], "days": 7, "q": ""},
        "payments stripe": {"q": "payments stripe"},
    }.items():
        got = parse(q)["filters"]
        assert all(got.get(k) == v for k, v in want.items()), (q, got)
    print("ok: nlq cases")
