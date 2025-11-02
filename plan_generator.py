# Add these new imports at the top of your file
import os
import requests

# ... (keep your existing imports and constants like P40, TZ, etc.)

def get_weather_forecast():
    """Fetches 8-day weather forecast from OpenWeatherMap."""
    
    # Safely get the API key from GitHub Secrets
    api_key = os.getenv("WEATHER_API_KEY")
    if not api_key:
        print("Error: WEATHER_API_KEY not found in environment variables.")
        return None # Or you could return a default/simulated forecast

    # Use Pier 40's coordinates
    lat, lon = P40
    
    # Construct the API URL
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&exclude=current,minutely,hourly,alerts&appid={api_key}&units=imperial"
    
    try:
        response = requests.get(url)
        # This will raise an exception for bad responses (4xx or 5xx)
        response.raise_for_status() 
        
        weather_data = response.json()
        
        # We only care about the 'daily' forecast part
        return weather_data.get('daily', [])
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching weather data: {e}")
        return None

# --- In your main() function, you will replace the simulated wind ---
# --- values with a call to this new function. ---

def main():
    # --- START of new code for main() ---
    
    print("Fetching real weather forecast...")
    daily_forecasts = get_weather_forecast()

    if not daily_forecasts:
        print("Could not retrieve forecast. Exiting.")
        return # Stop the script if the API call fails
    
    # --- END of new code for main() ---

    rider_preset = "Casual"
    # DELETED: base_speed = 3.0 (this should be defined per-route or rider)
    # DELETED: wind = 10; gust = 15  (we now get this from the API!)
    days_out = 8 # The API provides 8 days of data

    payload = {
        # ... (your payload structure)
    }

    # Now, loop through the REAL forecast data
    # The 'enumerate' function gives us an index 'd' and the 'day_forecast' data
    for d, day_forecast in enumerate(daily_forecasts):
        # The API gives dates in a 'dt' timestamp format, we need to convert it
        the_date = datetime.fromtimestamp(day_forecast['dt'], tz=TZ).date()

        # Extract real wind and gust data!
        # Wind speed from knots to mph is roughly 1.15, but OWM `imperial` gives mph directly
        wind_mph = day_forecast['wind_speed']
        
        # Gusts are not always present, so we use .get() with a fallback
        gust_mph = day_forecast.get('wind_gust', wind_mph) 

        print(f"Processing forecast for {the_date}: Wind={wind_mph:.1f} mph, Gust={gust_mph:.1f} mph")
        
        # ... from here, you continue your loop to build the day_obj,
        # but instead of the old hardcoded wind/gust, you use these new variables.
        # You will also need to convert your logic from knots to mph if necessary.
        
    # ... (rest of your script)

# plan_generator.py
import json, math, os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

try:
    from astral import LocationInfo
    from astral.sun import sun
    HAVE_ASTRAL = True
except ImportError:
    HAVE_ASTRAL = False

TZ = ZoneInfo("America/Los_Angeles")
TODAY = datetime.now(TZ).date()

# Coordinates
P40 = (37.7835, -122.3883)
P39 = (37.8087, -122.4098)
CLIPPER = (37.8270, -122.3694)
TIBURON = (37.8735, -122.4565)
CAVALLO = (37.8357, -122.4771)

ROUTES = [
    {"id":"p40-p39","name":"Pier 40 to Pier 39","stops":["Pier 39"],"legs":[(P40,P39),(P39,P40)],"exposed":False},
    {"id":"p40-clipper","name":"Pier 40 to Clipper Cove","stops":["Clipper Cove"],"legs":[(P40,CLIPPER),(CLIPPER,P40)],"exposed":False},
    {"id":"p40-tiburon","name":"Pier 40 to Tiburon","stops":["Tiburon"],"legs":[(P40,TIBURON),(TIBURON,P40)],"exposed":True},
    {"id":"p40-cavallo","name":"Pier 40 to Cavallo Point","stops":["Cavallo Point"],"legs":[(P40,CAVALLO),(CAVALLO,P40)],"exposed":True},
]

CONFIG = {
    "version": "0.2.1",
    "rider_preset": "Casual",
    "base_speed_mph": 3.0,
    "min_speed_mph": 1.2,
    "days_out": 11,
    "start_time_offset_hours": 1,
    "search_step_minutes": 30,
    "time_step_minutes": 15,
    "min_hours": 2.0,
    "max_hours": 8.0,
    "extend_p40_p39": True,    # set False if you want that route to remain No-Go
    "simulation": {
        "base_wind_kn": 10,    # morning baseline wind
        "dir_deg": 280         # wind comes from the west
    }
}

def haversine_miles(a,b):
    R = 3958.761
    lat1,lon1=a; lat2,lon2=b
    phi1,phi2 = math.radians(lat1),math.radians(lat2)
    dphi = math.radians(lat2-lat1)
    dl = math.radians(lon2-lon1)
    x = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return 2*R*math.atan2(math.sqrt(x), math.sqrt(1-x))

def bearing_deg(a,b):
    lat1,lon1=a; lat2,lon2=b
    phi1,phi2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2-lon1)
    y = math.sin(dlon)*math.cos(phi2)
    x = math.cos(phi1)*math.sin(phi2) - math.sin(phi1)*math.cos(phi2)*math.cos(dlon)
    return (math.degrees(math.atan2(y,x)) + 360) % 360

def wind_diurnal(hour_local:int):
    base = CONFIG["simulation"]["base_wind_kn"]
    if hour_local < 10:
        spd = max(4, base - 2)
    elif hour_local < 14:
        spd = base + 2
    elif hour_local < 17:
        spd = base + 4
    else:
        spd = base
    gust = spd + 5
    direction_from = CONFIG["simulation"]["dir_deg"]
    return spd, gust, direction_from

def wind_components_kn(speed_kn, wind_from_deg, leg_bearing_deg):
    wind_to = (wind_from_deg + 180) % 360
    delta = math.radians(((wind_to - leg_bearing_deg + 540) % 360) - 180)
    head_comp = speed_kn * max(0.0, math.cos(delta))
    cross_comp = speed_kn * abs(math.sin(delta))
    return head_comp, cross_comp

def classify(duration_h, max_gust):
    if max_gust > 25: return "No-Go"
    if duration_h <= 3 and max_gust <= 15: return "Easy"
    if duration_h <= 6 and max_gust <= 20: return "Moderate"
    return "Challenging"

def why_line(route_id, start_dt, max_gust, headwind_avg):
    hour = start_dt.hour
    when = "morning" if hour < 12 else "afternoon"
    if route_id=="p40-clipper":
        return f"Easy; mostly sheltered behind Treasure Island, gusts ≤ {int(max_gust)} kt, {when} timing avoids the breeziest hours."
    if route_id=="p40-tiburon":
        return f"Moderate; cross Bay exposure with average headwind ~{int(round(headwind_avg))} kt, gusts ≤ {int(max_gust)} kt."
    if route_id=="p40-cavallo":
        return f"Moderate; some lee near Raccoon Strait, Golden Gate approach is exposed, gusts ≤ {int(max_gust)} kt."
    return "Not recommended as a stand alone out and back under the two hour minimum."

def day_sun(date):
    if HAVE_ASTRAL:
        loc = LocationInfo("San Francisco","USA","America/Los_Angeles", P40[0], P40[1])
        s = sun(loc.observer, date=date, tzinfo=TZ)
        return s["sunrise"], s["sunset"]
    sunrise = datetime(date.year,date.month,date.day,7,0,tzinfo=TZ)
    sunset  = datetime(date.year,date.month,date.day,17,0,tzinfo=TZ)
    return sunrise, sunset

def simulate_leg_duration_miles(distance_mi, leg_bearing_deg, start_dt, base_speed_mph):
    dt_minutes = CONFIG["time_step_minutes"]
    remaining = distance_mi
    t = 0.0
    max_gust = 0.0
    head_accum = 0.0
    steps = 0
    while remaining > 0:
        hour = (start_dt + timedelta(minutes=t)).hour
        spd_kn, gust_kn, wind_from = wind_diurnal(hour)
        max_gust = max(max_gust, gust_kn)
        head_kn, cross_kn = wind_components_kn(spd_kn, wind_from, leg_bearing_deg)
        penalty = 0.03*head_kn + 0.02*cross_kn
        v_eff = max(CONFIG["min_speed_mph"], base_speed_mph - penalty)
        step_hours = dt_minutes/60.0
        traveled = v_eff * step_hours
        remaining -= traveled
        t += dt_minutes
        head_accum += head_kn
        steps += 1
        if t/60.0 > CONFIG["max_hours"] + 1:
            break
    duration_h = t/60.0
    head_avg = head_accum/max(1, steps)
    return duration_h, max_gust, head_avg

def route_leg_info(route):
    dists, bearings = [], []
    for a,b in route["legs"]:
        dists.append(haversine_miles(a,b))
        bearings.append(bearing_deg(a,b))
    return dists, bearings

def evaluate_window(route, start_dt, sunrise, sunset):
    base = CONFIG["base_speed_mph"]
    dists, bearings = route_leg_info(route)

    duration_total = 0.0
    max_gust_total = 0.0
    head_kn_list = []
    current_start = start_dt

    for di, bi in zip(dists, bearings):
        dur_h, max_gust, head_avg = simulate_leg_duration_miles(di, bi, current_start, base)
        duration_total += dur_h
        max_gust_total = max(max_gust_total, max_gust)
        head_kn_list.append(head_avg)
        current_start = current_start + timedelta(hours=dur_h)

    end_dt = start_dt + timedelta(hours=duration_total)

    if route["id"] == "p40-p39" and CONFIG["extend_p40_p39"] and duration_total < CONFIG["min_hours"]:
        extension_h = min(CONFIG["min_hours"] - duration_total, 0.8)
        duration_total += extension_h
        end_dt = end_dt + timedelta(hours=extension_h)

    if end_dt > sunset:
        return None
    if duration_total < CONFIG["min_hours"] and route["id"] != "p40-p39":
        return None
    if duration_total > CONFIG["max_hours"]:
        return None

    diff = classify(duration_total, max_gust_total)
    head_avg_all = sum(head_kn_list)/len(head_kn_list)
    if route.get("exposed") and head_avg_all > 15 and diff in ("Easy","Moderate"):
        diff = "Moderate" if diff == "Easy" else "Challenging"

    rec = {
        "route_id": route["id"],
        "name": route["name"],
        "stops": route["stops"],
        "start_local": start_dt.isoformat() if diff != "No-Go" else None,
        "end_local": end_dt.isoformat() if diff != "No-Go" else None,
        "duration_hours": round(duration_total, 2) if diff != "No-Go" else 0.0,
        "distance_miles": round(sum(d for d in dists), 2) if diff != "No-Go" else 0.0,
        "difficulty": diff,
        "confidence": "Low",
        "why": why_line(route["id"], start_dt, max_gust_total, head_avg_all),
        "notes": "Simulated time of day winds; replace with real forecasts for higher confidence."
    }
    if diff == "No-Go":
        rec["no_go_reason"] = "Safety veto or daylight window insufficient."
    return rec

def best_window_for_route(route, sunrise, sunset):
    best = None
    start = sunrise + timedelta(hours=CONFIG["start_time_offset_hours"])
    step = timedelta(minutes=CONFIG["search_step_minutes"])
    approx_min_h = 2.0
    latest_start = sunset - timedelta(hours=approx_min_h)

    while start <= latest_start:
        rec = evaluate_window(route, start, sunrise, sunset)
        if rec:
            rank = {"Easy":0,"Moderate":1,"Challenging":2,"No-Go":3}.get(rec["difficulty"], 3)
            key = (rank, rec.get("duration_hours", 99), rec.get("start_local",""))
            if not best or key < best["key"]:
                best = {"rec":rec, "key":key}
        start += step

    if not best and route["id"] == "p40-p39" and not CONFIG["extend_p40_p39"]:
        return {
            "route_id": route["id"],
            "name": route["name"],
            "stops": route["stops"],
            "difficulty": "No-Go",
            "confidence": "Low",
            "why": "Not recommended as a stand alone out and back under the two hour minimum.",
            "no_go_reason": "Too short under current rules; consider a Harbor Loop extension.",
            "notes": "Administrative rule, not a weather veto."
        }
    return best["rec"] if best else None

def main():
    payload = {
        "generated_at": datetime.now(TZ).isoformat(),
        "timezone": "America/Los_Angeles",
        "rider_preset": CONFIG["rider_preset"],
        "version": CONFIG["version"],
        "days": [],
        "disclaimer": "Advisory only. Conditions change on the water. Final go or no-go is made on site by the captain."
    }

    for d in range(CONFIG["days_out"]):
        the_date = TODAY + timedelta(days=d)
        sunrise, sunset = day_sun(the_date)
        day_obj = {
            "date_local": the_date.isoformat(),
            "sunrise": sunrise.isoformat(),
            "sunset": sunset.isoformat(),
            "recommendations": []
        }
        for r in ROUTES:
            rec = best_window_for_route(r, sunrise, sunset)
            if not rec:
                rec = {
                    "route_id": r["id"],
                    "name": r["name"],
                    "stops": r["stops"],
                    "difficulty": "No-Go",
                    "confidence": "Low",
                    "why": "No safe or valid window within daylight.",
                    "no_go_reason": "All candidate times exceeded daylight or duration limits.",
                    "notes": "Simulated winds only."
                }
            day_obj["recommendations"].append(rec)
        payload["days"].append(day_obj)

    os.makedirs("docs", exist_ok=True)
    with open("docs/plan.json","w") as f:
        json.dump(payload, f, indent=2)

if __name__ == "__main__":
    main()
