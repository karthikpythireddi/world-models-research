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
        rows.append({
            "title":        p.get("title") or "",
            "abstract":     p.get("abstract") or "",
            "year":         p.get("year") or 0,
            "venue":        p.get("venue") or "Unknown",
            "authors":      author_str,
            "citations":    p.get("citationCount") or 0,
            "paper_url":    p.get("paperUrl") or "",
            "code_url":     p.get("codeUrl") or "",
            "pub_date":     p.get("publicationDate") or "",
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
    st.warning("No data yet — run `python scripts/fetch_papers.py` to populate.")
    st.stop()

# ── Sidebar filters ───────────────────────────────────────────────────────────

st.sidebar.header("Filters")

current_year = datetime.now(timezone.utc).year
min_year = int(df["year"].min())

year_range = st.sidebar.slider(
    "Year range",
    min_value=min_year,
    max_value=current_year,
    value=(current_year - 2, current_year),
)

venues = sorted(df["venue"].dropna().unique().tolist())
selected_venues = st.sidebar.multiselect("Conference / Venue", venues)

search = st.sidebar.text_input("Search title or abstract", "")

sort_by = st.sidebar.selectbox("Sort by", ["Year (newest)", "Citations (most)"])

show_no_code = st.sidebar.checkbox("Only papers with code", value=False)

# ── Apply filters ─────────────────────────────────────────────────────────────

filtered = df[
    (df["year"] >= year_range[0]) &
    (df["year"] <= year_range[1])
].copy()

if selected_venues:
    filtered = filtered[filtered["venue"].isin(selected_venues)]

if search:
    mask = (
        filtered["title"].str.contains(search, case=False, na=False) |
        filtered["abstract"].str.contains(search, case=False, na=False)
    )
    filtered = filtered[mask]

if show_no_code:
    filtered = filtered[filtered["code_url"] != ""]

if sort_by == "Year (newest)":
    filtered = filtered.sort_values("year", ascending=False)
else:
    filtered = filtered.sort_values("citations", ascending=False)

# ── Stats row ─────────────────────────────────────────────────────────────────

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total papers (all time)", len(df))
col2.metric("Shown (filtered)", len(filtered))
col3.metric("With code", int((df["code_url"] != "").sum()))
col4.metric("Year range", f"{min_year} – {current_year}")

st.divider()

# ── Paper cards ───────────────────────────────────────────────────────────────

if filtered.empty:
    st.info("No papers match your filters.")
else:
    for _, row in filtered.iterrows():
        with st.container(border=True):
            title_line = f"### {row['title']}"
            st.markdown(title_line)

            meta_parts = []
            if row["year"]:
                meta_parts.append(f"📅 **{int(row['year'])}**")
            if row["venue"] and row["venue"] != "Unknown":
                meta_parts.append(f"🎓 {row['venue']}")
            if row["authors"]:
                meta_parts.append(f"👤 {row['authors']}")
            if row["citations"]:
                meta_parts.append(f"🔖 {int(row['citations'])} citations")
            st.markdown("  ·  ".join(meta_parts))

            link_parts = []
            if row["paper_url"]:
                link_parts.append(f"[📄 Paper]({row['paper_url']})")
            if row["code_url"]:
                link_parts.append(f"[💻 Code]({row['code_url']})")
            if link_parts:
                st.markdown("  |  ".join(link_parts))

            if row["abstract"]:
                with st.expander("Abstract"):
                    st.write(row["abstract"])
