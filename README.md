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

Topics are assigned at request time in [`server.py`](server.py) by keyword-matching
the title + abstract against a curated map (`TOPICS`). A paper can belong to multiple
topics; anything unmatched falls back to `Other`. This keeps classification
transparent and easy to tweak — no model, no training, just editable keyword lists.

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

## Run locally

```bash
pip install -r requirements.txt

python scripts/fetch_papers.py      # harvest arXiv + OpenAlex → data/papers.json
cp data/papers.json .               # server reads ./papers.json from the cwd

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

## Project layout

```
.
├── server.py                     # FastAPI backend + topic classifier
├── Dockerfile                    # HF Spaces container (uvicorn on :7860)
├── requirements.txt
├── static/                       # frontend (index.html, app.js, style.css)
├── data/
│   └── papers.json               # generated catalog (arXiv + OpenAlex)
├── scripts/
│   ├── fetch_papers.py           # arXiv/OpenAlex ingestion pipeline
│   └── deploy_to_hf.py           # packages + pushes the app to the Space
└── .github/workflows/
    └── daily_fetch.yml           # daily fetch + redeploy cron
```

## Stack

FastAPI · vanilla JS · Docker · Hugging Face Spaces · GitHub Actions · arXiv API · OpenAlex
