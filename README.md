Here’s a clean, ready-to-paste README.md for spinout-fair-ride (no “Project Nautilus” anywhere):

# Spinout Fair Ride — Automated Daily Planner

**Automated planner that generates daily sailing recommendations for Spinout Fair Ride.**  
A Python script runs via GitHub Actions to produce a public **`plan.json`** with route suggestions, recommended launch windows, and difficulty/effort ratings.

- **Outputs:** `plan.json` (Today) + optional 5-day outlook
- **Audience:** Guides/instructors, members, and guests
- **Scope:** Daylight-only, safety-first recommendations for SF Bay routes

---

## Features

- **Deterministic daily plan** – Computes *when* to go, not just *whether*, aligning launch/return with daylight and tide slack where possible.
- **Leg-aware currents** – Projects current vectors onto each route leg to estimate aiding/opposing flow and cross-current demand.
- **Skill profiles** – Casual / Intermediate / Expert thresholds tune wind, gust, and adverse-current tolerances.
- **Explainable by design** – Green/Yellow/Red badges with reasons, stations used, and clear fallbacks when data is partial.
- **Zero-ops publishing** – GitHub Actions fetches data → runs the model → validates output → commits/updates `plan.json`.

> **Important:** This is decision support for trained operators, not a navigation product. Always verify on-site conditions.

---

## How it works

1. **Data ingestion**: NOAA CO-OPS (tides/currents with `interval=hilo`), NDBC or Open-Meteo/OpenWeather (wind), sunrise/sunset.
2. **Computation**: daylight bounds, tide events, per-leg current vectors, exposure checks, skill-aware thresholds, safe windows.
3. **Validation**: sanity checks (non-empty windows *or* explicit holds, value bounds, JSON schema).
4. **Publish**: commit/update `plan.json` for the website/app to consume.

---

## Repository layout (suggested)

spinout-fair-ride/
├─ src/
│  ├─ plan_generator.py
│  ├─ rules.py                 # thresholds & safety rules (reads from config)
│  ├─ data_clients/            # NOAA, NDBC, Open-Meteo/OpenWeather
│  └─ utils/
├─ config/
│  ├─ thresholds.yml           # skill profiles & exposure limits
│  ├─ stations.yml             # tide/current/wind stations per route leg
│  └─ app.yml                  # provider toggles, caching, timezone
├─ tests/
│  └─ test_output.py           # basic JSON/schema guardrails
├─ .github/workflows/
│  └─ publish.yml              # scheduled Action to build & publish plan.json
├─ plan.json                   # generated (ignored locally)
├─ requirements.txt
├─ .env.example
└─ README.md

---

## Quick start (local)

**Requires:** Python 3.11+

```bash
git clone https://github.com/<org>/spinout-fair-ride.git
cd spinout-fair-ride
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add keys if using OpenWeather; Open-Meteo requires none
python -m src.plan_generator --date today --skill intermediate --out plan.json

Common .env keys:

# If using OpenWeather:
OPENWEATHERMAP_API_KEY=...


⸻

Configuration

config/stations.yml (example)

leg_station_mapping:
  p40-p39:
    tide: "9414290"     # San Francisco, CA
    current: "SFB1201"  # SF Bay, Bay Bridge
    wind: "sfdc1"       # NDBC station
  p40-clipper:
    tide: "9414290"
    current: "SFB1201"
    wind: "sfdc1"
  p40-tiburon:
    tide: "9414290"
    current: "SFB1201"
    wind: "sfdc1"
  p40-cavallo:
    tide: "9414290"
    current: "SFB1201"
    wind: "sfdc1"

config/thresholds.yml (example)

profiles:
  casual:
    max_wind_mph: 12
    max_gust_mph: 16
    max_adverse_current_kts: 0.6
  intermediate:
    max_wind_mph: 16
    max_gust_mph: 22
    max_adverse_current_kts: 1.0
  expert:
    max_wind_mph: 22
    max_gust_mph: 30
    max_adverse_current_kts: 1.5

exposure_zones:
  crissy_slot_wnw: caution
  raccoon_strait_flood: caution


⸻

GitHub Actions (publish)

.github/workflows/publish.yml

name: Publish plan.json

on:
  schedule:
    # ~05:00 PT daily (adjust as needed)
    - cron: "0 13 * * *"
  workflow_dispatch:

jobs:
  build-plan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt

      - name: Generate plan.json
        run: |
          python -m src.plan_generator --date today --skill intermediate --out plan.json

      - name: Validate JSON
        run: |
          python - <<'PY'
          import json
          with open('plan.json') as f: data = json.load(f)
          assert 'routes' in data and isinstance(data['routes'], list) and data['routes'], 'No routes in plan.json'
          print('plan.json valid with', len(data['routes']), 'routes')
          PY

      - name: Commit plan.json
        run: |
          git config user.name "github-actions"
          git config user.email "actions@users.noreply.github.com"
          git add plan.json
          git commit -m "chore: publish plan.json" || echo "No changes"
          git push


⸻

Output: plan.json (simplified)

{
  "generated_at": "2025-11-05T07:10:00-08:00",
  "timezone": "America/Los_Angeles",
  "day": "2025-11-05",
  "routes": [
    {
      "id": "p40-tiburon",
      "name": "Pier 40 ↔ Tiburon",
      "status": "yellow",            // green | yellow | red
      "skill": "intermediate",
      "effort": 6,                   // 1–10 relative effort
      "windows": [
        {
          "start": "2025-11-05T09:40:00-08:00",
          "end":   "2025-11-05T12:10:00-08:00",
          "reasons": [
            "slack ~10:12",
            "wind 9–14 mph, gust 18",
            "current max 1.2 kts (with you outbound)"
          ]
        }
      ],
      "exposure": ["Crissy (WNW)", "Raccoon Strait (flood)"],
      "data_sources": { "tide": "9414290", "current": "SFB1201", "wind": "sfdc1" },
      "notes": "Avoid ferry window 11:20–11:40"
    }
  ]
}

Status meanings
	•	Green: Within profile thresholds; windows provided.
	•	Yellow: Manageable with caution; tighter windows and exposure notes.
	•	Red: Hold; outside thresholds or insufficient data.

⸻

Running tests

pytest -q

Tests verify plan.json exists, parses, has at least one route, and contains sane field ranges.

⸻

Safety
	•	Daylight-only windows (no night planning).
	•	Conservative defaults when source data is missing or inconsistent.
	•	Final go/no-go remains with trained guides based on on-site conditions.

⸻

Troubleshooting
	•	Empty tide events → ensure local timezone handling and use NOAA interval=hilo.
	•	No windows produced → thresholds may be too strict for the day; try --skill expert to confirm behavior.
	•	Action succeeded but no commit → no material changes since last plan.json.

⸻

Contributing

PRs welcome: docs fixes, station additions, threshold tuning with rationale.
Include a before/after diff of plan.json on at least one historical day.

⸻

License

TBD
