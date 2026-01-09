import streamlit as st
import requests
import pandas as pd
import os
from urllib.parse import urlparse
import plotly.express as px
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

# ----------------------------
# Setup
# ----------------------------
load_dotenv()
st.set_page_config(page_title="SERP Tracker", layout="wide")

DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "serp_history.csv")
os.makedirs(DATA_DIR, exist_ok=True)

# ----------------------------
# Google Custom Search Fetch
# ----------------------------
def fetch_serp(api_key, cx, query, gl="us", hl="en", num=10, start=1):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "gl": gl,
        "hl": hl,
        "num": num,
        "start": start,
        "safe": "off",
        "googlehost": "google.com"
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def parse_items(data, query, gl, hl, batch_id):
    items = data.get("items", [])
    rows = []
    for idx, item in enumerate(items, start=1):
        link = item.get("link", "")
        domain = urlparse(link).netloc.replace("www.", "")
        rows.append({
            "batch_id": batch_id,
            "timestamp": pd.Timestamp.utcnow(),
            "query": query,
            "gl": gl,
            "hl": hl,
            "rank": idx,
            "title": item.get("title"),
            "link": link,
            "domain": domain,
            "snippet": item.get("snippet")
        })
    return rows

# ----------------------------
# Load / Save Helpers
# ----------------------------
def load_history():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        return df
    return pd.DataFrame()

def save_history(df):
    df.to_csv(DATA_FILE, index=False)

# ----------------------------
# Sidebar Inputs
# ----------------------------
st.sidebar.title("🔎 SERP Tracking Settings")

api_key = st.sidebar.text_input("Google API Key", type="password", value=os.getenv("GOOGLE_API_KEY", ""))
cx = st.sidebar.text_input("Custom Search Engine ID (CX)", value=os.getenv("GOOGLE_CX", ""))

queries_text = st.sidebar.text_area(
    "Queries (one per line)",
    value="best trekking shoes\nbest hiking boots"
)
queries = [q.strip() for q in queries_text.splitlines() if q.strip()]

gl = st.sidebar.text_input("Region (gl)", value="us")
hl = st.sidebar.text_input("Language (hl)", value="en")

num = st.sidebar.slider("Results per pull (max 10)", 1, 10, 10)
refresh = st.sidebar.slider("Refresh interval (seconds)", 3, 60, 10)
max_pulls = st.sidebar.number_input("Max pulls (quota safety)", 1, 500, 100)

start_stream = st.sidebar.toggle("▶ Start Live Tracking", value=False)
clear_btn = st.sidebar.button("🧹 Clear History")

# ----------------------------
# App State
# ----------------------------
if "serp_history" not in st.session_state:
    st.session_state.serp_history = load_history()

if "pull_count" not in st.session_state:
    st.session_state.pull_count = 0

if "query_index" not in st.session_state:
    st.session_state.query_index = 0

# Clear history
if clear_btn:
    st.session_state.serp_history = pd.DataFrame()
    st.session_state.pull_count = 0
    st.session_state.query_index = 0
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)
    st.success("✅ History cleared.")
    st.stop()

# ----------------------------
# Header
# ----------------------------
st.title("📊 SERP Tracker + Visualizer")
st.caption("Programmable Search API → Snapshot collection → Data science analysis → Plotly visualization (Streamlit)")

df = st.session_state.serp_history

# ----------------------------
# Live Tracking using Auto Refresh
# ----------------------------
if start_stream:
    if not api_key or not cx:
        st.warning("⚠ Please enter API Key + CX to start.")
        st.stop()

    if st.session_state.pull_count >= max_pulls:
        st.warning("🛑 Max pulls reached — stopped to protect quota.")
        st.stop()

    # Auto refresh
    st_autorefresh(interval=refresh * 1000, key="serp_autorefresh")

    # Rotate queries (batch pull)
    current_query = queries[st.session_state.query_index % len(queries)] if queries else "test query"
    st.session_state.query_index += 1

    batch_id = int(datetime.utcnow().timestamp())

    try:
        data = fetch_serp(api_key, cx, current_query, gl=gl, hl=hl, num=num, start=1)
        new_rows = parse_items(data, current_query, gl, hl, batch_id)
        new_df = pd.DataFrame(new_rows)

        st.session_state.serp_history = pd.concat([df, new_df], ignore_index=True)
        save_history(st.session_state.serp_history)

        st.session_state.pull_count += 1

        st.success(f"✅ Pulled {len(new_df)} results for '{current_query}' | Pull #{st.session_state.pull_count}")

    except Exception as e:
        st.error(f"❌ API Error: {e}")

df = st.session_state.serp_history

# ----------------------------
# Stop if empty
# ----------------------------
if df.empty:
    st.info("No SERP data yet. Enable ▶ Start Live Tracking from sidebar.")
    st.stop()

# ----------------------------
# Latest Snapshot + Metrics
# ----------------------------
latest_batch = df["batch_id"].max()
latest = df[df["batch_id"] == latest_batch].sort_values("rank")

batches = sorted(df["batch_id"].unique())
has_prev = len(batches) > 1
prev_batch = batches[-2] if has_prev else None

# Rank delta calculation
if has_prev:
    prev = df[df["batch_id"] == prev_batch][["link", "rank"]].set_index("link")["rank"].to_dict()
    latest["prev_rank"] = latest["link"].map(prev)
    latest["delta"] = latest["prev_rank"] - latest["rank"]
else:
    latest["prev_rank"] = None
    latest["delta"] = None

# Volatility score
volatility = latest["delta"].abs().mean() if has_prev else None

# Stability score (% urls retained)
if has_prev:
    prev_links = set(df[df["batch_id"] == prev_batch]["link"])
    latest_links = set(latest["link"])
    stability = len(prev_links.intersection(latest_links)) / max(len(prev_links), 1)
else:
    stability = None

# New/Dropped URLs
if has_prev:
    new_urls = latest_links - prev_links
    dropped_urls = prev_links - latest_links
else:
    new_urls = set()
    dropped_urls = set()

# ----------------------------
# Top Metrics Row
# ----------------------------
m1, m2, m3, m4 = st.columns(4)

m1.metric("Total rows collected", f"{len(df)}")
m2.metric("Total snapshots", f"{df['batch_id'].nunique()}")
m3.metric("Volatility (avg |Δrank|)", f"{volatility:.2f}" if volatility is not None else "N/A")
m4.metric("Stability (% URLs retained)", f"{stability*100:.0f}%" if stability is not None else "N/A")

# ----------------------------
# Layout: Latest Snapshot + Domain Bar
# ----------------------------
col1, col2 = st.columns([1.4, 1])

with col1:
    st.subheader("📌 Latest SERP Snapshot")
    st.dataframe(
        latest[["rank", "prev_rank", "delta", "title", "domain", "link"]],
        use_container_width=True
    )

with col2:
    st.subheader("🏷 Domain Distribution (Latest)")
    dom_counts = latest["domain"].value_counts().reset_index()
    dom_counts.columns = ["domain", "count"]
    fig_bar = px.bar(dom_counts, x="domain", y="count")
    st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# ----------------------------
# Winners / Losers
# ----------------------------
st.subheader("🚀 Winners & Losers (Rank Movers)")

if has_prev:
    movers = latest.dropna(subset=["delta"]).sort_values("delta", ascending=False)
    winners = movers.head(5)[["rank", "prev_rank", "delta", "domain", "title"]]
    losers = movers.tail(5)[["rank", "prev_rank", "delta", "domain", "title"]]

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### ✅ Winners (Moved Up)")
        st.dataframe(winners, use_container_width=True)
    with c2:
        st.markdown("### ❌ Losers (Moved Down)")
        st.dataframe(losers, use_container_width=True)
else:
    st.info("Need at least 2 snapshots to calculate rank movers.")

st.divider()

# ----------------------------
# New Entrants / Dropped URLs
# ----------------------------
st.subheader("🆕 New Entrants & ❌ Dropped URLs")

if has_prev:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🆕 New URLs in Latest Snapshot")
        st.write(list(new_urls)[:10] if new_urls else "None")

    with c2:
        st.markdown("### ❌ Dropped URLs (Were in Prev Snapshot)")
        st.write(list(dropped_urls)[:10] if dropped_urls else "None")
else:
    st.info("Need at least 2 snapshots to compute new/dropped URLs.")

st.divider()

# ----------------------------
# Rank Movement Over Time
# ----------------------------
st.subheader("📈 Rank Movement Over Time (Top URLs)")

top_urls = df.groupby("link")["rank"].min().sort_values().head(10).index.tolist()
movement = df[df["link"].isin(top_urls)].copy()

fig_line = px.line(
    movement,
    x="timestamp",
    y="rank",
    color="domain",
    line_group="link",
    hover_data=["title", "link", "query"],
    markers=True
)
fig_line.update_yaxes(autorange="reversed")
st.plotly_chart(fig_line, use_container_width=True)

st.divider()

# ----------------------------
# Domain Presence Heatmap
# ----------------------------
st.subheader("🔥 Domain Presence Heatmap (Across Snapshots)")

heat = df.groupby(["batch_id", "domain"]).size().reset_index(name="count")
heat_pivot = heat.pivot(index="domain", columns="batch_id", values="count").fillna(0)

if heat_pivot.shape[1] > 1:
    fig_heat = px.imshow(heat_pivot, aspect="auto")
    st.plotly_chart(fig_heat, use_container_width=True)
else:
    st.info("Need more snapshots to show heatmap.")

st.divider()

# ----------------------------
# Export
# ----------------------------
st.subheader("💾 Export Dataset")

st.write(f"✅ Persistent file saved automatically at: `{DATA_FILE}`")

csv_bytes = df.to_csv(index=False).encode("utf-8")
st.download_button("Download SERP history as CSV", csv_bytes, "serp_history.csv", "text/csv")