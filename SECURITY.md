# Security Policy

We keep riders safe by keeping our code safe. Thanks for helping us protect the community.

## Supported Versions

We support the active branch and the most recent minor releases. Older versions receive fixes only if explicitly marked LTS.

| Version  | Supported                      |
|--------- |--------------------------------|
| `main`   | :white_check_mark: Active      |
| `1.3.x`  | :white_check_mark:             |
| `1.2.x`  | :white_check_mark:             |
| `1.1.x`  | :white_check_mark: Security fixes only until 2026-03-31 |
| `< 1.1`  | :x:                            |

> Maintainers: update the table on each release. If your repo is pre-1.0, treat the latest two minors as supported.

---

## Reporting a Vulnerability

**Please use one of the two options below:**

1) **GitHub Security Advisories**  
   Go to **Security → Report a vulnerability** in this repository. This creates a private advisory thread with maintainers.

2) **Email (encrypted preferred)**  
   Send details to **security@spinoutfitness.com** with the subject line: `VULN REPORT: <project> <version>`.  
   Optional PGP key: `pgp.pub` in the repo root (or request via email).

### What to include

- Affected repo, versions, and environment.
- Impact summary and CVSS v3.x estimate if you have one.
- Repro steps or proof-of-concept (minimal, deterministic).
- Any logs, stack traces, or screenshots that help triage.
- Your disclosure timeline preferences and contact handle for credit.

Please avoid sending secrets or personal data. Redact when possible.

---

## Our Response & Timelines

We aim to be responsive and predictable.

- **Acknowledgment:** within **2 business days**
- **Triage & severity assignment:** within **5 business days**
- **Status updates:** at least **weekly** until resolution
- **Target fix windows (from triage date):**
  - Critical: **7 days**
  - High: **14 days**
  - Medium: **30 days**
  - Low: **90 days**

If broad exploitation is observed, we may publish interim mitigations sooner.

---

## Coordinated Disclosure

- We prefer coordinated disclosure with an initial **90-day** embargo.
- We may shorten the window if a fix or mitigation ships earlier.
- If we cannot meet the target window, we’ll explain why and propose a new date.
- Duplicate reports are appreciated; credit goes to the first clear report, with honorable mentions for meaningful extras.

---

## Scope

**In scope**
- Repositories under the SpinOut Fitness / Waterbike.ai GitHub orgs.
- First-party code, configs, and release artifacts we publish.

**Out of scope**
- Social engineering, physical attacks, or third-party platforms we use (e.g., hosting, ESPs, booking systems).  
  You’re welcome to report them upstream; if you inform us, we’ll route to the vendor when possible.
- Denial-of-service tests that degrade service for real users.
- Automated scanner results without a working proof of impact.

---

## Safe Harbor

We will not pursue legal action for **good-faith** research that:
- Avoids privacy violations, data destruction, and service degradation.
- Uses only the minimum data necessary to demonstrate impact.
- Respects rate limits and never attempts ransom or extortion.
- Stops immediately if asked by a maintainer.

If you’re unsure whether your approach is acceptable, contact us first.

---

## Fixes, Advisories, and Credit

- Security fixes ship as patches to supported versions and the `main` branch.
- We publish a brief advisory with impact, affected versions, and upgrade/mitigation steps.
- With permission, we add you to our **Hall of Thanks** in `SECURITY.md` or `CREDITS.md`.

---

## Contact

- Primary: **security@spinoutfitness.com**
- Emergencies (critical, actively exploited): use GitHub Security Advisory **and** email.

Thank you for helping keep the community safe.
