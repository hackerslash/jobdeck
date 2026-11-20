# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

SvelteKit (static adapter) + Tailwind, served by a FastAPI backend over a local DuckDB database. Runs locally on the owner's Mac first.

## Users

Primary: the owner, a developer hunting for roles, using it as a personal power tool. Later: other developers. Optimize for speed and density over onboarding.

## Product Purpose

jobdeck is a job search portal for developers built on the Stapply open job snapshot (daily parquet). It ingests ~44 developer-relevant sources, keeps only tech roles posted in the last 180 days, enriches every job locally (role family, seniority, skills, years of experience, USD-normalized salary, remote scope, countries, visa/equity/relocation, posting language, required languages), and lets the user triage hundreds of fresh roles fast.

Success: open it, filter hard, and find the handful of roles worth applying to in minutes.

## Positioning

Developer-centric and local-first: every attribute is computed locally from transparent rules the user can edit (tags are SQL expressions in rules.toml), and every job is pre-embedded so a resume matcher can rank against the whole corpus instantly.

## Operating Context

- Daily background sync from storage.stapply.ai; only changed source files are re-downloaded (sha256), then the DB is rebuilt and new jobs embedded.
- Used on a desktop browser, keyboard-first. Applying happens on the employer's own page (apply_url).

## Capabilities and Constraints

- MVP: dense list, filters (role, seniority, remote/region, country, skills, tags, salary floor, recency, years of experience, visa, source, language), sorting (newest, salary, company, relevance), job detail with full description, similar jobs via embeddings.
- Not in MVP (planned): BYOK AI adapter (OpenRouter / OpenAI / Anthropic key) that parses an uploaded resume and ranks jobs with a match percentage. The data is prepared for it (embeddings, skills, seniority, years).
- Data is a daily snapshot; it can be up to ~1 day stale.

## Evidence on Hand

Real data only: ~150k enriched jobs from the Stapply snapshot. No users, testimonials or metrics exist; do not fabricate any.

## Product Principles

1. Triage speed first: density, keyboard, instant filters.
2. Transparent and local: rules and attributes are inspectable and editable, nothing is a black box.
3. Fresh or gone: stale and old postings never reach the list.
4. Prepare for matching: every job carries the structured attributes and vectors ranking will need.
