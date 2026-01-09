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
# Session State Init
# ----------------------------
if "api_key" not in st.session_state:
    st.session_state.api_key = os.getenv("GOOGLE_API_KEY", "")

if "cx" not in st.session_state:
    st.session_state.cx = os.getenv("GOOGLE_CX", "")

if "show_creds_editor" not in st.session_state:
    st.session_state.show_creds_editor = False

if "serp_history" not in st.session_state:
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        st.session_state.serp_history = df
    else:
        st.session_state.serp_history = pd.DataFrame()

if "pull_count" not in st.session_state:
    st.session_state.pull_count = 0

if "query_index" not in st.session_state:
    st.session_state.query_index = 0

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
    rows = []
    for idx, item in enumerate(data.get("items", []), start=1):
        link = item.get("link", "")
        rows.append({
            "batch_id": batch_id,
            "timestamp": pd.Timestamp.utcnow(),
            "query": query,
            "gl": gl,
            "hl": hl,
            "rank": idx,
            "title": item.get("title"),
            "link": link,
            "domain": urlparse(link).netloc.replace("www.", ""),
            "snippet": item.get("snippet")
        })
    return rows

def save_history(df):
    df.to_csv(DATA_FILE, index=False)

# ============================================================
# 🔐 SIDEBAR — CREDENTIALS (TOP)
# ============================================================
st.sidebar.title("🔐 Credentials")

if st.sidebar.button("✏️ Change API Key / CX"):
    st.session_state.show_creds_editor = True

if st.session_state.show_creds_editor:
    with st.sidebar.expander("Update Credentials", expanded=True):
        new_api_key = st.text_input(
            "New Google API Key",
            type="password",
            placeholder="Enter new API key",
            value=""
        )

        new_cx = st.text_input(
            "New Custom Search Engine ID (CX)",
            placeholder="Enter new CX",
            value=""
        )

        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 Save"):
                if new_api_key:
                    st.session_state.api_key = new_api_key
                if new_cx:
                    st.session_state.cx = new_cx
                st.session_state.show_creds_editor = False
                st.success("✅ Credentials updated")
                st.rerun()

        with c2:
            if st.button("❌ Cancel"):
                st.session_state.show_creds_editor = False
                st.rerun()

st.sidebar.divider()

# ============================================================
# 🔎 SIDEBAR — SERP SETTINGS
# ============================================================
st.sidebar.title("🔎 Settings")

queries_text = st.sidebar.text_area(
    "Queries (one per line)",
    value=""
)
queries = [q.strip() for q in queries_text.splitlines() if q.strip()]

gl = st.sidebar.text_input("Region (gl)", value="us")
hl = st.sidebar.text_input("Language (hl)", value="en")

num = st.sidebar.slider("Results per pull", 1, 10, 10)
refresh = st.sidebar.slider("Refresh interval (seconds)", 3, 60, 10)
max_pulls = st.sidebar.number_input("Max pulls", 1, 500, 100)

start_stream = st.sidebar.toggle("▶ Start Live Tracking", value=False)
clear_btn = st.sidebar.button("🧹 Clear History")

# ----------------------------
# Clear history
# ----------------------------
if clear_btn:
    st.session_state.serp_history = pd.DataFrame()
    st.session_state.pull_count = 0
    st.session_state.query_index = 0
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)
    st.success("History cleared")
    st.stop()

# ----------------------------
# Header
# ----------------------------
st.title("📊 SERP Tracker + Visualizer")

df = st.session_state.serp_history
api_key = st.session_state.api_key
cx = st.session_state.cx

# ----------------------------
# Live Tracking
# ----------------------------
if start_stream:
    if not api_key or not cx:
        st.warning("⚠ Please set API Key and CX first")
        st.stop()

    if st.session_state.pull_count >= max_pulls:
        st.warning("🛑 Max pulls reached")
        st.stop()

    st_autorefresh(interval=refresh * 1000, key="serp_autorefresh")

    current_query = queries[st.session_state.query_index % len(queries)]
    st.session_state.query_index += 1

    batch_id = int(datetime.utcnow().timestamp())

    try:
        data = fetch_serp(api_key, cx, current_query, gl, hl, num)
        new_df = pd.DataFrame(parse_items(data, current_query, gl, hl, batch_id))
        st.session_state.serp_history = pd.concat([df, new_df], ignore_index=True)
        save_history(st.session_state.serp_history)
        st.session_state.pull_count += 1
        st.success(f"Pulled '{current_query}' | #{st.session_state.pull_count}")
    except Exception as e:
        st.error(e)

df = st.session_state.serp_history
if df.empty:
    st.info("No data yet")
    st.stop()

# ----------------------------
# Latest Snapshot
# ----------------------------
latest_batch = df["batch_id"].max()
latest = df[df["batch_id"] == latest_batch].sort_values("rank")

st.subheader("📌 Latest SERP Snapshot")
st.dataframe(latest[["rank", "title", "domain", "link"]], use_container_width=True)

# ----------------------------
# Export
# ----------------------------
st.subheader("💾 Export Dataset")
st.download_button(
    "Download CSV",
    df.to_csv(index=False).encode("utf-8"),
    "serp_history.csv",
    "text/csv"
)