"""
Tag papers with topics + a one-line TL;DR using Claude via the Message Batches API.

Only papers not already in data/research/topics.json are sent, so after the
first backfill each daily run costs a few cents. If the batch hasn't finished
within --wait-minutes, its id is saved and the next run picks the results up.

Usage: ANTHROPIC_API_KEY=... python3 scripts/classify_topics.py [--max 5000] [--wait-minutes 50]
"""
import argparse
import json
import os
import pathlib
import sys
import time
from datetime import datetime, timezone

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

REPO_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))
from topics import TOPICS  # noqa: E402

PAPERS_PATH  = REPO_ROOT / "data" / "papers.json"
RESEARCH_DIR = REPO_ROOT / "data" / "research"
TOPICS_PATH  = RESEARCH_DIR / "topics.json"
PENDING_PATH = RESEARCH_DIR / "pending_batch.json"

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5")
TOPIC_NAMES = list(TOPICS) + ["Other"]

SYSTEM = f"""You tag research papers for a dashboard about world models.

Pick the 1-3 topics from this list that best describe the paper's main contribution:
{chr(10).join("- " + t for t in TOPIC_NAMES)}

Use "Other" only when none of the listed topics fit. Also write a TL;DR: one plain
sentence (max 25 words) stating what the paper does and why it matters. No hype words."""

SCHEMA = {
    "type": "object",
    "properties": {
        "topics": {"type": "array", "items": {"type": "string", "enum": TOPIC_NAMES}},
        "tldr":   {"type": "string"},
    },
    "required": ["topics", "tldr"],
    "additionalProperties": False,
}


def load_json(path: pathlib.Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def save_json(path: pathlib.Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True) + "\n")


def build_request(custom_id: str, paper: dict) -> Request:
    prompt = f"Title: {paper.get('title', '')}\n\nAbstract: {paper.get('abstract', '')}"
    return Request(
        custom_id=custom_id,
        params=MessageCreateParamsNonStreaming(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": prompt}],
        ),
    )


def submit(client: anthropic.Anthropic, papers: list, known: dict, limit: int) -> dict | None:
    todo = [p for p in papers if p.get("paperId") and p["paperId"] not in known][:limit]
    if not todo:
        print("All papers already classified.")
        return None
    # custom_id must match [a-zA-Z0-9_-]{1,64}; arXiv ids contain '.' and '/'.
    id_map = {f"p{i}": p["paperId"] for i, p in enumerate(todo)}
    batch = client.messages.batches.create(
        requests=[build_request(cid, p) for cid, p in zip(id_map, todo)]
    )
    pending = {"batch_id": batch.id, "model": MODEL, "id_map": id_map}
    save_json(PENDING_PATH, pending)
    print(f"Submitted batch {batch.id} with {len(todo)} papers.")
    return pending


def collect(client: anthropic.Anthropic, pending: dict, store: dict) -> int:
    added = 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for result in client.messages.batches.results(pending["batch_id"]):
        paper_id = pending["id_map"].get(result.custom_id)
        if not paper_id:
            continue
        if result.result.type != "succeeded":
            print(f"  {paper_id}: {result.result.type}")
            continue
        msg = result.result.message
        if msg.stop_reason != "end_turn":
            print(f"  {paper_id}: stop_reason={msg.stop_reason}")
            continue
        text = next((b.text for b in msg.content if b.type == "text"), "")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            print(f"  {paper_id}: invalid JSON")
            continue
        topics = [t for t in parsed["topics"] if t in TOPIC_NAMES][:3] or ["Other"]
        store["papers"][paper_id] = {"topics": topics, "tldr": parsed["tldr"].strip()}
        added += 1
    store["model"] = pending["model"]
    store["updated_at"] = now
    return added


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=5000, help="max papers to submit in one batch")
    parser.add_argument("--wait-minutes", type=float, default=50)
    args = parser.parse_args()

    client = anthropic.Anthropic()
    papers = load_json(PAPERS_PATH, {"papers": []})["papers"]
    store = load_json(TOPICS_PATH, {"papers": {}})

    pending = load_json(PENDING_PATH, None) or submit(client, papers, store["papers"], args.max)
    if not pending:
        return

    deadline = time.monotonic() + args.wait_minutes * 60
    while True:
        batch = client.messages.batches.retrieve(pending["batch_id"])
        if batch.processing_status == "ended":
            break
        if time.monotonic() > deadline:
            print(f"Batch {batch.id} still {batch.processing_status}; will collect next run.")
            return
        time.sleep(60)

    added = collect(client, pending, store)
    save_json(TOPICS_PATH, store)
    PENDING_PATH.unlink()
    print(f"Classified {added} papers ({len(store['papers'])} total).")


if __name__ == "__main__":
    main()
