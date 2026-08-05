# Spinout Fair Ride

Automated daily ride planner for Waterbike.ai. A Python script runs on a
schedule via GitHub Actions and publishes `docs/plan.json`, a public file
containing route recommendations, launch windows, and safety badges for San
Francisco Bay.

- **Output:** `docs/plan.json`, regenerated daily
- **Audience:** Guides and instructors, members, guests
- **Scope:** Daylight-only, safety-first recommendations
- **Status:** v1.8.1 in production

> This is decision support for trained operators, not a navigation product.
> The system recommends. A trained guide on site decides. Always verify
> conditions before launch.

---

## Governing Documents

| File | Purpose |
|------|---------|
| `WATERBIKE_AI_SAFETY_CANON_V1_0.md` | Governs all ride logic. Wins over every other document. |
| `CLAUDE.md` | Project memory for Claude Code. Loaded automatically each session. |
| `BRANCHING.md` | Branch strategy, release and hotfix flow, planned CI checks. |
| `SECURITY.md` | Vulnerability reporting. |

Where any document disagrees with the Safety Canon, the Canon wins.

---

## Features

- **Deterministic daily plan.** Computes when to go, not just whether,
  aligning launch and return with daylight and tide slack where possible.
- **Leg-aware currents.** Projects current vectors onto each route leg to
  estimate aiding, opposing, and cross-current demand.
- **Skill profiles.** Casual, Intermediate, and Expert tiers tune wind, gust,
  and adverse-current tolerances.
- **Explainable by design.** Green, yellow, and red badges carry reasons, the
  stations used, and an explicit note when data is modeled rather than
  measured.
- **Zero-ops publishing.** GitHub Actions fetches data, runs the model,
  validates the output, and commits `docs/plan.json`. No servers.

---

## How It Works

1. **Ingest.** NOAA CO-OPS tides and currents (`interval=hilo` required),
   OpenWeatherMap wind, NWS marine advisories, computed sunrise and sunset.
2. **Compute.** Daylight bounds, tide events, per-leg current vectors,
   exposure checks, skill-aware thresholds, safe windows.
3. **Validate.** Safety weight assertion, non-empty routes, badge values in
   range.
4. **Publish.** Commit `docs/plan.json` for the website and app to consume.

---

## Repository Layout

```
spinout-fair-ride/
├─ plan_generator.py           entry point, all planning logic
├─ rules.yaml                  thresholds, weights, badges, route rules
├─ requirements.txt            see note below
├─ docs/
│  └─ plan.json                generated output, served via GitHub Pages
├─ data/
├─ .github/workflows/
│  └─ publish.yml              scheduled daily build and publish
├─ CLAUDE.md
├─ BRANCHING.md
├─ SECURITY.md
└─ README.md
```

The planner is currently a single file at the repo root. A `src/` and
`config/` restructure is planned but not built. Do not assume those
directories exist.

`requirements.txt` predates the stdlib-only rebuild of `plan_generator.py`.
It is retained pending review and may no longer reflect actual dependencies.

---

## Quick Start

Requires Python 3.11 or later.

```bash
git clone https://github.com/SpinOutYachtClub/spinout-fair-ride.git
cd spinout-fair-ride
export OWM_API_KEY=your_key_here
python plan_generator.py --date today --skill intermediate --out docs/plan.json
```

Arguments:

| Flag | Values | Purpose |
|------|--------|---------|
| `--date` | `today` or `YYYY-MM-DD` | Plan date |
| `--skill` | `casual`, `intermediate`, `expert` | Threshold profile |
| `--out` | path | Output file |

Environment:

| Variable | Required | Notes |
|----------|----------|-------|
| `OWM_API_KEY` | Yes | OpenWeatherMap. Stored as a repo secret for Actions. |

---

## Configuration

Thresholds live in `rules.yaml` and mirror Safety Canon section 2. These are
operator settings, not code. Changing them changes what the system will
recommend.

```yaml
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
```

**The safety weight is 0.40 and is not a tunable parameter.** It is asserted
on every build. A drift fails the job and blocks publication.

---

## Data Sources

| Source | Station | Use | Fallback |
|--------|---------|-----|----------|
| NOAA CO-OPS tides | 9414290 | High and low events | Cached last known good |
| NOAA CO-OPS currents | SFB1201 | Golden Gate current | Seasonal model, disclosed |
| NWS marine | PZZ545 | Advisories | No-Go if unavailable |
| OpenWeatherMap | n/a | Forecast wind | Seasonal SF Bay defaults, disclosed |

Fallback status is reported in the `data_quality` block of every plan. The
system does not present a modeled value as a measurement. An active advisory
forces Red regardless of every other input.

**Current status as of the 2026-08-04 plan:**

| Source | Status |
|--------|--------|
| Tides | Live |
| Advisory | Live |
| Wind | Estimated, running on modeled fallback |
| Currents | Not reported in `data_quality` |

Wind has been on fallback rather than live OpenWeatherMap data. Currents are
not currently reported in `data_quality` at all, so a fallback there would be
invisible to a reader. Both are open items.

---

## Automation

The daily build is defined in `.github/workflows/publish.yml`. It runs on a
cron schedule and can be triggered manually with `workflow_dispatch`.

The workflow validates before publishing:

- `safety_weight` equals 0.40, or the job fails
- `routes` is non-empty
- every route status is `green`, `yellow`, or `red`

A failed validation means no publish. The previous good `plan.json` stays
live. This is intentional. A stale plan is safer than a wrong one.

---

## Output Format

`docs/plan.json`, schema version 2.1.2. One route shown, abridged.

```json
{
  "generated_at": "2026-08-04T23:56:50.859142-07:00",
  "version": "2.1.2",
  "timezone": "America/Los_Angeles",
  "day": "2026-08-04",
  "skill_default": "intermediate",
  "skills": ["casual", "intermediate", "expert"],
  "safety_weight": 0.4,
  "advisory": "none",
  "routes": [
    {
      "id": "p40-clipper",
      "name": "Pier 40 to Clipper Cove",
      "status": "yellow",
      "status_by_skill": {
        "casual": "red",
        "intermediate": "yellow",
        "expert": "green"
      },
      "skill": "intermediate",
      "effort": 5,
      "windows": [
        {
          "start": "2026-08-04T06:30:00-07:00",
          "end": "2026-08-04T10:00:00-07:00",
          "reasons": [
            "ebb current aiding outbound",
            "wind 11 mph, gust 15"
          ]
        }
      ],
      "exposure": ["Bay Bridge shadow", "Yerba Buena chop"],
      "data_sources": {
        "tide": "9414290",
        "current": "SFB1201",
        "wind": "OpenWeatherMap"
      },
      "daylight": {
        "sunrise": "2026-08-04T06:15:18.040230-07:00",
        "sunset": "2026-08-04T20:16:25.772718-07:00"
      },
      "notes": "Mind posted ferry windows and verify on-site conditions before launch."
    }
  ],
  "data_quality": {
    "tide": "live",
    "wind": "estimated",
    "advisory": "live",
    "notes": "Estimated sources are modeled fallbacks. Guides make the final call."
  }
}
```

### Top-level fields

| Field | Notes |
|-------|-------|
| `version` | Schema version. Consumers should check this. |
| `day` | The date the plan applies to, local time |
| `safety_weight` | Always 0.4. Asserted on every build. |
| `advisory` | `none`, or the active NWS marine advisory |
| `skills` | Profiles graded in `status_by_skill` |
| `data_quality` | Per-source `live` or `estimated`. See below. |

### Per-route fields

| Field | Notes |
|-------|-------|
| `status` | Badge for `skill_default` |
| `status_by_skill` | Badge for every profile. A route can be green for expert and red for casual on the same day. |
| `windows` | Empty array means hold. Not an error. |
| `daylight` | Sunrise and sunset. Windows close 30 minutes before sunset. |
| `exposure` | Named hazard zones on the route |

### Badge meanings

| Badge | Meaning |
|-------|---------|
| Green | Within profile thresholds. Windows provided. |
| Yellow | Manageable with caution. Tighter windows, exposure noted. |
| Red | Hold. Outside thresholds, advisory active, or required data missing. |

An empty `windows` array with a red status is a correct and expected output.
It means the day does not clear thresholds for that profile. Consumers must
render this as a hold, never as missing data.

Timestamps are emitted at full precision, including microseconds on
sunrise, sunset, and any window boundary derived from them. A window ending
at `19:45:23.816309-07:00` is sunset minus the 30 minute return buffer.
Consumers must format these for display. Never render a raw timestamp to a
rider.

### Reading data_quality

`live` means the value came from the named source. `estimated` means the
source was unavailable and a modeled fallback was substituted. Any consumer
displaying a plan must surface `estimated` to the rider. A modeled wind speed
must never be presented as a measurement.

Any change to this schema is a breaking change for downstream consumers, even
when it looks additive.

---

## Contributing

Branch off `main` using `feature/*` or `fix/*`. See `BRANCHING.md` for the
full model, including release and hotfix paths.

Pull requests welcome for documentation fixes, station additions, and
threshold tuning with rationale. For any change affecting scoring or
thresholds, include a before and after diff of `plan.json` for at least one
historical day.

There is no automated test suite yet. Three tests are planned and specified in
`BRANCHING.md` section 8: safety weight enforcement, casual night exclusion,
and missing-input No-Go.

---

## Safety

- Daylight-only windows. Night planning is specified in the Safety Canon but
  is not enabled, because no visibility data source is wired in. Under Canon
  principle 5, absence of required data is a No-Go, not an unknown.
- Conservative defaults when source data is missing or inconsistent.
- Cancellation is the default outcome under uncertainty.
- Final go or no-go authority rests with the guide on site.

---

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| Empty tide events | Missing `interval=hilo` on the NOAA request |
| NOAA returns 400 | Naive datetime. All datetimes must be timezone aware. |
| No windows produced | Thresholds too strict for the day. Try `--skill expert` to confirm behavior. |
| Action succeeded, no commit | No material change since the last plan |
| Action succeeded, plan stale | Validation failed, or a commit step failed silently. Check the run log. |

---

## License

TBD
