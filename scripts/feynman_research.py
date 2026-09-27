"""
Run Feynman research workflows headless and store their reports for the dashboard.

  digest   weekly /lit review of the newest papers in the catalog
  compare  /compare of the most-cited papers in one topic (rotates weekly)
  recipe   /recipe for one world-model training goal (rotates weekly)
  audit    /audit paper-vs-code for the most-cited papers with code, N per run

Reports land in data/research/reports/ and are indexed in data/research/index.json.
Audits are also reduced to a match score in data/research/audits.json with a Claude
call, since Feynman's audit report is free-form markdown.

Requires `feynman` on PATH and ANTHROPIC_API_KEY.
Usage: python3 scripts/feynman_research.py {digest,compare,recipe,audit} [options]
"""
import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

import anthropic

REPO_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))
from topics import TOPICS, assign_topics  # noqa: E402

PAPERS_PATH  = REPO_ROOT / "data" / "papers.json"
RESEARCH_DIR = REPO_ROOT / "data" / "research"
REPORTS_DIR  = RESEARCH_DIR / "reports"
INDEX_PATH   = RESEARCH_DIR / "index.json"
AUDITS_PATH  = RESEARCH_DIR / "audits.json"
TOPICS_PATH  = RESEARCH_DIR / "topics.json"

CLAUDE_MODEL    = os.environ.get("CLAUDE_MODEL", "claude-opus-5")
RUN_TIMEOUT_SEC = int(os.environ.get("FEYNMAN_TIMEOUT_SEC", 45 * 60))

RECIPE_GOALS = [
    "train a latent world model (Dreamer-style RSSM) for sample-efficient RL on Atari or DMC",
    "train an action-conditioned video world model for robot manipulation",
    "train a world model for autonomous driving scene forecasting",
    "train a JEPA-style predictive world model from video without pixel reconstruction",
    "fine-tune a video diffusion model into an interactive, controllable game world model",
    "use a learned world model for model-predictive control of a real robot",
]


# ── helpers ──────────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: pathlib.Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def save_json(path: pathlib.Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True) + "\n")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def arxiv_id(paper: dict) -> str:
    return re.sub(r"v\d+$", "", paper["paperId"])


def load_papers() -> list:
    """Papers with their effective topics (LLM tags when present, keywords otherwise)."""
    papers = load_json(PAPERS_PATH, {"papers": []})["papers"]
    tagged = load_json(TOPICS_PATH, {"papers": {}})["papers"]
    for p in papers:
        tag = tagged.get(p.get("paperId"))
        p["topics"] = tag["topics"] if tag else assign_topics(p.get("title", ""), p.get("abstract", ""))
    return papers


def week_index() -> int:
    return datetime.now(timezone.utc).isocalendar().week


def run_feynman(prompt: str, suffix: str) -> str:
    """Run one Feynman workflow in a scratch dir and return the final report's markdown.

    `suffix` selects the deliverable in outputs/ (e.g. "-audit.md"); for /lit the
    deliverable is a bare "<slug>.md", so pass ".md" and intermediates are skipped.
    """
    with tempfile.TemporaryDirectory() as tmp:
        cmd = ["feynman", "--no-session", "--cwd", tmp, f"--prompt={prompt}"]
        env = {**os.environ, "FEYNMAN_TELEMETRY": "off"}
        print(f"$ feynman --prompt {prompt[:120]!r}...", flush=True)
        proc = subprocess.run(cmd, cwd=tmp, env=env, timeout=RUN_TIMEOUT_SEC,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True)
        print(proc.stdout[-3000:])
        if proc.returncode != 0:
            print(proc.stderr[-3000:], file=sys.stderr)
            raise RuntimeError(f"feynman exited with {proc.returncode}")

        outputs = pathlib.Path(tmp) / "outputs"
        candidates = [
            f for f in outputs.glob(f"*{suffix}")
            if not f.name.endswith(".provenance.md") and "-research-" not in f.name
        ] if outputs.is_dir() else []
        if not candidates:
            raise RuntimeError(f"feynman produced no outputs/*{suffix} report")
        return max(candidates, key=lambda f: f.stat().st_size).read_text()


def write_report(kind: str, slug: str, title: str, markdown: str, **meta) -> dict:
    rel = pathlib.Path(kind) / f"{slug}.md"
    (REPORTS_DIR / rel).parent.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / rel).write_text(markdown)
    entry = {"title": title, "path": f"reports/{rel.as_posix()}", "generated_at": now_iso(), **meta}

    index = load_json(INDEX_PATH, {})
    entries = [e for e in index.get(kind, []) if e["path"] != entry["path"]]
    index[kind] = sorted([entry, *entries], key=lambda e: e["generated_at"], reverse=True)
    save_json(INDEX_PATH, index)
    print(f"Saved {entry['path']}")
    return entry


# ── workflows ────────────────────────────────────────────────────────────────

def cmd_digest(args):
    papers = load_papers()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=args.days)).date().isoformat()
    recent = [p for p in papers if (p.get("pub_date") or "") >= cutoff]
    recent.sort(key=lambda p: p.get("citations") or 0, reverse=True)
    if not recent:
        print(f"No papers since {cutoff}; skipping digest.")
        return
    listing = "\n".join(f"- arxiv:{arxiv_id(p)} — {p['title']}" for p in recent[: args.max_papers])
    prompt = (
        f"/lit What is new in world models research in the last {args.days} days? "
        f"{len(recent)} new papers were published since {cutoff}; the most notable are:\n{listing}\n"
        "Summarize the main themes and standout results, how they relate to prior work "
        "(e.g. Ha & Schmidhuber, the Dreamer series, JEPA, video world models), and open questions."
    )
    md = run_feynman(prompt, ".md")
    week = datetime.now(timezone.utc).strftime("%G-W%V")
    write_report("digests", week, f"World models digest — week {week}", md, paper_count=len(recent))


def cmd_compare(args):
    topic = args.topic or list(TOPICS)[week_index() % len(TOPICS)]
    papers = [p for p in load_papers() if topic in p["topics"]]
    papers.sort(key=lambda p: p.get("citations") or 0, reverse=True)
    top = papers[: args.n]
    if len(top) < 2:
        print(f"Not enough papers in {topic!r} to compare.")
        return
    ids = " ".join(f"arxiv:{arxiv_id(p)}" for p in top)
    md = run_feynman(f"/compare {ids} — world-model papers on {topic}", "-comparison.md")
    write_report("comparisons", slugify(topic), f"{topic}: most-cited papers compared", md,
                 topic=topic, papers=[p["paperId"] for p in top])


def cmd_recipe(args):
    goal = args.goal or RECIPE_GOALS[week_index() % len(RECIPE_GOALS)]
    md = run_feynman(f"/recipe {goal}", "-recipe.md")
    write_report("recipes", slugify(goal), goal[0].upper() + goal[1:], md, goal=goal)


AUDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "match_pct": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        "verdict":   {"type": "string", "enum": ["consistent", "minor issues", "major issues", "inconclusive"]},
        "summary":   {"type": "string"},
    },
    "required": ["match_pct", "verdict", "summary"],
    "additionalProperties": False,
}


def summarize_audit(client: anthropic.Anthropic, report: str) -> dict:
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": AUDIT_SCHEMA}},
        messages=[{"role": "user", "content": (
            "Below is an audit comparing a paper's claims with its public code. Extract: "
            "match_pct (share of checked claims the code supports, 0-100, or null if the report "
            "gives no basis for a number), an overall verdict, and a one-sentence summary of the "
            "most important finding.\n\n" + report
        )}],
    )
    if response.stop_reason != "end_turn":
        raise RuntimeError(f"audit summary stop_reason={response.stop_reason}")
    return json.loads(next(b.text for b in response.content if b.type == "text"))


def cmd_audit(args):
    audits = load_json(AUDITS_PATH, {})
    todo = [p for p in load_papers() if p.get("code_url") and p["paperId"] not in audits]
    todo.sort(key=lambda p: p.get("citations") or 0, reverse=True)
    client = anthropic.Anthropic()
    failures = 0
    for p in todo[: args.limit]:
        try:
            md = run_feynman(f"/audit {p['code_url']} --paper arxiv:{arxiv_id(p)}", "-audit.md")
            entry = write_report("audits", slugify(p["paperId"]), p["title"], md, paper_id=p["paperId"])
            audits[p["paperId"]] = {**summarize_audit(client, md), "path": entry["path"],
                                    "generated_at": entry["generated_at"]}
            save_json(AUDITS_PATH, audits)
        except (RuntimeError, subprocess.TimeoutExpired, anthropic.APIError) as e:
            failures += 1
            print(f"Audit failed for {p['paperId']}: {e}", file=sys.stderr)
    if failures and failures == min(args.limit, len(todo)):
        sys.exit(1)


def main():
    if not shutil.which("feynman"):
        sys.exit("feynman not found on PATH — npm install -g @companion-ai/feynman")

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("digest");  p.add_argument("--days", type=int, default=7)
    p.add_argument("--max-papers", type=int, default=25)
    p = sub.add_parser("compare"); p.add_argument("--topic", choices=list(TOPICS))
    p.add_argument("--n", type=int, default=5)
    p = sub.add_parser("recipe");  p.add_argument("--goal")
    p = sub.add_parser("audit");   p.add_argument("--limit", type=int, default=2)

    args = parser.parse_args()
    {"digest": cmd_digest, "compare": cmd_compare, "recipe": cmd_recipe, "audit": cmd_audit}[args.cmd](args)


if __name__ == "__main__":
    main()
