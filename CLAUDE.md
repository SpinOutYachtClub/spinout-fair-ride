# spinout-fair-ride

Safety-first ride planning engine for Waterbike.ai. Generates a daily plan.json
of go/no-go windows for San Francisco Bay waterbike routes. Python, GitHub
Actions, GitHub Pages. Currently v1.8.1 in production.

This is a marine safety system. A wrong output can put a rider in the water at
night in 54 degree fog. Treat every rule below as load-bearing.

---

## Never Do These

- Never change the safety weight. It is 0.40. It is not a tunable parameter.
- Never let a composite score override a threshold violation. Hard No-Go wins.
- Never emit a plan when a required input is missing. Missing input means
  No-Go, not "unknown" and not a warning banner.
- Never present a modeled fallback as a measurement. Label substitutions.
- Never commit directly to main or to a release branch.
- Never bypass a failing check. Do not suggest `--no-verify` or admin override.
- Never edit generated files by hand. docs/plan.json is Action output.
- Never widen scope mid-task. If you notice a second bug, report it, do not fix
  it in the same branch.

If a request would break one of these, stop and say so rather than complying.

---

## Branching

- Branch off main: `feature/*` for new work, `fix/*` for permanent bug fixes
- Hotfixes branch off `release/vX.Y`, never off main
- Release branches never merge back to main. Cherry-pick the hotfix commit.
- One branch, one concern. Under two days old.
- Squash merge to main.
- Every deploy is tagged.

Full rationale is in BRANCHING.md. Read it only when asked.

---

## Before You Report Work Complete

Run these and paste the output:

```
python -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('config/*.yaml')]"
python -m pytest tests/ -q
python src/plan_generator.py
```

Do not say a task is done because the code looks right. Run it.

---

## Bugs That Already Cost Us. Do Not Reintroduce.

**Time Traveler.** Naive datetimes caused NOAA 400s. Every datetime is
timezone aware.

```python
from pytz import timezone
TZ = timezone('America/Los_Angeles')
now = datetime.now(TZ)
```

Never `datetime.now()` bare. Never `utcnow()`.

**API Double-Speak.** NOAA predictions omits the `type` field without
`interval=hilo`. Tide parsing then silently yields zero high/low events and the
safety engine scores against nothing.

```python
params = {'product': 'predictions', 'interval': 'hilo', ...}
```

**Silent Failures.** A third-party commit action failed while reporting
success, so plan.json went stale without alerting. Use direct git commands in
workflows. Assert the file changed before declaring success.

---

## Code Conventions

- Version header with changelog at the top of every module in src/
- Validate every input before use. Assume external APIs return garbage.
- Every external data source needs an explicit fallback and an explicit
  disclosure when the fallback is used.
- Thresholds, weights, routes, and stations live in config/*.yaml. Never
  hardcode a number that an operator might need to change.
- Log the "why" alongside every score and every badge. Explainability is a
  product requirement, not a debug aid.
- Fail loudly. A caught exception that returns a default is how a stale plan
  ships.

---

## Layout

```
src/plan_generator.py    orchestrator
src/data_ingestion.py    API fetching
src/safety_engine.py     rules and scoring
src/routing_solver.py    window and route finding
config/rules.yaml        trip rules, score weights, badges
config/thresholds.yaml   per-tier safety limits
config/stations.yaml     data source mapping
config/routes.yaml       route and leg definitions
docs/plan.json           generated output, do not hand edit
```

---

## Data Sources

| Source | ID | Use | Fallback |
|--------|-----|-----|----------|
| NOAA tides | 9414290 | High/low events | Cached last known good |
| NOAA currents | SFB1201 | Golden Gate current | Seasonal model, disclosed |
| NWS marine | PZZ545 | Advisories | No-Go if unavailable |
| NDBC wind | FTPC1 | Observed wind | OpenWeatherMap |
| OpenWeatherMap | n/a | Forecast wind | Seasonal SF Bay defaults, disclosed |

An active advisory forces Red regardless of every other input.

---

## Safety Canon

WATERBIKE_AI_SAFETY_CANON_V1_0.md governs this repo. Where it and any other
document disagree, the canon wins. Key constraints the code must satisfy:

- Night skill escalation applies exactly once, night operations only,
  non-stacking
- Casual tier riders are excluded from night operations entirely
- Guides required equals ceil(riders / 6), guides excluded from rider count
- Night window opens 4h before sunrise, closes 4h after sunset, no override
- Night visibility minimum is 1 statute mile, Hard No-Go below it
- Night return buffer is 45 minutes, daylight is 30

Visibility has no wired data source yet. Until it does, every night plan must
return No-Go. Do not implement a workaround for this.

---

## When Unsure

Ask before assuming. Specifically ask when:

- A change touches scoring, thresholds, or badge boundaries
- A change alters the plan.json schema, which is a breaking change for every
  downstream consumer even when it looks additive
- A fix requires editing more than one module
- The safest interpretation and the most useful interpretation differ

Recommending No-Go incorrectly costs a refund. Recommending Go incorrectly
costs more than that.

