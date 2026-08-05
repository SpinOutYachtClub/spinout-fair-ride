# Branching Strategy

Repo: spinout-fair-ride
Version: 1.0
Status: Active
Owner: SpinOut Yacht Club
Last updated: 2026-08-04

This document explains how code moves from an idea to production in this
repository. It is written for a person. The machine-readable version of these
rules lives in CLAUDE.md at the repo root.

Neither file enforces anything. Enforcement lives in branch protection and CI.
If a rule here is not backed by a required status check, treat it as a habit,
not a guarantee.

---

## 1. The Short Version

Most of the time you will only do this:

1. Branch off main
2. Make a small change
3. Open a pull request
4. CI passes, you merge, main is deployable again
5. Tag it and ship it

Release branches and hotfix branches are the exceptions. You cut them only when
production needs a patch and main has already moved on. If you are not sure
whether you need one, you do not need one.

---

## 2. Branch Map

| Branch | Lives for | Cut from | Merges to | Purpose |
|--------|-----------|----------|-----------|---------|
| main | Forever | n/a | n/a | Always deployable. Source code only. Protected. |
| feature/* | Under 2 days | main | main | New work |
| fix/* | Under 2 days | main | main | Permanent bug fixes |
| release/vX.Y | Weeks | main | never | Stabilizing a shipped version |
| hotfix/* | Hours | release/vX.Y | release, then cherry-pick to main | Emergency production patch |
| data/plan | Forever | orphan | never | Generated plan.json only. Not yet active, see section 7. |

Tags mark what actually shipped. Every deploy gets one. No exceptions.

---

## 3. Naming

```
feature/tide-window-solver
feature/per-leg-current-projection
fix/wind-station-fallback
hotfix/noaa-endpoint-migration
release/v1.8
```

Lowercase, hyphens, no spaces, no personal names, no ticket numbers unless the
ticket is the clearest description available.

Tags follow semantic-ish versioning:

- Patch bump (v1.8.1 to v1.8.2) for fixes that change no behavior a rider sees
- Minor bump (v1.8 to v1.9) for new capability that is backward compatible
- Major bump for a plan.json schema change that breaks consumers

Any change to the plan.json schema is a breaking change even if it looks
additive. Downstream spokes parse it.

---

## 4. The Normal Path

This is the path for roughly 90 percent of commits.

```
main ──────●──────────●──────────●─────── tag v1.9.0
            \        /
             ●──────●
          feature/tide-window-solver
```

Steps:

1. `git checkout main && git pull`
2. `git checkout -b feature/short-description`
3. Commit as often as you like. Nobody else reads these commits.
4. Push and open a PR against main.
5. Wait for all required checks. Do not merge red.
6. Squash merge. One feature becomes one commit on main.
7. Delete the branch.

Keep branches under two days old. A branch that lives a week has stopped being a
branch and started being a fork. If work is taking longer, merge the safe,
inert parts to main behind a config flag and keep going.

---

## 5. Release Branches

Cut one only when both of these are true:

- A version is live in production
- Main has already moved past it with work you do not want to ship yet

If main is idle, skip the release branch. Tag main and deploy.

```
git checkout main
git checkout -b release/v1.8 <sha-of-last-known-good>
git push -u origin release/v1.8
```

Rules:

- Release branches never merge back into main. Ever.
- Only hotfixes land on a release branch. No features, no refactors, no
  "while I am in here" cleanup.
- Delete the branch once its version is retired and every hotfix has a matching
  permanent fix on main.
- Do not run more than two release branches at once. If you need a third, the
  real problem is that main is not shipping often enough.

---

## 6. Hotfixes

This is the highest-risk path in the repo. It is also the path most likely to
be taken at 11pm with the site down.

```
release/v1.8 ──●────────●──── tag v1.8.2
                \      /
                 ●────●
             hotfix/noaa-endpoint-migration
                     │
                     └── cherry-pick ──> main
```

Steps:

1. `git checkout release/v1.8 && git pull`
2. `git checkout -b hotfix/short-description`
3. Fix the one thing. Nothing else.
4. PR into release/v1.8. Full CI runs. All required checks apply.
5. Merge, tag the patch version, deploy, verify the live widget renders.
6. `git checkout main && git cherry-pick <sha>`
7. Open an issue labeled `permanent-fix` if the hotfix was a workaround.

**Two rules that are not negotiable:**

**Hotfix branches run the identical required check set as main.** No admin
bypass, no `--no-verify`, no "it is only a config change." The emergency path
is exactly where a marine safety system hurts someone. A degraded site is an
inconvenience. A wrong safety badge is not.

**Every hotfix gets a permanent fix on main within 7 days, or it was never a
fix.** Track it as an issue. If the 7 days pass and nothing happened, the
workaround has quietly become the architecture.

---

## 7. The Data Plane Split

Status: Planned. Not active. Do not cut over during a production incident.

Today GitHub Actions writes the generated `docs/plan.json` back to main. Code
and generated data share a branch. This is why the workflow needs
`git pull --rebase origin main` before every push, and it gets worse as more
spokes write outputs.

Target state: an orphan branch `data/plan` holds generated artifacts only.
GitHub Pages serves from there. Code branches never contain generated output.

Cutover checklist, to be run on a calm day:

1. Production is green and has been for 72 hours
2. Create the orphan branch and seed it with the current plan.json
3. Point GitHub Pages at data/plan
4. Verify the Squarespace widget renders from the new URL
5. Keep the old path serving a redirect for 7 days
6. Add `docs/plan.json` to .gitignore on code branches
7. Update the Actions workflow to push to data/plan

Until step 7 lands, the current behavior stands and is correct.

---

## 8. Branch Protection and Required Checks

Applied to `main` and every `release/*` branch, identically.

| Check | Asserts | Source |
|-------|---------|--------|
| safety_weight | Safety weight equals 0.40, no drift | Safety Canon 1.1 |
| hard_no_go_precedence | No composite score can override a threshold violation | Safety Canon 1.2 |
| escalation_nonstacking | Night skill escalation applies once, night only | Safety Canon 4 |
| casual_night_exclusion | Casual tier is refused for night operations | Safety Canon 4 |
| guide_ratio | Guides required equals ceil(riders / 6) | Safety Canon 6 |
| window_boundaries | Night window is sunrise minus 4h to sunset plus 4h | Safety Canon 3 |
| missing_input_no_go | Missing required input returns No-Go, not a warning | Safety Canon 1.5 |
| fallback_disclosure | Modeled fallback is never presented as a measurement | Safety Canon 1.4 |
| noaa_contract | interval=hilo present, all datetimes timezone aware | Known bugs 1 and 2 |
| config_schema | All YAML in config/ parses and validates | Defensive default |

Settings:

- Require PR before merging
- Require all checks above to pass
- Require branches to be up to date before merging
- Do not allow force push
- Do not allow deletions
- Include administrators. This one matters. You are the administrator.

---

## 9. Commit Messages

Short imperative subject line, under 72 characters. Body only when the change
needs a why.

```
Fix NOAA tide fetch missing interval=hilo

The predictions product returns no type field without this parameter,
so parse_tide_events silently produced zero high/low events and the
safety engine scored against an empty tide series.
```

Prefix generated commits so they are filterable:

```
chore(data): daily plan 2026-08-04
```

---

## 10. Worked Example: The Current NOAA Fix

The site is degraded. The fix package targets NOAA endpoint migration, the
Time Traveler bug, the API Double-Speak bug, and silent Action failures.

```
1. git tag v1.8.1-prod <current-deployed-sha>
2. git push origin v1.8.1-prod
3. git checkout -b release/v1.8 <last-known-good-sha>
4. git checkout -b hotfix/noaa-endpoint-migration
5. Apply the fix package. Nothing else.
6. PR into release/v1.8. All checks green.
7. Merge, tag v1.8.2, deploy.
8. Verify spinoutfitness.com/waterbikeai renders a real plan.
9. git checkout main && git cherry-pick <sha>
10. Only now resume waterbike-ai-nautilus.
```

Step 1 exists so you can get back to today if the fix makes things worse.
Do not skip it because you are in a hurry. You are always in a hurry.

---

## 11. Common Mistakes

| Mistake | What happens | Do instead |
|---------|--------------|------------|
| Merging release into main | Stabilization commits and their history flood main | Cherry-pick the single hotfix commit |
| Long-lived feature branch | Painful merge, large untestable diff | Merge early behind a config flag |
| Committing generated plan.json in a feature branch | Conflicts with the daily Action on every merge | Let the Action own it, see section 7 |
| Hotfixing directly on main | Untested emergency code becomes the trunk | Branch, even at 11pm |
| Bypassing a red check to ship | The check existed for a reason you have forgotten | Fix the check or fix the code |
| Vibe-coding a large change in one session | Unreviewable diff, no rollback point | One branch, one concern, small |

---

## 12. Working With Claude Code

The AI reads CLAUDE.md automatically at the start of every session. It does not
read this file unless you ask it to, and that is deliberate: this document is
long and would consume context every session for no gain.

If Claude Code proposes committing straight to main, bypassing a check, or
editing generated output, it has drifted. Stop the session, point it at
CLAUDE.md, and start again. Never assume the model remembers a rule from an
earlier session. It does not.

Rules the AI must obey belong in CLAUDE.md. Rules that must never be broken
belong in CI. This document is the explanation, not the enforcement.

---

## 13. Change Control

Changes to sections 6 and 8 require a documented rationale, because those two
sections are what keep an emergency from reaching riders unchecked.

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-08-04 | Initial strategy, trunk-based with release and hotfix paths |
