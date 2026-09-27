from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import json
from pathlib import Path

from topics import assign_topics

RESEARCH_DIR = Path("research")


def load_research(name: str, default):
    path = RESEARCH_DIR / name
    return json.loads(path.read_text()) if path.exists() else default


app = FastAPI()


@app.get("/api/papers")
def get_papers():
    data_path = Path("papers.json")
    if not data_path.exists():
        return JSONResponse({"papers": [], "total": 0, "last_updated": None})
    raw = json.loads(data_path.read_text())
    papers = raw.get("papers", [])
    tagged = load_research("topics.json", {"papers": {}})["papers"]
    audits = load_research("audits.json", {})
    enriched = []
    for p in papers:
        if not p.get("year"):
            continue
        tag = tagged.get(p.get("paperId"), {})
        enriched.append({
            "paper_id":    p.get("paperId") or "",
            "title":       p.get("title") or "",
            "abstract":    p.get("abstract") or "",
            "year":        p.get("year") or 0,
            "venue":       p.get("venue") or "",
            "authors":     p.get("authors") or "",
            "citations":   p.get("citationCount") or p.get("citations") or 0,
            "paper_url":   p.get("paper_url") or p.get("paperUrl") or "",
            "code_url":    p.get("code_url") or p.get("codeUrl") or "",
            "topics":      tag.get("topics") or assign_topics(p.get("title", ""), p.get("abstract", "")),
            "tldr":        tag.get("tldr") or "",
            "audit":       audits.get(p.get("paperId")),
        })
    return JSONResponse({
        "papers":       enriched,
        "total":        len(enriched),
        "last_updated": raw.get("last_updated"),
    })


@app.get("/api/research")
def get_research():
    return JSONResponse(load_research("index.json", {}))


_visit_count = 0

@app.get("/api/visit")
def record_visit():
    global _visit_count
    _visit_count += 1
    return JSONResponse({"visits": _visit_count})

@app.get("/api/stats")
def get_stats():
    return JSONResponse({"visits": _visit_count})

RESEARCH_DIR.joinpath("reports").mkdir(parents=True, exist_ok=True)
app.mount("/research", StaticFiles(directory=RESEARCH_DIR), name="research")
app.mount("/", StaticFiles(directory="static", html=True), name="static")
