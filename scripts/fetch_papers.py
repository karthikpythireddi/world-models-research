"""
Fetches world models papers from arXiv API.
Enriches with venue + citations via OpenAlex; extracts code links (github/gitlab/
bitbucket) from the paper abstract/comment. Saves to data/papers.json.
Saves to data/papers.json. Run daily via GitHub Actions.
"""
import json
import re
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

ARXIV_API   = "http://export.arxiv.org/api/query"
OPENALEX    = "https://api.openalex.org/works"
OA_EMAIL    = "karthik9@stanford.edu"   # polite pool → higher limits

NS = {
    "atom":       "http://www.w3.org/2005/Atom",
    "arxiv":      "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}

QUERIES = [
    'ti:"world model"',
    'ti:"world models"',
    'abs:"world model" AND ti:robot',
]

# Normalize verbose conference names to short forms
_CONF_RE = [
    (r"(?i)advances in neural information processing systems",  "NeurIPS"),
    (r"(?i)neural information processing systems",             "NeurIPS"),
    (r"(?i)international conference on learning representations","ICLR"),
    (r"(?i)international conference on machine learning",       "ICML"),
    (r"(?i)computer vision and pattern recognition",            "CVPR"),
    (r"(?i)european conference on computer vision",             "ECCV"),
    (r"(?i)international conference on computer vision",        "ICCV"),
    (r"(?i)robotics[: ]+science and systems",                  "RSS"),
    (r"(?i)international conference on robotics and automation","ICRA"),
    (r"(?i)conference on robot learning",                       "CoRL"),
    (r"(?i)association for the advancement of artificial intelligence", "AAAI"),
    (r"(?i)international joint conference on artificial intelligence",  "IJCAI"),
    (r"(?i)empirical methods in natural language processing",   "EMNLP"),
    (r"(?i)annual meeting of the association for computational linguistics", "ACL"),
    (r"(?i)transactions on (?:pattern analysis and machine intelligence|pami)", "TPAMI"),
    (r"(?i)\bproceedings of (?:the )?", ""),
    (r"(?i)\bworkshop\b.*",             ""),   # strip workshop suffixes
    (r"\s{2,}",                         " "),
]

# Patterns to find venue from the arXiv comment field
_COMMENT_VENUE = [
    r"(?i)accepted (?:at|to|in|by) ([A-Z][A-Za-z\s&]+\d{4})",
    r"(?i)(?:published|to appear|appearing) (?:at|in) ([A-Z][A-Za-z\s&]+\d{4})",
    r"(?i)\b((?:NeurIPS|ICML|ICLR|CVPR|ECCV|ICCV|ICRA|CoRL|RSS|AAAI|IJCAI|EMNLP|ACL|ICLR)\s*(?:20\d{2})?)\b",
]


# Repo/code URL extraction from free text (abstract or arXiv comment).
# Trailing punctuation (". ; ,") is stripped; ".git" suffix is kept.
_CODE_RE = re.compile(
    r"https?://(?:www\.)?(?:github\.com|gitlab\.com|bitbucket\.org)/[\w.\-]+/[\w.\-]+",
    re.I,
)


def extract_code_url(*texts: str) -> str:
    """Return the first github/gitlab/bitbucket repo URL found in the given texts, else ''."""
    for t in texts:
        if not t:
            continue
        m = _CODE_RE.search(t)
        if m:
            return m.group(0).rstrip(".,;)")
    return ""


def clean_venue(raw: str) -> str:
    if not raw:
        return ""
    s = raw.strip()
    for pattern, repl in _CONF_RE:
        s = re.sub(pattern, repl, s)
    return s.strip(" ,;:").rstrip(".")


def extract_venue_from_comment(comment: str) -> str:
    """Try to pull a conference name from an arXiv comment string."""
    if not comment:
        return ""
    for pat in _COMMENT_VENUE:
        m = re.search(pat, comment)
        if m:
            return clean_venue(m.group(1))
    return ""


def arxiv_fetch(query: str, batch: int = 100) -> dict:
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
        try:
            with urllib.request.urlopen(f"{ARXIV_API}?{params}", timeout=30) as r:
                xml = r.read()
        except Exception as e:
            print(f"  arXiv error at start={start}: {e}")
            break

        root    = ET.fromstring(xml)
        total   = int(root.findtext("opensearch:totalResults", "0", NS))
        entries = root.findall("atom:entry", NS)
        if not entries:
            break

        for entry in entries:
            raw_id   = entry.findtext("atom:id", namespaces=NS) or ""
            arxiv_id = raw_id.split("/abs/")[-1]
            title    = (entry.findtext("atom:title",   namespaces=NS) or "").strip().replace("\n", " ")
            abstract = (entry.findtext("atom:summary", namespaces=NS) or "").strip().replace("\n", " ")
            comment  = (entry.findtext("arxiv:comment",namespaces=NS) or "").strip()
            published = entry.findtext("atom:published", namespaces=NS) or ""
            year      = int(published[:4]) if published else 0
            authors   = [a.findtext("atom:name", namespaces=NS) or ""
                         for a in entry.findall("atom:author", NS)]
            author_str = ", ".join(authors[:3]) + (f" +{len(authors)-3}" if len(authors) > 3 else "")
            venue_from_comment = extract_venue_from_comment(comment)

            papers[arxiv_id] = {
                "paperId":   arxiv_id,
                "title":     title,
                "abstract":  abstract,
                "year":      year,
                "pub_date":  published,
                "authors":   author_str,
                "paper_url": f"https://arxiv.org/abs/{arxiv_id}",
                "venue":     venue_from_comment,  # from comment; S2 may upgrade this
                "citations": 0,
                # Extract repo link from abstract/comment; None if none found (OpenAlex won't add one)
                "code_url":  extract_code_url(abstract, comment) or None,
            }

        start += len(entries)
        print(f"  {start}/{total} fetched")
        if start >= total:
            break
        time.sleep(3)

    return papers


def openalex_enrich(papers: dict, max_lookups: int = 1641) -> dict:
    """Enrich with citation counts + venue via OpenAlex (free, no auth, 100k/day).
    Queries one paper at a time via the direct works/arxiv:{id} endpoint — simple and reliable.
    At 10 req/s polite limit: 1641 papers ≈ 3 minutes.
    """
    to_enrich = [k for k, v in papers.items() if v.get("code_url") is None]
    print(f"  {len(to_enrich)} papers queued for OpenAlex enrichment")
    done = 0
    for arxiv_id in to_enrich[:max_lookups]:
        # Strip version suffix (e.g. 2301.04104v2 → 2301.04104)
        clean_id = arxiv_id.split("v")[0]
        url = f"{OPENALEX}/arxiv:{clean_id}?select=cited_by_count,primary_location,ids&mailto={OA_EMAIL}"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": f"world-models-dashboard/1.0 (mailto:{OA_EMAIL})"}
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                item = json.loads(r.read())

            papers[arxiv_id]["citations"] = item.get("cited_by_count") or 0

            if not papers[arxiv_id].get("venue"):
                loc    = item.get("primary_location") or {}
                source = loc.get("source") or {}
                raw_v  = source.get("display_name") or ""
                if raw_v and "arxiv" not in raw_v.lower():
                    papers[arxiv_id]["venue"] = clean_venue(raw_v)

            papers[arxiv_id]["code_url"] = ""  # mark as checked

        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"  OpenAlex rate-limited at {done}, stopping for today — rest on next run")
                break   # save progress and exit cleanly; GitHub Actions runs daily
            papers[arxiv_id]["code_url"] = ""  # 404 or other — not in OA
        except Exception:
            papers[arxiv_id]["code_url"] = ""

        done += 1
        if done % 200 == 0:
            print(f"  Enriched {done}/{len(to_enrich)}…")
            # Save progress so a crash or rate-limit doesn't lose everything
            save(papers, Path(__file__).parent.parent / "data" / "papers.json")
        time.sleep(0.35)  # ~3 req/s — conservative to avoid rate limits

    return papers


def save(papers: dict, path: Path):
    out = {
        "papers":       list(papers.values()),
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "total":        len(papers),
    }
    path.write_text(json.dumps(out, indent=2))
    print(f"  Saved {len(papers)} papers → {path}")


def main():
    data_path = Path(__file__).parent.parent / "data" / "papers.json"
    data_path.parent.mkdir(exist_ok=True)

    # Load cache
    all_papers: dict = {}
    if data_path.exists():
        cached = json.loads(data_path.read_text())
        for p in cached.get("papers", []):
            all_papers[p["paperId"]] = p
        print(f"Loaded {len(all_papers)} cached papers")

    # Reset broken "" code_url entries (from old failed PWC enrichment) → None so S2 retries them
    reset = sum(1 for p in all_papers.values() if p.get("code_url") == "")
    for p in all_papers.values():
        if p.get("code_url") == "":
            p["code_url"] = None
    if reset:
        print(f"Reset {reset} stale entries → None for S2 re-enrichment")

    # Backfill code_url on cached papers from their stored abstract (no API needed)
    backfilled = 0
    for p in all_papers.values():
        if not p.get("code_url"):
            url = extract_code_url(p.get("abstract", ""))
            if url:
                p["code_url"] = url
                backfilled += 1
    if backfilled:
        print(f"Backfilled {backfilled} code links from cached abstracts")

    # Fetch new papers from arXiv (also extracts venue from comment field)
    for q in QUERIES:
        print(f"\nFetching: {q}")
        fetched = arxiv_fetch(q)
        new = {k: v for k, v in fetched.items() if k not in all_papers}
        # For existing papers: upgrade venue from comment if we didn't have one
        for k, v in fetched.items():
            if k in all_papers and not all_papers[k].get("venue") and v.get("venue"):
                all_papers[k]["venue"] = v["venue"]
        print(f"  +{len(new)} new")
        all_papers.update(new)
        save(all_papers, data_path)

    # Enrich with OpenAlex (citations + venue) — no auth, 100k req/day
    print(f"\nEnriching with OpenAlex…")
    all_papers = openalex_enrich(all_papers, max_lookups=1641)
    save(all_papers, data_path)

    print(f"\nDone. {len(all_papers)} papers total.")


if __name__ == "__main__":
    main()
