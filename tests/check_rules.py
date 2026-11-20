"""Regression check for the local enrichment rules. Run: uv run python -m tests.check_rules"""
import re

import duckdb

from jobdeck import pipeline, taxonomy as T

ROLE_CASES = {
    "Community Impact Manager": None, "Mobile Phlebotomist (Bowling Green, KY)": None, "Flight Test Engineer": None,
    "Civil Design Engineer": None, "Development Director": None, "Clinical Data Manager": None,
    "Executive Assistant (CTO, CPO)": None, "Press Brake Machine Programmer": None,
    "Prozessplaner / Prozessentwickler Fertigungstechnik": None, "Corporate Physician - AI Research Participants": None,
    "Automotive Mobile Technician": None, "Account Executive, Geo Enterprise": None,
    "Founding Product Engineer": "software", "Collibra Data Lineage Engineer": "data_eng",
    "Director, Applied Science": "ml_ai", "Senior Product Analyst": "data_analytics", "Director of Global IT": "eng_mgmt",
    "Sr. iOS Engineer": "mobile", "Senior Software Engineer - Mobile (iOS)": "mobile", "Junior Gameplay Engineer": "gamedev",
    "Software Engineer, Ambient AI": "ml_ai", "Senior Mobile Flutter Developer": "mobile", "Manual QA Intern": "qa",
    "Senior Softwareentwickler Java (m/w/d)": "software", "Backend Engineer (Go)": "backend",
    "Staff Software Engineer": "software", "Engineering Manager, Payments": "eng_mgmt", "Product Designer": "design",
    "Mobile Engineer": "mobile", "Site Reliability Engineer": "devops",
}
SENIORITY_CASES = {"Staff Software Engineer": "staff", "Sr. Backend Engineer": "senior", "Software Engineering Intern": "intern",
                   "Engineering Manager, Payments": "manager", "Junior .NET Developer": "junior", "Backend Engineer": None,
                   "Principal Engineer": "principal", "VP of Engineering": "director"}
PLACE_CASES = {"Bengaluru, KA, IN": "IN", "Seattle, WA": "US", "Indianapolis, IN": "US", "Toronto, ON, CA": "CA",
               "SG": "SG", "London": "GB", "Santiago, Chile": "CL", "Remote": None, "Berlin, Germany": "DE"}


def first(pairs, s):
    return next((n for n, rx in pairs if re.search(rx, s)), None)


def role(t):
    t = t.lower()
    return None if re.search(T.NOT_TECH, t) else first(T.ROLES, t)


bad = [(t, role(t), w) for t, w in ROLE_CASES.items() if role(t) != w]
bad += [(t, first(T.SENIORITY, t.lower()), w) for t, w in SENIORITY_CASES.items() if first(T.SENIORITY, t.lower()) != w]

c = duckdb.connect()
for loc, want in PLACE_CASES.items():
    got = c.execute(f"""SELECT {pipeline.place_country()} FROM
        (SELECT list_transform(string_split(lower(?), ','), lambda x: trim(x)) AS lparts)""", [loc]).fetchone()[0]
    if got != want:
        bad.append((loc, got, want))

assert not bad, "\n".join(f"{t!r}: got {g!r}, want {w!r}" for t, g, w in bad)
print(f"ok: {len(ROLE_CASES)} roles, {len(SENIORITY_CASES)} levels, {len(PLACE_CASES)} places")
