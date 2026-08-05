# spinout-fair-ride

Safety-first ride planning engine for Waterbike.ai. Generates a daily
docs/plan.json of go/no-go windows for San Francisco Bay waterbike routes.
Python, GitHub Actions, GitHub Pages. Currently v1.8.1 in production.

This is a marine safety system. A wrong output can put a rider in the water at
night in 54 degree fog. Treat every rule below as load-bearing.

---

## Repo Layout Is Flat. README Is Wrong.

README.md describes a `src/` and `config/` structure. That structure does not
exist. It was a plan, never built. Trust this file over README.md on any
question of where something lives.

```
plan_generator.py          entry point, repo root, not in src/
rules.yaml                 config, repo root, not in config/
requirements.txt           see note below
docs/plan.json             generated output, do not hand edit
data/                      contents not yet documented
.github/workflows/publish.yml   daily scheduled run
BRANCHING.md               branch strategy, read only when asked
```

There is no `src/`, no `config/`, no `tests/`, no `.env.example`.
Do not create them without being asked. A repo restructure is planned as
`feature/repo-layout`, after v1.8.2 ships.

`requirements.txt` predates the stdlib-only rebuild of plan_generator.py.
Do not add dependencies. Ask before installing anything from it.

---

## Never Do These

- Never change the safety weight. It is 0.40. It is not a tunable parameter.
- Never let a composite score override a threshold violation. Hard No-Go wins.
- Never emit a plan when a required input is missing. Missing input means
  No-Go, not "unknown" and not a warning banner.
- Never present a modeled fallback as a measurement. Label substitutions.
- Never commit directly to main or to a release branch.
- Never bypass a failing check. Do not suggest `--no-verify` or admin override.
- Never edit docs/plan.json by hand. It is Action output.
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

Branch protection is not yet enabled. These are conventions, not locks.
Full rationale is in BRANCHING.md. Read it only when asked.

---

## Running It

```
python plan_generator.py --date today --skill intermediate --out docs/plan.json
```

Wind API key is `OWM_API_KEY` in repo secrets. README calls it
`OPENWEATHERMAP_API_KEY`. README is wrong.

Config sanity check:

```
python -c "import yaml; yaml.safe_load(open('rules.yaml'))"
```

There is no test suite yet. Do not run pytest. Do not report a task complete
because the code looks right. Run the generator and read the output.

---

## What Already Guards Safety

`.github/workflows/publish.yml` asserts on every daily run:

- `safety_weight == 0.40`, job fails if it drifts
- `routes` is non-empty
- every route status is green, yellow, or red

This runs after merge, on a schedule. It stops a bad plan from publishing.
It does not stop a bad commit from landing. Do not weaken these assertions.

---

## Bugs That Already Cost Us. Do Not Reintroduce.

**Time Traveler.** Naive datetimes caused NOAA 400s. Every datetime is
timezone aware, America/Los_Angeles. Never `datetime.now()` bare. Never
`utcnow()`.

**API Double-Speak.** NOAA predictions omits the `type` field without
`interval=hilo`. Tide parsing then silently yields zero high/low events and the
safety engine scores against nothing.

**Silent Failures.** A third-party commit action failed while reporting
success, so plan.json went stale without alerting. Use direct git commands in
workflows. Assert the file changed before declaring success.

---

## Code Conventions

- Version header with changelog at the top of plan_generator.py
- Python stdlib only. No new dependencies.
- Validate every input before use. Assume external APIs return garbage.
- Every external data source needs an explicit fallback and an explicit
  disclosure when the fallback is used.
- Thresholds, weights, and routes belong in rules.yaml. Never hardcode a
  number an operator might need to change.
- Log the "why" alongside every score and badge. Explainability is a product
  requirement, not a debug aid.
- Fail loudly. A caught exception that returns a default is how a stale plan
  ships.

---

## Data Sources

| Source | ID | Use | Fallback |
|--------|-----|-----|----------|
| NOAA tides | 9414290 | High/low events, needs interval=hilo | Cached last known good |
| NOAA currents | SFB1201 | Golden Gate current | Seasonal model, disclosed |
| NWS marine | PZZ545 | Advisories | No-Go if unavailable |
| OpenWeatherMap | OWM_API_KEY | Forecast wind | Seasonal SF Bay defaults, disclosed |

An active advisory forces Red regardless of every other input.

NOAA migrated its cloud infrastructure in early 2026 and broke these
endpoints. That is the current production outage.

---

## Safety Canon

WATERBIKE_AI_SAFETY_CANON_V1_0.md governs this repo. Where it and any other
document disagree, the canon wins. Key constraints:

- Night skill escalation applies exactly once, night operations only,
  non-stacking
- Casual tier riders are excluded from night operations entirely
- Guides required equals ceil(riders / 6), guides excluded from rider count
- Night window opens 4h before sunrise, closes 4h after sunset, no override
- Night visibility minimum is 1 statute mile, Hard No-Go below it
- Night return buffer is 45 minutes, daylight is 30

Visibility has no wired data source. Until it does, every night plan must
return No-Go, and the product ships daylight-only. Do not implement a
workaround for this.

---

## When Unsure

Ask before assuming. Specifically ask when:

- A change touches scoring, thresholds, or badge boundaries
- A change alters the plan.json schema, which is a breaking change for every
  downstream consumer even when it looks additive
- A fix requires touching more than one file
- The safest interpretation and the most useful interpretation differ

Recommending No-Go incorrectly costs a refund. Recommending Go incorrectly
costs more than that.
