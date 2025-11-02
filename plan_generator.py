# plan_generator.py - VERSION 7.1 (ECHO fix: tz handling + currents direction)
import json
import math
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests

# --- CONSTANTS ---
TZ = ZoneInfo("America/Los_Angeles")

P40 = (37.7835, -122.3883)
P39 = (37.8087, -122.4098)
CLIPPER = (37.8270, -122.3694)
TIBURON = (37.8735, -122.4565)
CAVALLO = (37.8357, -122.4771)

ROUTES = [
    {"id": "p40-p39", "name": "Pier 40 to Pier 39", "stops": ["Pier 39"], "legs": [(P40, P39), (P39, P40)]},
    {"id": "p40-clipper", "name": "Pier 40 to Clipper Cove", "stops": ["Clipper Cove"], "legs": [(P40, CLIPPER), (CLIPPER, P40)]},
    {"id": "p40-tiburon", "name": "Pier 40 to Tiburon", "stops": ["Tiburon"], "legs": [(P40, TIBURON), (TIBURON, P40)]},
    {"id": "p40-cavallo", "name": "Pier 40 to Cavallo Point", "stops": ["Cavallo Point"], "legs": [(P40, CAVALLO), (CAVALLO, P40)]},
]

NOAA_TIDE_STATION = "9414290"
NOAA_CURRENT_STATION = "SFB1201"

# --- HELPERS ---
def haversine_miles(a, b):
    R = 3958.761
    lat1, lon1 = a
    lat2, lon2 = b
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(x), math.sqrt(1 - x))

def route_distance_miles(route):
    return sum(haversine_miles(a, b) for a, b in route["legs"])

def classify(duration_hours, gust_mph):
    if gust_mph > 28:
        return "No-Go"
    if duration_hours <= 3 and gust_mph <= 17:
        return "Easy"
    if duration_hours <= 6 and gust_mph <= 23:
        return "Moderate"
    return "Challenging"

# --- DATA FETCH ---
def get_weather_forecast():
    api_key = os.getenv("WEATHER_API_KEY")
    if not api_key:
        print("CRITICAL: WEATHER_API_KEY not found.")
        return None, None
    url = (
        f"https://api.openweathermap.org/data/3.0/onecall"
        f"?lat={P40[0]}&lon={P40[1]}&exclude=current,minutely,alerts"
        f"&appid={api_key}&units=imperial"
    )
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
        print("Successfully fetched weather data.")
        return data.get("daily", []), data.get("hourly", [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching weather data: {e}")
        return None, None

def get_noaa_predictions(station, product, date_str):
    params = {
        "station": station,
        "product": product,
        "datum": "MLLW",
        "units": "english",            # knots for currents, feet for tides
        "time_zone": "lst_ldt",
        "format": "json",
        "application": "SpinoutFairRide",
        "begin_date": date_str,
        "range": "168"                 # 7 days
    }
    if product == "predictions":
        # High/Low events so entries include 'type' = 'H'/'L'
        params["interval"] = "hilo"

    url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    headers = {"User-Agent": "SpinoutFairRide/1.0 (https://github.com/SpinOutYachtClub/spinout-fair-ride)"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        print(f"INFO: Could not fetch NOAA {product} for {station}. Error: {e}")
        return None

# --- MAIN ---
def main():
    daily_forecasts, hourly_forecasts = get_weather_forecast()
    if not daily_forecasts:
        print("Exiting due to weather API failure.")
        return

    today_str = datetime.now(TZ).strftime("%Y%m%d")
    tide_data = get_noaa_predictions(NOAA_TIDE_STATION, "predictions", today_str)
    current_data = get_noaa_predictions(NOAA_CURRENT_STATION, "currents_predictions", today_str)

    payload = {
        "generated_at": datetime.now(TZ).isoformat(),
        "rider_preset": "Casual",
        "version": "7.1.0-echo-fix",
        "days": [],
        "disclaimer": "Advisory only. Verify local conditions and official guidance before going out."
    }

    for d, day_forecast in enumerate(daily_forecasts):
        the_date = datetime.fromtimestamp(day_forecast["dt"], tz=TZ).date()
        day_obj = {"date_local": the_date.strftime("%Y-%m-%d"), "recommendations": []}

        start_time = datetime.fromtimestamp(day_forecast["sunrise"], tz=TZ) + timedelta(hours=1)

        for r in ROUTES:
            dist = route_distance_miles(r)
            duration = dist / 2.7  # mph
            end_time = start_time + timedelta(hours=duration)

            # Wind window
            hourly_in_window = [
                h for h in (hourly_forecasts or [])
                if start_time <= datetime.fromtimestamp(h["dt"], tz=TZ) < end_time
            ]
            max_gust = max((h.get("wind_gust", h.get("wind_speed", 0)) for h in hourly_in_window),
                           default=day_forecast.get("wind_gust", 0))
            wind_speeds = [h.get("wind_speed", 0) for h in hourly_in_window] or [day_forecast.get("wind_speed", 0)]
            wind_range = f"{round(min(wind_speeds))}-{round(max(wind_speeds))}"

            tide_summary, current_summary = "", ""

            # --- TIDES: use hilo events, attach TZ rather than astimezone on naive ---
            try:
                if tide_data and "predictions" in tide_data:
                    events_in_window = []
                    for p in tide_data["predictions"]:
                        if "t" not in p:
                            continue
                        dt_local = datetime.strptime(p["t"], "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
                        if start_time <= dt_local < end_time:
                            events_in_window.append(p)
                    tide_summary = ", ".join(
                        f"{'High' if e.get('type') == 'H' else 'Low'} at "
                        f"{datetime.strptime(e['t'], '%Y-%m-%d %H:%M').strftime('%-I:%M%p')}"
                        for e in events_in_window if "type" in e
                    )
            except Exception as e:
                print(f"WARN: Handled a tide parsing error: {e}")

            # --- CURRENTS: choose first non-zero speed for Flood/Ebb, else Slack ---
            try:
                if current_data and "data" in current_data:
                    points = []
                    for p in current_data["data"]:
                        if "t" not in p or "s" not in p:
                            continue
                        dt_local = datetime.strptime(p["t"], "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
                        if start_time <= dt_local < end_time:
                            points.append(p)

                    if points:
                        speeds = [float(p["s"]) for p in points if "s" in p]
                        if speeds:
                            min_c = min(speeds)
                            max_c = max(speeds)
                            # pick first non-zero to infer direction
                            first_nonzero = next((s for s in speeds if abs(s) >= 0.05), 0.0)
                            if first_nonzero > 0:
                                direction = "Flood"
                            elif first_nonzero < 0:
                                direction = "Ebb"
                            else:
                                direction = "Slack"
                            current_summary = f"{direction} {abs(min_c):.1f}-{abs(max_c):.1f} kts"
            except Exception as e:
                print(f"WARN: Handled a current parsing error: {e}")

            rec = {
                "route_id": r["id"],
                "name": r["name"],
                "start_local": start_time.isoformat(),
                "end_local": end_time.isoformat(),
                "duration_hours": round(duration, 1),
                "distance_miles": round(dist, 1),
                "difficulty": classify(duration, max_gust),
                "confidence": "High" if d < 3 else "Medium",
                "wind_range": wind_range,
                "tide_summary": tide_summary,
                "current_summary": current_summary,
                "notes": f"Max gusts to {max_gust:.1f} mph."
            }

            if r["id"] == "p40-p39":
                rec.update({
                    "difficulty": "No-Go",
                    "duration_hours": 0.0,
                    "distance_miles": round(dist, 1),
                    "no_go_reason": "Route too short."
                })

            day_obj["recommendations"].append(rec)

        payload["days"].append(day_obj)

    os.makedirs("docs", exist_ok=True)
    with open("docs/plan.json", "w") as f:
        json.dump(payload, f, indent=2)
    print("Successfully wrote new plan with ECHO v7.1 fix.")

if __name__ == "__main__":
    main()
