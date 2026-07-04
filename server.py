from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import json
from pathlib import Path

TOPICS = {
    "Robot Navigation":        ["navigation", "path planning", "mobile robot", "localization", "mapping", "slam"],
    "Autonomous Driving":      ["autonomous driving", "self-driving", "vehicle", "traffic", "waymo", "nuplan", "carla"],
    "Reinforcement Learning":  ["reinforcement learning", " rl ", "policy", "reward", "q-learning", "actor-critic", "ppo", "sac"],
    "Video Generation":        ["video generation", "video prediction", "future frame", "video diffusion", "video synthesis"],
    "3D Scene Modeling":       ["nerf", "3d scene", "scene reconstruction", "point cloud", "occupancy", "gaussian splatting"],
    "Physics & Dynamics":      ["physics", "dynamics", "rigid body", "fluid", "contact", "mujoco", "isaac"],
    "Planning & Control":      ["planning", "model predictive", "mpc", "tree search", "mcts", "decision making"],
    "Language & Vision":       ["vision-language", "vlm", "multimodal", "language model", "llm", "gpt", "clip"],
    "Situational Awareness":   ["situational awareness", "scene understanding", "anomaly", "uncertainty", "safety"],
    "Game Playing":            ["atari", "minecraft", "chess", "dota", "starcraft", "game environment"],
    "Robotics & Manipulation": ["manipulation", "grasping", "dexterous", "humanoid", "end-effector"],
    "Latent Space Models":     ["latent", "vae", "encoder", "representation learning", "dreamer", "rssm"],
}


def assign_topics(title: str, abstract: str):
    text = (title + " " + abstract).lower()
    matched = [t for t, kws in TOPICS.items() if any(k in text for k in kws)]
    return matched or ["Other"]


app = FastAPI()


@app.get("/api/papers")
def get_papers():
    data_path = Path("papers.json")
    if not data_path.exists():
        return JSONResponse({"papers": [], "total": 0, "last_updated": None})
    raw = json.loads(data_path.read_text())
    papers = raw.get("papers", [])
    enriched = []
    for p in papers:
        if not p.get("year"):
            continue
        enriched.append({
            "title":       p.get("title") or "",
            "abstract":    p.get("abstract") or "",
            "year":        p.get("year") or 0,
            "venue":       p.get("venue") or "",
            "authors":     p.get("authors") or "",
            "citations":   p.get("citationCount") or p.get("citations") or 0,
            "paper_url":   p.get("paper_url") or p.get("paperUrl") or "",
            "code_url":    p.get("code_url") or p.get("codeUrl") or "",
            "topics":      assign_topics(p.get("title", ""), p.get("abstract", "")),
        })
    return JSONResponse({
        "papers":       enriched,
        "total":        len(enriched),
        "last_updated": raw.get("last_updated"),
    })


_visit_count = 0

@app.get("/api/visit")
def record_visit():
    global _visit_count
    _visit_count += 1
    return JSONResponse({"visits": _visit_count})

@app.get("/api/stats")
def get_stats():
    return JSONResponse({"visits": _visit_count})

app.mount("/", StaticFiles(directory="static", html=True), name="static")
