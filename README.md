# 📊 SERP Live Tracker + Analyzer (Streamlit)

This is a Streamlit-based SERP tracking dashboard that pulls Google search results using the **Google Programmable Search (Custom Search JSON API)**, stores snapshots over time, and visualizes ranking changes, volatility, and domain trends.

---

## Features

- Live SERP tracking with auto-refresh polling.
- Rotates through multiple queries (one per refresh).
- Fetches top results using Google Custom Search JSON API.
- Saves SERP snapshots to a persistent CSV file (`data/serp_history.csv`).
- Snapshot comparison metrics:
  - Rank delta (Δrank) per URL
  - Volatility score (avg |Δrank|)
  - Stability score (% URLs retained)
  - New entrants & dropped URLs
- Visualizations with Plotly:
  - Domain distribution bar chart (latest snapshot)
  - Rank movement over time (top URLs)
  - Domain presence heatmap (across snapshots)
- Export SERP history as CSV from the UI.

---

## Setup Instructions

1. Clone the repo:

   ```bash
   git clone https://github.com/rajeshtudu/SERP-Live-Analyzer.git
   cd SERP-Live-Analyzer
