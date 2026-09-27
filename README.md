# World Models Research

A self-updating research dashboard for the **world models** literature. It indexes
~1,600 papers from arXiv, enriches them with citations and venues, auto-classifies
them into 12 topics, and **redeploys itself every morning** — so the catalog is
never stale and there's no manual upkeep.

🔗 **Live app:** https://huggingface.co/spaces/karthikpythireddi93/world-models-papers

Built because doing a literature review on world models — starting from
Ha & Schmidhuber and working through the Dreamer series — meant chasing papers
scattered across arXiv with no easy way to see the whole landscape. This is the
tool that map should have been.

---

## Contents

- [Features](#features)
- [Architecture](#architecture)
- [The data pipeline](#the-data-pipeline)
- [Topic classification](#topic-classification)
- [The web app](#the-web-app)
- [Daily automation](#daily-automation)
- [Research layer](#research-layer)
- [Run locally](#run-locally)
- [Deploy your own](#deploy-your-own)
- [Project layout](#project-layout)
- [Stack](#stack)

---

## Features

- **~1,600 papers** harvested from the arXiv API across multiple world-model queries.
- **Citation counts & venues** enriched via [OpenAlex](https://openalex.org) (with
  verbose conference names normalized to short forms — NeurIPS, ICLR, CoRL, RSS, …).
- **12 topic filters** assigned automatically from title + abstract keywords:
  Robot Navigation · Autonomous Driving · Reinforcement Learning · Video Generation ·
  3D Scene Modeling · Physics & Dynamics · Planning & Control · Language & Vision ·
  Situational Awareness · Game Playing · Robotics & Manipulation · Latent Space Models.
- **Full-text search** across titles, authors, and abstracts.
- **Filters & sorting** — year range, sort by newest/oldest/most-cited.
- **"Only papers with code"** toggle — GitHub/GitLab/Bitbucket links are
  auto-extracted from abstracts and arXiv comments.
- **Self-updating** — a daily GitHub Actions job refetches and redeploys the entire
  app with zero manual steps.
- **Research layer (Claude + [Feynman](https://github.com/companion-inc/feynman))** —
  Claude topic tags and one-line TL;DRs for every paper, paper-vs-code audits shown as
  badges on paper cards, and weekly digests, topic comparisons and training recipes, each
  in its own dashboard tab.

## Architecture

```
        ┌────────────┐        ┌──────────────┐
        │   arXiv    │        │   OpenAlex   │
        │    API     │        │  (citations) │
        └─────┬──────┘        └──────┬───────┘
              │                      │
              ▼                      ▼
        ┌──────────────────────────────────┐
        │     scripts/fetch_papers.py      │
        │  query • enrich • extract code   │
        └────────────────┬─────────────────┘
                         ▼
                 data/papers.json
                         │
   GitHub Actions        │        (daily cron, 09:00 UTC)
   daily_fetch.yml ──────┤
                         ▼
        ┌──────────────────────────────────┐
        │     scripts/deploy_to_hf.py      │
        │  package server + static + data  │
        └────────────────┬─────────────────┘
                         ▼
        ┌──────────────────────────────────┐
        │        Hugging Face Space        │
        │   Docker · FastAPI · static UI   │
        │   GET /api/papers  →  frontend   │
        └──────────────────────────────────┘
```

## The data pipeline

[`scripts/fetch_papers.py`](scripts/fetch_papers.py) is the ingestion step:

1. **Query arXiv** — paginated searches over the arXiv Atom API, e.g.
   `ti:"world model"`, `ti:"world models"`, `abs:"world model" AND ti:robot`.
2. **Enrich via OpenAlex** — looks up each paper to attach citation counts and the
   publication venue. The `OA_EMAIL` "polite pool" address earns higher rate limits.
3. **Normalize venues** — regex rules collapse long conference names into short
   forms (e.g. *Advances in Neural Information Processing Systems* → *NeurIPS*) and
   strip workshop/proceedings suffixes.
4. **Extract code links** — scans abstracts and arXiv comment fields for
   GitHub/GitLab/Bitbucket URLs.
5. **Write** the merged, de-duplicated result to
   [`data/papers.json`](data/papers.json).

## Topic classification

Topics come from Claude (see [Research layer](#research-layer)), limited to a fixed list
of 12 topic names in [`topics.py`](topics.py). Papers Claude hasn't tagged yet fall back to
keyword-matching the title and abstract against the same list (`TOPICS`). A paper can have
several topics; anything unmatched is `Other`.

## The web app

- [`server.py`](server.py) — a small **FastAPI** backend.
  - `GET /api/papers` — returns enriched, topic-tagged papers plus totals and the
    last-updated timestamp.
  - `GET /api/visit` / `GET /api/stats` — a lightweight visit counter.
  - Mounts [`static/`](static/) as the SPA frontend.
- [`static/`](static/) — the dashboard UI, **vanilla JS with no build step**:
  `index.html`, `app.js`, `style.css`. Sidebar filters (year range, topics, sort,
  code-only), a search bar, and a responsive card grid with live stat chips.
- [`Dockerfile`](Dockerfile) — Python 3.11 slim image running
  `uvicorn server:app` on port 7860 (the Hugging Face Spaces convention).

## Daily automation

[`.github/workflows/daily_fetch.yml`](.github/workflows/daily_fetch.yml) runs every
day at **09:00 UTC** (and on manual `workflow_dispatch`):

1. Runs `fetch_papers.py` to rebuild `data/papers.json`.
2. Commits the refreshed data back to the repo.
3. Runs `deploy_to_hf.py` to push the full app (server + static + data) to the
   Hugging Face Space, using the `HF_TOKEN` repository secret.

The result: the live dashboard reflects the latest arXiv papers every morning,
untouched by hand.

## Research layer

A second workflow, [`.github/workflows/feynman_research.yml`](.github/workflows/feynman_research.yml),
runs after each successful daily fetch and writes everything to [`data/research/`](data/research/):

| When | What | How |
| --- | --- | --- |
| Daily | Topic tags + TL;DR for new papers | [`scripts/classify_topics.py`](scripts/classify_topics.py): Claude via the Message Batches API, structured output restricted to the 12 topics |
| Daily | Paper-vs-code audits (`AUDITS_PER_RUN`, default 2, most-cited first) | `feynman_research.py audit`, then a Claude call reduces each report to a match score for the card badge |
| Monday | Weekly digest of new papers | `feynman_research.py digest` (Feynman `/lit`) |
| Wednesday | Most-cited papers in one topic, compared (rotates weekly) | `feynman_research.py compare` (Feynman `/compare`) |
| Friday | One world-model training recipe (rotates weekly) | `feynman_research.py recipe` (Feynman `/recipe`) |

Each task is isolated: a failure shows in the run log but doesn't block the others or
the deploy. Any task can be run on demand from the Actions tab (`workflow_dispatch`).
Papers without Claude tags fall back to the keyword classifier in [`topics.py`](topics.py).

Settings (repo **Secrets** / **Variables**):

- `ANTHROPIC_API_KEY` (secret, required) — used by both Claude and Feynman.
- `OPENALEX_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY` (secrets, optional) — Feynman's literature
  search uses its own rate limits with these.
- `FEYNMAN_MODEL` (variable, optional) — e.g. `anthropic/claude-sonnet-5`; by default Feynman
  picks the newest Claude Opus available to the key.
- `AUDITS_PER_RUN` (variable, optional) — audits per day.

## Run locally

```bash
pip install -r requirements.txt

python scripts/fetch_papers.py      # harvest arXiv + OpenAlex → data/papers.json
cp data/papers.json .               # server reads ./papers.json from the cwd
ln -s data/research research        # …and ./research for tags, audits and reports

uvicorn server:app --reload         # → http://localhost:8000
```

## Deploy your own

1. Create a Docker Space on Hugging Face and set `REPO_ID` in
   [`scripts/deploy_to_hf.py`](scripts/deploy_to_hf.py) to `your-username/your-space`.
2. Push once manually to seed it:

   ```bash
   python scripts/deploy_to_hf.py --token hf_xxx
   ```
3. Add your Hugging Face write token as an `HF_TOKEN` GitHub Actions secret so the
   daily workflow can redeploy automatically.
4. Optional: add `ANTHROPIC_API_KEY` to turn on the [research layer](#research-layer).

## Project layout

```
.
├── server.py                     # FastAPI backend
├── topics.py                     # topic taxonomy + keyword fallback classifier
├── Dockerfile                    # HF Spaces container (uvicorn on :7860)
├── requirements.txt
├── static/                       # frontend (index.html, app.js, style.css)
├── data/
│   ├── papers.json               # generated catalog (arXiv + OpenAlex)
│   └── research/                 # Claude tags, audits, Feynman reports
├── scripts/
│   ├── fetch_papers.py           # arXiv/OpenAlex ingestion pipeline
│   ├── classify_topics.py        # Claude topic tags + TL;DRs (Batches API)
│   ├── feynman_research.py       # Feynman digest / compare / recipe / audit
│   └── deploy_to_hf.py           # packages + pushes the app to the Space
└── .github/workflows/
    ├── daily_fetch.yml           # daily fetch + redeploy cron
    └── feynman_research.yml      # research layer, runs after each fetch
```

## Stack

FastAPI · vanilla JS · Docker · Hugging Face Spaces · GitHub Actions · arXiv API · OpenAlex ·
Claude API · Feynman
