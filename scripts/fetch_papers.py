"""
Fetches world models papers from Semantic Scholar and code links from Papers With Code.
Saves results to data/papers.json. Run daily via GitHub Actions.
"""
import requests
import json
import time
from pathlib import Path
from datetime import datetime

SS_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
PWC_SEARCH = "https://paperswithcode.com/api/v1/papers/"

FIELDS = (
    "paperId,title,abstract,year,venue,authors,"
    "externalIds,openAccessPdf,citationCount,publicationDate"
)

QUERIES = ["world model", "world models"]


def ss_fetch(query):
    papers = {}
    offset = 0
    while True:
        try:
            resp = requests.get(
                SS_SEARCH,
                params={"query": query, "fields": FIELDS, "limit": 100, "offset": offset},
                timeout=30,
            )
            if resp.status_code == 429:
                print("Rate limited — waiting 60s")
                time.sleep(60)
                continue
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"Error fetching offset {offset}: {e}")
            break

        batch = data.get("data", [])
        for p in batch:
            if p.get("paperId"):
                papers[p["paperId"]] = p

        total = data.get("total", 0)
        offset += len(batch)
        print(f"  {offset}/{total} fetched")

        if offset >= total or not batch:
            break
        time.sleep(1.5)

    return papers


def pwc_code_url(arxiv_id):
    try:
        resp = requests.get(PWC_SEARCH, params={"arxiv_id": arxiv_id}, timeout=10)
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                repos = results[0].get("repositories", [])
                if repos:
                    return repos[0].get("url")
    except Exception:
        pass
    return None


def paper_url(paper):
    ids = paper.get("externalIds") or {}
    if ids.get("ArXiv"):
        return f"https://arxiv.org/abs/{ids['ArXiv']}"
    if ids.get("DOI"):
        return f"https://doi.org/{ids['DOI']}"
    pdf = paper.get("openAccessPdf") or {}
    return pdf.get("url")


def main():
    data_path = Path(__file__).parent.parent / "data" / "papers.json"
    data_path.parent.mkdir(exist_ok=True)

    # Load existing cache
    all_papers = {}
    if data_path.exists():
        with open(data_path) as f:
            cached = json.load(f)
        for p in cached.get("papers", []):
            all_papers[p["paperId"]] = p
        print(f"Loaded {len(all_papers)} cached papers")

    # Fetch from Semantic Scholar
    for query in QUERIES:
        print(f"\nFetching: '{query}'")
        fetched = ss_fetch(query)
        new = {k: v for k, v in fetched.items() if k not in all_papers}
        print(f"  {len(new)} new papers")

        # Enrich new papers with code links + paper URL
        for i, (pid, p) in enumerate(new.items()):
            p["paperUrl"] = paper_url(p)
            arxiv_id = (p.get("externalIds") or {}).get("ArXiv")
            if arxiv_id:
                p["codeUrl"] = pwc_code_url(arxiv_id)
                time.sleep(0.5)
            else:
                p["codeUrl"] = None
            if (i + 1) % 20 == 0:
                print(f"  enriched {i+1}/{len(new)}")

        all_papers.update(new)

    # Save
    output = {
        "papers": list(all_papers.values()),
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "total": len(all_papers),
    }
    with open(data_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved {len(all_papers)} papers to {data_path}")


if __name__ == "__main__":
    main()
