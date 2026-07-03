import json
from pathlib import Path
from datetime import datetime, timezone

import streamlit as st
import pandas as pd

DATA_PATH = Path(__file__).parent.parent / "data" / "papers.json"

st.set_page_config(
    page_title="World Models Papers",
    page_icon="🌍",
    layout="wide",
)

# ── Topic taxonomy (keyword-based) ────────────────────────────────────────────

TOPICS = {
    "Robot Navigation":       ["navigation", "path planning", "mobile robot", "localization", "mapping", "slam"],
    "Autonomous Driving":     ["autonomous driving", "self-driving", "vehicle", "traffic", "waymo", "nuplan", "carla"],
    "Reinforcement Learning": ["reinforcement learning", " rl ", "policy", "reward", "agent", "q-learning", "actor-critic", "ppo", "sac"],
    "Video Generation":       ["video generation", "video prediction", "future frame", "video diffusion", "video synthesis"],
    "3D Scene Modeling":      ["nerf", "3d", "scene reconstruction", "point cloud", "occupancy", "gaussian splatting", "spatial"],
    "Physics & Dynamics":     ["physics", "dynamics", "simulation", "rigid body", "fluid", "contact", "mujoco", "isaac"],
    "Planning & Control":     ["planning", "model predictive", "mpc", "tree search", "mcts", "decision making", "control"],
    "Language & Vision":      ["vision-language", "vlm", "multimodal", "language model", "llm", "gpt", "clip", "vqa"],
    "Situational Awareness":  ["situational awareness", "scene understanding", "anomaly", "out-of-distribution", "uncertainty", "safety"],
    "Game Playing":           ["atari", "game", "minecraft", "chess", "go ", "dota", "starcraft", "game environment"],
    "Robotics & Manipulation":["robot", "manipulation", "grasping", "dexterous", "humanoid", "arm", "end-effector"],
    "Latent Space Models":    ["latent", "vae", "encoder", "representation learning", "embedding", "dreamer", "rssm"],
}


def assign_topics(title: str, abstract: str) -> list:
    text = (title + " " + abstract).lower()
    return [topic for topic, kws in TOPICS.items() if any(kw in text for kw in kws)] or ["Other"]


# ── Load data ─────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_papers():
    if not DATA_PATH.exists():
        return pd.DataFrame(), None
    with open(DATA_PATH) as f:
        raw = json.load(f)
    papers = raw.get("papers", [])
    last_updated = raw.get("last_updated")
    rows = []
    for p in papers:
        authors = p.get("authors") or ""
        if isinstance(authors, list):
            author_str = ", ".join(a.get("name", "") for a in authors[:3])
            if len(authors) > 3:
                author_str += f" +{len(authors)-3}"
        else:
            author_str = authors

        title    = p.get("title") or ""
        abstract = p.get("abstract") or ""

        rows.append({
            "title":      title,
            "abstract":   abstract,
            "year":       p.get("year") or 0,
            "venue":      p.get("venue") or "",
            "authors":    author_str,
            "citations":  p.get("citationCount") or 0,
            "paper_url":  p.get("paper_url") or p.get("paperUrl") or "",
            "code_url":   p.get("code_url") or p.get("codeUrl") or "",
            "topics":     assign_topics(title, abstract),
        })

    df = pd.DataFrame(rows)
    df = df[df["year"] > 0].copy()
    return df, last_updated


df, last_updated = load_papers()

# ── Header ────────────────────────────────────────────────────────────────────

st.title("🌍 World Models Papers")
if last_updated:
    st.caption(f"Last updated: {last_updated} · Refreshes daily at 09:00 UTC")

if df is None or df.empty:
    st.warning("No data yet — run `python3 scripts/fetch_papers.py` to populate.")
    st.stop()

# ── Sidebar filters ───────────────────────────────────────────────────────────

st.sidebar.header("Filters")

current_year = datetime.now(timezone.utc).year
min_year     = int(df["year"].min())

year_range = st.sidebar.slider(
    "Year range",
    min_value=min_year,
    max_value=current_year,
    value=(current_year - 2, current_year),
)

selected_topics = st.sidebar.multiselect(
    "Topic",
    options=sorted(TOPICS.keys()) + ["Other"],
)

venues = sorted(v for v in df["venue"].dropna().unique() if v)
selected_venues = st.sidebar.multiselect("Conference / Venue", venues)

search = st.sidebar.text_input("Search title or abstract", "")

sort_by = st.sidebar.selectbox("Sort by", ["Year (newest)", "Citations (most)"])

show_code_only = st.sidebar.checkbox("Only papers with code", value=False)

# ── Apply filters ─────────────────────────────────────────────────────────────

filtered = df[
    (df["year"] >= year_range[0]) &
    (df["year"] <= year_range[1])
].copy()

if selected_topics:
    filtered = filtered[
        filtered["topics"].apply(lambda t: any(topic in t for topic in selected_topics))
    ]

if selected_venues:
    filtered = filtered[filtered["venue"].isin(selected_venues)]

if search:
    mask = (
        filtered["title"].str.contains(search, case=False, na=False) |
        filtered["abstract"].str.contains(search, case=False, na=False)
    )
    filtered = filtered[mask]

if show_code_only:
    filtered = filtered[filtered["code_url"].str.strip() != ""]

if sort_by == "Year (newest)":
    filtered = filtered.sort_values("year", ascending=False)
else:
    filtered = filtered.sort_values("citations", ascending=False)

# ── Stats row ─────────────────────────────────────────────────────────────────

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total papers (all time)", len(df))
col2.metric("Shown (filtered)", len(filtered))
col3.metric("With code", int((df["code_url"].str.strip() != "").sum()))
col4.metric("Year range", f"{min_year} – {current_year}")

st.divider()

# ── Paper cards ───────────────────────────────────────────────────────────────

if filtered.empty:
    st.info("No papers match your filters.")
else:
    for _, row in filtered.iterrows():
        with st.container(border=True):
            st.markdown(f"### {row['title']}")

            # Topic badges
            badges = "  ".join(f"`{t}`" for t in row["topics"] if t != "Other")
            if badges:
                st.markdown(badges)

            # Meta line
            meta = []
            if row["year"]:
                meta.append(f"📅 **{int(row['year'])}**")
            if row["venue"]:
                meta.append(f"🎓 {row['venue']}")
            if row["authors"]:
                meta.append(f"👤 {row['authors']}")
            if row["citations"]:
                meta.append(f"🔖 {int(row['citations'])} citations")
            if meta:
                st.markdown("  ·  ".join(meta))

            # Links as buttons
            btn_cols = st.columns([1, 1, 8])
            if row["paper_url"]:
                btn_cols[0].link_button("📄 Paper", row["paper_url"], use_container_width=True)
            if row["code_url"] and row["code_url"].strip():
                btn_cols[1].link_button("💻 Code", row["code_url"], use_container_width=True)

            if row["abstract"]:
                with st.expander("Abstract"):
                    st.write(row["abstract"])
