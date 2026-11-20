# jobdeck

A local-first, keyboard-driven job search for developers. It pulls the free daily [Stapply](https://data.stapply.ai) job snapshot, keeps the tech roles posted in the last 180 days (about 150k), enriches each one locally, and ranks them against your resumes. No accounts or API keys; your data stays on your machine.

## Features

- **Fast triage:** dense list, faceted filters with live counts, `j`/`k` navigation, sorting by newest, pay, relevance or match.
- **Plain-language search:** `remote backend from india 2-4 years` becomes role, remote, eligibility and experience filters. Tokens such as `skill:Rust region:europe` work too.
- **Local enrichment:** role family, seniority, skills, years required, pay normalised to USD per year, remote scope, countries, visa and equity signals, posting language, and cross-source dedup.
- **Resume match:** upload one or more resume versions (PDF, DOCX or TXT). Every job shows its best match % and which version produced it, plus matched and missing skills.
- **Similar jobs** using local embeddings (bge-small, running on Apple MPS or the CPU).
- **Tags as SQL:** define your own tags in `rules.toml` as DuckDB expressions. Changes apply live.
- **Auto-update:** a background job checks the snapshot hourly and re-downloads only the sources that changed.

## Quick start

Requires [uv](https://docs.astral.sh/uv/), Node 20+ and [pnpm](https://pnpm.io).

```sh
git clone https://github.com/hackerslash/jobdeck && cd jobdeck
cd web && pnpm install && pnpm build && cd ..
uv run python -m jobdeck serve      # http://localhost:8700
```

The first run downloads about 2 GB of parquet, then builds and embeds the index. This takes about 15 minutes on an M-series Mac. The page fills in on its own when it's done.

## Commands

```sh
uv run python -m jobdeck sync               # download changed sources
uv run python -m jobdeck build              # rebuild the enriched jobs table
uv run python -m jobdeck embed              # embed new or changed jobs
uv run python -m jobdeck update [--force]   # all three; this is what the background job runs
uv run python -m tests.check_rules          # regression check for the classifier rules
cd web && pnpm dev                          # UI dev server, proxies /api to :8700
```

## Configuration

- `config.toml`: sources, `max_age_days`, sync interval, embedding model, and `role_filter` (`tech` or `all`).
- `rules.toml`: your tags, written as SQL over job columns.

## How matching works

Match % is computed per job, per resume version:

| Component | Weight | How it's measured |
|---|---|---|
| Meaning | 45% | Cosine similarity of the resume and job embeddings, calibrated per resume against all jobs |
| Stack coverage | 30% | Smoothed share of the job's skills that appear in the resume |
| Level and years | 15% | Seniority distance, plus years of experience against the years the job asks for |
| Role family | 10% | Same role, or a related one |

Each job shows the best score across your resume versions.

## Stack

FastAPI · DuckDB (full-text search, vectors) · sentence-transformers · SvelteKit + Tailwind

## Privacy

The server binds to `127.0.0.1`. If you expose it through a Cloudflare tunnel, resume and sync endpoints refuse tunnelled requests (detected by the `cf-connecting-ip` header). Other reverse proxies are not detected, so don't expose the server through them.

Job data comes from the [Stapply ats-scrapers](https://github.com/kalil0321/ats-scrapers) snapshot.
