"""
Fetches world models papers from arXiv API + Papers With Code for code/venue.
Saves results to data/papers.json. Run daily via GitHub Actions.
"""
import json
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

ARXIV_API  = "http://export.arxiv.org/api/query"
PWC_API    = "https://paperswithcode.com/api/v1/papers/"
NS         = {"atom": "http://www.w3.org/2005/Atom",
               "arxiv": "http://arxiv.org/schemas/atom"}

QUERIES    = [
    'ti:"world model"',
    'ti:"world models"',
    'abs:"world model" AND ti:robot',
]


def arxiv_fetch(query, batch=100):
    papers = {}
    start  = 0
    while True:
        params = urllib.parse.urlencode({
            "search_query": query,
            "start":        start,
            "max_results":  batch,
            "sortBy":       "submittedDate",
            "sortOrder":    "descending",
        })
        url = f"{ARXIV_API}?{params}"
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                xml = r.read()
        except Exception as e:
            print(f"  Error at start={start}: {e}")
            break

        root  = ET.fromstring(xml)
        total = int(root.findtext("opensearch:totalResults",
                                  default="0",
                                  namespaces={"opensearch": "http://a9.com/-/spec/opensearch/1.1/"}))
        entries = root.findall("atom:entry", NS)
        if not entries:
            break

        for entry in entries:
            arxiv_id = entry.findtext("atom:id", namespaces=NS).split("/abs/")[-1]
            title    = (entry.findtext("atom:title", namespaces=NS) or "").strip().replace("\n", " ")
            abstract = (entry.findtext("atom:summary", namespaces=NS) or "").strip().replace("\n", " ")
            published= entry.findtext("atom:published", namespaces=NS)
            year     = int(published[:4]) if published else 0
            authors  = [a.findtext("atom:name", namespaces=NS)
                        for a in entry.findall("atom:author", NS)]
            author_str = ", ".join(authors[:3]) + (f" +{len(authors)-3}" if len(authors) > 3 else "")

            papers[arxiv_id] = {
                "paperId":   arxiv_id,
                "title":     title,
                "abstract":  abstract,
                "year":      year,
                "pub_date":  published,
                "authors":   author_str,
                "paper_url": f"https://arxiv.org/abs/{arxiv_id}",
                "venue":     "",
                "citations": 0,
                "code_url":  None,
            }

        start += len(entries)
        print(f"  {start}/{total} fetched")
        if start >= total:
            break
        time.sleep(3)  # arXiv asks for 3s between requests

    return papers


def pwc_enrich(papers, max_lookups=300):
    """Fetch venue (conference) and code URL from Papers With Code."""
    done = 0
    for arxiv_id, p in papers.items():
        if p.get("code_url") is not None:
            continue
        try:
            url = f"{PWC_API}?arxiv_id={urllib.parse.quote(arxiv_id)}"
            with urllib.request.urlopen(url, timeout=10) as r:
                data = json.loads(r.read())
            results = data.get("results", [])
            if results:
                hit   = results[0]
                repos = hit.get("repositories", [])
                p["code_url"] = repos[0]["url"] if repos else ""
                if not p["venue"] and hit.get("proceedings"):
                    p["venue"] = hit["proceedings"]
        except Exception:
            pass
        p["code_url"] = p.get("code_url") or ""
        done += 1
        time.sleep(0.4)
        if done >= max_lookups:
            print(f"  Enriched {done} papers (cap reached, rest on next run)")
            break
    return papers


def save(papers, path):
    out = {
        "papers":       list(papers.values()),
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "total":        len(papers),
    }
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"  Saved {len(papers)} papers → {path}")


def main():
    data_path = Path(__file__).parent.parent / "data" / "papers.json"
    data_path.parent.mkdir(exist_ok=True)

    # Load cache
    all_papers = {}
    if data_path.exists():
        cached = json.loads(data_path.read_text())
        for p in cached.get("papers", []):
            all_papers[p["paperId"]] = p
        print(f"Loaded {len(all_papers)} cached papers")

    # Fetch from arXiv
    for q in QUERIES:
        print(f"\nFetching: {q}")
        new = {k: v for k, v in arxiv_fetch(q).items() if k not in all_papers}
        print(f"  +{len(new)} new")
        all_papers.update(new)
        save(all_papers, data_path)   # save after each query

    # Enrich with PWC (code links + venue)
    print(f"\nEnriching with Papers With Code (up to 300)...")
    all_papers = pwc_enrich(all_papers, max_lookups=300)
    save(all_papers, data_path)

    print(f"\nDone. {len(all_papers)} papers total.")


if __name__ == "__main__":
    main()
