#!/usr/bin/env python3
"""
Waterbike AI - Daily Plan Generator
Version: 2.1.2  (wind interpolation fix)

Generates a daily plan.json of safety-scored ride windows for SF Bay
waterbike routes. Pure Python standard library only, so it runs on a
bare GitHub Actions runner with no pip install step.

Design rules (hard-won, do not regress):
  - Time Traveler bug: always use timezone-aware time in America/Los_Angeles.
    Never call bare datetime.now() or datetime.utcnow() anywhere.
  - API Double-Speak bug: NOAA tide predictions require interval=hilo to
    return the 'type' (H/L) field. Always send it.
  - NOAA cloud migration: use the current endpoint and send an
    application= identifier on every call (NOAA's own examples all do).
  - Silent Failures: this script never crashes on a bad API. Every external
    call degrades to a labeled fallback, and a data_quality block records
    which sources were live vs estimated.

Safety principle (immutable):
  SAFETY_WEIGHT = 0.40 is a foundational design constant. Hard No-Go rules
  (active advisory, over-threshold wind/gust/current, insufficient daylight)
  force a Red badge regardless of the numeric score. A good score can never
  buy back a hard safety violation.
"""

import argparse
import csv
import json
import math
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------

VERSION = "2.1.2"
APP_ID = "WaterbikeAI"                       # NOAA courtesy identifier
TZ = ZoneInfo("America/Los_Angeles")         # single source of local time
SAFETY_WEIGHT = 0.40                         # immutable; see module docstring
HTTP_TIMEOUT = 12                            # seconds, fail fast to fallback

NOAA_DATAGETTER = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
NWS_ALERTS = "https://api.weather.gov/alerts/active"
OWM_FORECAST = "https://api.openweathermap.org/data/2.5/forecast"

# SF reference point for solar (daylight) math
SF_LAT = 37.7955
SF_LON = -122.3937

STATIONS = {
    "tide": "9414290",       # San Francisco (Bay), CA
    "current": "SFB1201",    # Golden Gate / Bay current station
    "wind_owm": (37.806, -122.465),  # near Fort Point for wind lat/lon
}

# Skill profiles. Mirrors config/thresholds.yml so guides can externalize
# these to YAML later without touching scoring logic.
THRESHOLDS = {
    "casual":       {"max_wind": 12, "max_gust": 16, "max_adverse_current": 0.6},
    "intermediate": {"max_wind": 16, "max_gust": 22, "max_adverse_current": 1.0},
    "expert":       {"max_wind": 22, "max_gust": 30, "max_adverse_current": 1.5},
}
SKILLS = ["casual", "intermediate", "expert"]

# Route table. current_scale approximates how strongly the Golden Gate
# flood/ebb is felt on this route (1.0 = full Gate strength, lower = more
# sheltered). Bearings drive the aiding/opposing current projection.
ROUTES = [
    {
        "id": "p40-tiburon",
        "name": "Pier 40 to Tiburon",
        "current_scale": 0.85,
        "exposure": ["Crissy (WNW)", "Raccoon Strait (flood)"],
        "ferry_sensitive": True,
        "legs": [
            {"name": "Pier 40 to Fort Point", "bearing": 315, "distance_mi": 3.2, "exposure_index": 1.4},
            {"name": "Fort Point to Tiburon", "bearing": 25, "distance_mi": 4.1, "exposure_index": 1.8},
        ],
    },
    {
        "id": "p40-cavallo",
        "name": "Pier 40 to Cavallo Point",
        "current_scale": 1.0,
        "exposure": ["Golden Gate mouth", "Horseshoe Bay eddy"],
        "ferry_sensitive": False,
        "legs": [
            {"name": "Pier 40 to Fort Point", "bearing": 315, "distance_mi": 3.2, "exposure_index": 1.4},
            {"name": "Fort Point to Horseshoe Bay", "bearing": 300, "distance_mi": 1.6, "exposure_index": 2.0},
        ],
    },
    {
        "id": "p40-clipper",
        "name": "Pier 40 to Clipper Cove",
        "current_scale": 0.5,
        "exposure": ["Bay Bridge shadow", "Yerba Buena chop"],
        "ferry_sensitive": True,
        "legs": [
            {"name": "Pier 40 to Clipper Cove", "bearing": 70, "distance_mi": 2.4, "exposure_index": 1.1},
        ],
    },
    {
        "id": "p40-p39",
        "name": "Pier 40 to Pier 39",
        "current_scale": 0.4,
        "exposure": ["Embarcadero waterfront"],
        "ferry_sensitive": True,
        "legs": [
            {"name": "Pier 40 to Pier 39", "bearing": 340, "distance_mi": 1.5, "exposure_index": 0.8},
        ],
    },
]

# Seasonal SF Bay wind fallback (mph), used only when live wind is
# unavailable. Bay afternoons are windier than mornings, summer strongest.
# base = typical sustained mph around midday; am_factor/pm_factor shift it.
SEASONAL_WIND = {
    1: 9, 2: 10, 3: 12, 4: 14, 5: 16, 6: 18,
    7: 19, 8: 18, 9: 15, 10: 12, 11: 10, 12: 9,
}

# Rules
MIN_DAYLIGHT_RETURN_MIN = 30
FERRY_WINDOWS = {
    "weekday": [("07:00", "10:00"), ("16:00", "19:00")],
    "weekend": [("10:00", "12:00"), ("15:00", "17:00")],
}
STEP_MIN = 30  # window sampling resolution


# ----------------------------------------------------------------------------
# HTTP helper (never raises)
# ----------------------------------------------------------------------------

def _get(url, params=None, headers=None):
    """Return (parsed_or_text, ok). Any failure returns (None, False)."""
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "WaterbikeAI/2.1.1 (+https://waterbike.ai)"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", "replace")
        try:
            return json.loads(raw), True
        except json.JSONDecodeError:
            return raw, True
    except Exception as exc:  # noqa: BLE001 - defensive by design
        sys.stderr.write(f"[fetch] {url} failed: {exc}\n")
        return None, False


# ----------------------------------------------------------------------------
# Daylight (NOAA solar algorithm, no network)
# ----------------------------------------------------------------------------

def sun_times(date, lat=SF_LAT, lon=SF_LON):
    """Return (sunrise, sunset) as tz-aware local datetimes for the date."""
    n = date.timetuple().tm_yday
    gamma = 2 * math.pi / 365 * (n - 1 + 0.5)  # solar noon approximation
    eqtime = 229.18 * (
        0.000075 + 0.001868 * math.cos(gamma) - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma) - 0.040849 * math.sin(2 * gamma)
    )
    decl = (
        0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma) + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma) + 0.00148 * math.sin(3 * gamma)
    )
    lat_r = math.radians(lat)
    cos_h = math.cos(math.radians(90.833)) / (math.cos(lat_r) * math.cos(decl)) - math.tan(lat_r) * math.tan(decl)
    cos_h = max(-1.0, min(1.0, cos_h))
    ha = math.degrees(math.acos(cos_h))

    def _utc_minutes_to_local(mins):
        base = datetime(date.year, date.month, date.day, tzinfo=timezone.utc)
        return (base + timedelta(minutes=mins)).astimezone(TZ)

    sunrise = _utc_minutes_to_local(720 - 4 * (lon + ha) - eqtime)
    sunset = _utc_minutes_to_local(720 - 4 * (lon - ha) - eqtime)
    return sunrise, sunset


# ----------------------------------------------------------------------------
# Tides (NOAA) + fallback
# ----------------------------------------------------------------------------

def fetch_tides(date):
    """Return (events, live). events = [{'t': dt, 'type': 'H'|'L', 'height': ft}]."""
    day = date.strftime("%Y%m%d")
    params = {
        "station": STATIONS["tide"],
        "product": "predictions",
        "datum": "MLLW",
        "time_zone": "lst_ldt",
        "units": "english",
        "interval": "hilo",          # required for the H/L type field
        "format": "json",
        "application": APP_ID,
        "begin_date": day,
        "end_date": day,
    }
    data, ok = _get(NOAA_DATAGETTER, params)
    events = []
    if ok and isinstance(data, dict) and data.get("predictions"):
        for p in data["predictions"]:
            try:
                t = datetime.strptime(p["t"], "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
                events.append({"t": t, "type": p.get("type", "?"), "height": float(p["v"])})
            except (KeyError, ValueError):
                continue
    if events:
        return events, True

    # Fallback: synthesize a plausible semidiurnal tide (period 12h25m).
    # Clearly estimated; used only to keep current phase reasoning alive.
    events = []
    anchor = datetime(date.year, date.month, date.day, 3, 0, tzinfo=TZ)
    period = timedelta(hours=6, minutes=12, seconds=30)
    kind = "L"
    for i in range(5):
        events.append({"t": anchor + period * i, "type": kind, "height": 0.5 if kind == "L" else 5.5})
        kind = "H" if kind == "L" else "L"
    return events, False


def current_at(when, tide_events, current_scale):
    """Estimate ('flood'|'ebb'|'slack', signed_speed_kts) at a time.

    Flood (water flooding into the Bay) between a low and the next high;
    ebb between a high and the next low. Magnitude follows a sine between
    slack points, peaking mid-cycle, scaled per route.
    """
    prev_ev = None
    next_ev = None
    for ev in tide_events:
        if ev["t"] <= when:
            prev_ev = ev
        elif next_ev is None:
            next_ev = ev
    if not prev_ev or not next_ev:
        return "slack", 0.0
    span = (next_ev["t"] - prev_ev["t"]).total_seconds()
    if span <= 0:
        return "slack", 0.0
    frac = (when - prev_ev["t"]).total_seconds() / span
    phase = "flood" if prev_ev["type"] == "L" else "ebb"
    peak = 2.6 * current_scale  # kts near Golden Gate at full scale
    speed = peak * math.sin(math.pi * frac)
    if speed < 0.2:
        return "slack", round(speed, 2)
    return phase, round(speed, 2)


# ----------------------------------------------------------------------------
# Wind (OpenWeatherMap) + seasonal fallback
# ----------------------------------------------------------------------------

def _seasonal_hour(date, hour):
    """Modeled SF Bay wind for one hour: calm mornings, windy afternoons."""
    base = SEASONAL_WIND[date.month]
    if hour < 10:
        factor = 0.6
    elif hour < 13:
        factor = 0.85
    elif hour < 18:
        factor = 1.15   # classic Bay afternoon westerly
    else:
        factor = 0.8
    wind = round(base * factor)
    return {"wind": wind, "gust": round(wind * 1.35)}


def _interpolate_hours(points):
    """Fill all 24 hours from sparse (hour, wind, gust) samples.

    OpenWeatherMap's free 5-day endpoint reports every 3 hours, so a plain
    exact-hour lookup finds data for only 8 of 24 hours. Linearly interpolate
    between samples and clamp at the ends, so every hour reflects real
    forecast data rather than a hardcoded placeholder.
    """
    if not points:
        return {}
    pts = sorted(points, key=lambda p: p[0])
    hourly = {}
    for h in range(24):
        before = None
        after = None
        for p in pts:
            if p[0] <= h:
                before = p
            if p[0] >= h and after is None:
                after = p
        if before and after and before[0] != after[0]:
            span = after[0] - before[0]
            frac = (h - before[0]) / span
            wind = before[1] + (after[1] - before[1]) * frac
            gust = before[2] + (after[2] - before[2]) * frac
        else:
            src = before or after
            wind, gust = src[1], src[2]
        hourly[f"{h:02d}"] = {"wind": round(wind), "gust": round(gust)}
    return hourly


def fetch_wind(date, owm_key):
    """Return (hourly, live). hourly maps 'HH' -> {'wind': mph, 'gust': mph}."""
    lat, lon = STATIONS["wind_owm"]
    if owm_key:
        params = {"lat": lat, "lon": lon, "appid": owm_key, "units": "imperial"}
        data, ok = _get(OWM_FORECAST, params)
        if ok and isinstance(data, dict) and data.get("list"):
            samples = []
            for slot in data["list"]:
                try:
                    t = datetime.fromtimestamp(slot["dt"], tz=timezone.utc).astimezone(TZ)
                    if t.date() != date.date():
                        continue
                    wind = float(slot["wind"]["speed"])
                    gust = float(slot["wind"].get("gust", wind * 1.3))
                    samples.append((t.hour, wind, gust))
                except (KeyError, ValueError):
                    continue
            # Require at least 3 real samples before trusting the day as live.
            # Fewer than that (e.g. a late-evening run near the forecast edge)
            # means most of the day would be extrapolated from one point.
            if len(samples) >= 3:
                return _interpolate_hours(samples), True

    # Fallback: seasonal diurnal curve. Mornings calmer, afternoons windier.
    hourly = {f"{h:02d}": _seasonal_hour(date, h) for h in range(24)}
    return hourly, False


# ----------------------------------------------------------------------------
# Marine advisory (NWS) + fallback
# ----------------------------------------------------------------------------

def fetch_advisory():
    """Return (status, live). status in {'none','small_craft','gale','unknown'}."""
    params = {"zone": "PZZ545"}
    data, ok = _get(NWS_ALERTS, params, headers={
        "User-Agent": "WaterbikeAI/2.1.1 (safety@waterbike.ai)",
        "Accept": "application/geo+json",
    })
    if ok and isinstance(data, dict):
        events = []
        for feat in data.get("features", []):
            ev = (feat.get("properties", {}) or {}).get("event", "")
            events.append(ev.lower())
        text = " ".join(events)
        if "gale" in text or "storm" in text:
            return "gale", True
        if "small craft" in text:
            return "small_craft", True
        return "none", True
    return "unknown", False


# ----------------------------------------------------------------------------
# Scoring
# ----------------------------------------------------------------------------

def _in_ferry_window(when):
    windows = FERRY_WINDOWS["weekend" if when.weekday() >= 5 else "weekday"]
    hm = when.strftime("%H:%M")
    return any(a <= hm < b for a, b in windows)


def score_step(route, when, wind, gust, cur_phase, cur_speed, skill, advisory):
    """Return (score 0-100, reasons list, hard_nogo bool) for one time step."""
    th = THRESHOLDS[skill]
    reasons = []
    hard_nogo = False

    # Aiding vs opposing: project current onto the outbound first leg bearing.
    # A flood pushes into the Bay (~090 true); ebb pushes out (~270 true).
    set_dir = 90 if cur_phase == "flood" else (270 if cur_phase == "ebb" else None)
    adverse_component = 0.0
    if set_dir is not None and cur_speed > 0:
        bearing = route["legs"][0]["bearing"]
        angle = math.radians((set_dir - bearing + 180) % 360 - 180)
        # positive cos => opposing the direction of travel on the outbound leg
        adverse_component = max(0.0, cur_speed * math.cos(angle))

    # Hard No-Go gates (safety cannot be scored away)
    if advisory in ("small_craft", "gale"):
        hard_nogo = True
        reasons.append("Small Craft Advisory in effect" if advisory == "small_craft" else "Gale warning in effect")
    if wind > th["max_wind"]:
        hard_nogo = True
        reasons.append(f"wind {wind} mph over {skill} limit {th['max_wind']}")
    if gust > th["max_gust"]:
        hard_nogo = True
        reasons.append(f"gust {gust} mph over {skill} limit {th['max_gust']}")
    if adverse_component > th["max_adverse_current"]:
        hard_nogo = True
        reasons.append(f"adverse current {adverse_component:.1f} kts over {skill} limit {th['max_adverse_current']}")

    # Soft score from available factors (0-100). Wave height is not modeled
    # (no wave source wired in), so it is intentionally excluded.
    wind_pen = min(1.0, wind / max(1, th["max_wind"]))
    gust_pen = min(1.0, gust / max(1, th["max_gust"]))
    cur_pen = min(1.0, adverse_component / max(0.1, th["max_adverse_current"]))
    exposure = max(l["exposure_index"] for l in route["legs"])
    exp_pen = min(1.0, (exposure - 0.8) / 1.2)  # 0.8 -> 0, 2.0 -> 1.0
    ferry_pen = 1.0 if (route["ferry_sensitive"] and _in_ferry_window(when)) else 0.0

    penalty = (
        0.34 * wind_pen + 0.18 * gust_pen + 0.28 * cur_pen
        + 0.15 * exp_pen + 0.05 * ferry_pen
    )
    score = round(max(0, min(100, 100 * (1 - penalty))))

    # Positive-side reasons for explainability
    if cur_phase == "slack":
        reasons.append("near slack water")
    elif adverse_component < 0.2:
        reasons.append(f"{cur_phase} current aiding outbound")
    else:
        reasons.append(f"{cur_phase} current {cur_speed:.1f} kts, {adverse_component:.1f} adverse")
    reasons.append(f"wind {wind} mph, gust {gust}")
    if ferry_pen:
        reasons.append("inside a ferry window, expect traffic")

    if hard_nogo:
        score = min(score, 40)  # keep it visibly Red
    return score, reasons, hard_nogo


def badge(score, hard_nogo):
    if hard_nogo or score < 50:
        return "red"
    if score < 70:
        return "yellow"
    return "green"


# ----------------------------------------------------------------------------
# Per-route computation
# ----------------------------------------------------------------------------

def plan_route(route, date, tides, wind_hourly, advisory, default_skill):
    sunrise, sunset = sun_times(date)
    last_launch = sunset - timedelta(minutes=MIN_DAYLIGHT_RETURN_MIN)

    status_by_skill = {}
    windows_default = []
    best_effort = 5

    for skill in SKILLS:
        step = sunrise.replace(minute=0, second=0, microsecond=0)
        open_win = None
        skill_windows = []
        day_best = 0

        while step <= last_launch:
            if step < sunrise:
                step += timedelta(minutes=STEP_MIN)
                continue
            hh = step.strftime("%H")
            # No silent placeholder: if an hour is somehow absent, use the
            # seasonal curve for that hour rather than a fixed number that
            # would look like a real measurement.
            w = wind_hourly.get(hh) or _seasonal_hour(date, int(hh))
            phase, speed = current_at(step, tides, route["current_scale"])
            score, reasons, nogo = score_step(route, step, w["wind"], w["gust"], phase, speed, skill, advisory)
            day_best = max(day_best, 0 if nogo else score)
            acceptable = (not nogo) and score >= 50

            if acceptable and open_win is None:
                open_win = {"start": step, "reasons": reasons}
            elif not acceptable and open_win is not None:
                open_win["end"] = step
                skill_windows.append(open_win)
                open_win = None
            step += timedelta(minutes=STEP_MIN)

        if open_win is not None:
            open_win["end"] = min(step, last_launch)
            skill_windows.append(open_win)

        status_by_skill[skill] = badge(day_best, day_best == 0)
        if skill == default_skill:
            windows_default = skill_windows
            best_effort = _effort_from_score(day_best)

    return {
        "id": route["id"],
        "name": route["name"],
        "status": status_by_skill[default_skill],
        "status_by_skill": status_by_skill,
        "skill": default_skill,
        "effort": best_effort,
        "windows": [
            {
                "start": w["start"].isoformat(),
                "end": w["end"].isoformat(),
                "reasons": w["reasons"],
            }
            for w in windows_default
        ],
        "exposure": route["exposure"],
        "data_sources": {"tide": STATIONS["tide"], "current": STATIONS["current"], "wind": "OpenWeatherMap"},
        "daylight": {"sunrise": sunrise.isoformat(), "sunset": sunset.isoformat()},
        "notes": _route_note(route, windows_default),
    }


def _effort_from_score(score):
    # Lower safety score => higher effort. Clamp 1-10.
    return max(1, min(10, round(10 - score / 12)))


def _route_note(route, windows):
    if not windows:
        return "Hold today. No window clears the safety thresholds for the selected skill."
    if route["ferry_sensitive"]:
        return "Mind posted ferry windows and verify on-site conditions before launch."
    return "Verify on-site conditions before launch."


# ----------------------------------------------------------------------------
# Plan assembly + output
# ----------------------------------------------------------------------------

def build_plan(date, owm_key, default_skill):
    tides, tides_live = fetch_tides(date)
    wind_hourly, wind_live = fetch_wind(date, owm_key)
    advisory, adv_live = fetch_advisory()

    routes = [plan_route(r, date, tides, wind_hourly, advisory, default_skill) for r in ROUTES]

    return {
        "generated_at": datetime.now(TZ).isoformat(),
        "version": VERSION,
        "timezone": "America/Los_Angeles",
        "day": date.strftime("%Y-%m-%d"),
        "skill_default": default_skill,
        "skills": SKILLS,
        "safety_weight": SAFETY_WEIGHT,
        "advisory": advisory,
        "routes": routes,
        "data_quality": {
            "tide": "live" if tides_live else "estimated",
            "wind": "live" if wind_live else "estimated",
            "advisory": "live" if adv_live else "unknown",
            "notes": "Estimated sources are modeled fallbacks. Guides make the final call.",
        },
    }


def write_outputs(plan, out_path):
    import os
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)
    csv_path = os.path.join(os.path.dirname(out_path) or ".", "windows.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["route", "status", "skill", "window_start", "window_end"])
        for r in plan["routes"]:
            if not r["windows"]:
                w.writerow([r["id"], r["status"], r["skill"], "", ""])
            for win in r["windows"]:
                w.writerow([r["id"], r["status"], r["skill"], win["start"], win["end"]])
    return out_path, csv_path


def validate(plan):
    assert plan["safety_weight"] == 0.40, "Safety weight must remain 0.40"
    assert isinstance(plan["routes"], list) and plan["routes"], "No routes generated"
    for r in plan["routes"]:
        assert r["status"] in ("green", "yellow", "red"), f"Bad status for {r['id']}"
    return True


def main():
    ap = argparse.ArgumentParser(description="Waterbike AI daily plan generator")
    ap.add_argument("--date", default="today", help="'today' or YYYY-MM-DD")
    ap.add_argument("--skill", default="intermediate", choices=SKILLS)
    ap.add_argument("--out", default="docs/plan.json")
    ap.add_argument("--owm-key", default=None, help="OpenWeatherMap API key (or set OWM_API_KEY)")
    args = ap.parse_args()

    if args.date == "today":
        date = datetime.now(TZ)
    else:
        date = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=TZ)

    import os
    owm_key = args.owm_key or os.environ.get("OWM_API_KEY")

    plan = build_plan(date, owm_key, args.skill)
    validate(plan)
    out, csv_path = write_outputs(plan, args.out)

    live = [k for k, v in plan["data_quality"].items() if v == "live"]
    print(f"plan.json written to {out} ({len(plan['routes'])} routes)")
    print(f"windows.csv written to {csv_path}")
    print(f"data quality: {plan['data_quality']}")
    if not live:
        print("NOTE: all sources fell back to estimates (expected off-network). "
              "In GitHub Actions with network + OWM_API_KEY, live data will populate.")


if __name__ == "__main__":
    main()
