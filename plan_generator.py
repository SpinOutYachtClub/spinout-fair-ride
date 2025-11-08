# plan_generator.py - VERSION 12.2 (KeyError Fix)
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
SFYH = (37.8070, -122.4430)
AQ_PARK = (37.8081, -122.4223)
TORPEDO = (37.8285, -122.4645)
CRANE_COVE = (37.7687, -122.3855)
BRISBANE = (37.6833, -122.3787)
JACK_LONDON = (37.7950, -122.2709)
BROOKLYN = (37.7892, -122.2575)
BERKELEY = (37.8631, -122.3168)
SCHOONMAKER = (37.8546, -122.4764)

# --- THIS IS THE FIX: Explicitly define legs for clarity and robustness ---
ROUTES = [
    # The original Pier 39 route, now marked as a 'no-go' intentionally.
    # We can even remove this later if we don't want to show it at all.
    {"id":"p40-p39-short", "name":"Pier 40 to Pier 39 (Direct)", "legs":[(P40, P39)]},
    
    # --- NEW HARBOR LOOP VERSION ---
    # Note the new 'id' and 'name'. The 'bonus_miles' is a special key we'll use.
    {"id":"p40-p39-loop", "name":"Pier 40 to Pier 39 (Harbor Loop)", "legs":[(P40, P39)], "bonus_miles": 1.5},
    {"id":"p40-clipper", "name":"Pier 40 to Clipper Cove", "legs":[(P40, CLIPPER)]},
    {"id":"p40-tiburon", "name":"Pier 40 to Tiburon", "legs":[(P40, TIBURON)]},
    {"id":"p40-cavallo", "name":"Pier 40 to Cavallo Point", "legs":[(P40, CAVALLO)]},
    {"id":"p40-sfyh", "name":"Pier 40 to San Francisco Yacht Harbor", "legs":[(P40, SFYH)]},
    {"id":"p40-aqpark", "name":"Pier 40 to San Francisco Aquatic Park", "legs":[(P40, AQ_PARK)]},
    {"id":"p40-torpedo", "name":"Pier 40 to Torpedo Warf", "legs":[(P40, TORPEDO)]},
    {"id":"p40-cranecove", "name":"Pier 40 to Crane Cove Park", "legs":[(P40, CRANE_COVE)]},
    {"id":"p40-brisbane", "name":"Pier 40 to Brisbane Marina", "legs":[(P40, BRISBANE)]},
    {"id":"p40-jacklondon", "name":"Pier 40 to Jack London Square Marina", "legs":[(P40, JACK_LONDON)]},
    {"id":"p40-brooklyn", "name":"Pier 40 to Brooklyn Basin", "legs":[(P40, BROOKLYN)]},
    {"id":"p40-berkeley", "name":"Pier 40 to Berkeley Marina", "legs":[(P40, BERKELEY)]},
    {"id":"p40-schoonmaker", "name":"Pier 40 to Schoonmaker Beach", "legs":[(P40, SCHOONMAKER)]},
]
NOAA_TIDE_STATION="9414290"; NOAA_CURRENT_STATION="SFB1201"
ROUTE_BEARINGS = {"p40-p39":350,"p40-clipper":20,"p40-tiburon":330,"p40-cavallo":320,"p40-sfyh":325,"p40-aqpark":335,"p40-torpedo":320,"p40-cranecove":170,"p40-brisbane":160,"p40-jacklondon":50,"p40-brooklyn":60,"p40-berkeley":10,"p40-schoonmaker":320}
EBB_BEARING = 240; FLOOD_BEARING = 60

# --- HELPER FUNCTIONS ---
def haversine_miles(a,b):
    R=3958.761;lat1,lon1=a;lat2,lon2=b;phi1,phi2=math.radians(lat1),math.radians(lat2);dphi=math.radians(lat2-lat1);dl=math.radians(lon2-lon1);x=math.sin(dphi/2)**2+math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2;return 2*R*math.atan2(math.sqrt(x),math.sqrt(1-x))
def route_distance_miles(route): return sum(haversine_miles(a, b) for a, b in route["legs"]) * 2
def classify(duration_hours, gust_mph):
    if gust_mph > 28: return "No-Go";
    if duration_hours <= 3 and gust_mph <= 17: return "Easy";
    if duration_hours <= 6 and gust_mph <= 23: return "Moderate";
    return "Challenging"

# --- DATA FETCHING ---
def get_weather_forecast():
    api_key=os.getenv("WEATHER_API_KEY");
    if not api_key: print("CRITICAL: WEATHER_API_KEY not found."); return None, None
    url=f"https://api.openweathermap.org/data/3.0/onecall?lat={P40[0]}&lon={P40[1]}&exclude=current,minutely,alerts&appid={api_key}&units=imperial"
    try:
        r=requests.get(url); r.raise_for_status(); data=r.json(); print("OK: Fetched weather"); return data.get('daily',[]), data.get('hourly',[])
    except requests.exceptions.RequestException as e: print(f"ERROR: Fetching weather: {e}"); return None, None

def get_noaa_predictions(station, product):
    today_str = datetime.now(TZ).strftime('%Y%m%d')
    params = {"date": "today", "station": station, "product": product, "datum": "MLLW", "units": "english", "time_zone": "lst_ldt", "format": "json", "application": "SpinoutFairRide", "begin_date": today_str, "range": "168"}
    if product == "predictions": params["interval"] = "hilo"
    url = f"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"; headers = {'User-Agent': 'SpinoutFairRide/1.0 (https://github.com/SpinOutYachtClub/spinout-fair-ride)'}
    try:
        r = requests.get(url, params=params, headers=headers); r.raise_for_status(); data=r.json(); print(f"OK: Fetched NOAA {product}"); return data
    except requests.exceptions.RequestException as e: print(f"ERROR: Fetching NOAA {product}: {e}"); return None

# --- MAIN SCRIPT ---
def main():
    daily_forecasts, hourly_forecasts = get_weather_forecast()
    if not daily_forecasts: return
    tide_data = get_noaa_predictions(NOAA_TIDE_STATION, "predictions"); current_data = get_noaa_predictions(NOAA_CURRENT_STATION, "currents_predictions")
    payload = {"generated_at": datetime.now(TZ).isoformat(), "rider_preset": "Casual", "version": "12.2.0-key-fix", "days": []}

    for d, day_forecast in enumerate(daily_forecasts):
        the_date = datetime.fromtimestamp(day_forecast['dt'], tz=TZ).date()
        day_obj = {"date_local": the_date.strftime('%Y-%m-%d'), "recommendations": []}; start_time = datetime.fromtimestamp(day_forecast['sunrise'], tz=TZ) + timedelta(hours=1)
        todays_tide_events = [p for p in tide_data.get('predictions', []) if 't' in p and datetime.strptime(p['t'], '%Y-%m-%d %H:%M').date() == the_date] if tide_data else []
        all_currents_today = [p for p in current_data.get('data',[]) if 't' in p and 's' in p and datetime.strptime(p['t'], '%Y-%m-%d %H:%M').date() == the_date] if current_data else []
        for r in ROUTES:
            dist = route_distance_miles(r) + r.get("bonus_miles", 0); duration = dist / 2.7; end_time = start_time + timedelta(hours=duration)
            hourly_in_window = [h for h in hourly_forecasts if start_time <= datetime.fromtimestamp(h['dt'],tz=TZ) < end_time] if hourly_forecasts else []
            max_gust = max((h.get('wind_gust', h.get('wind_speed', 0)) for h in hourly_in_window), default=day_forecast.get('wind_gust',0))
            wind_speeds = [h.get('wind_speed',0) for h in hourly_in_window] or [day_forecast.get('wind_speed',0)]; wind_range = f"{round(min(wind_speeds))}-{round(max(wind_speeds))}"
            tide_summary, current_summary, current_effect = "N/A", "N/A", "N/A"
            try:
                if all_currents_today:
                    departure_current = min(all_currents_today, key=lambda p: abs(datetime.strptime(p['t'], '%Y-%m-%d %H:%M').astimezone(TZ) - start_time))
                    departure_speed = float(departure_current['s']); direction = "Flood" if departure_speed > 0 else "Ebb"
                    currents_in_window = [p for p in all_currents_today if start_time <= datetime.strptime(p['t'], '%Y-%m-%d %H:%M').astimezone(TZ) < end_time]
                    if duration > 1.0 and currents_in_window:
                        min_c=min(float(p['s']) for p in currents_in_window); max_c=max(float(p['s']) for p in currents_in_window); current_summary = f"{direction} {abs(min_c):.1f}-{abs(max_c):.1f} kts"
                    else: current_summary = f"{direction} {abs(departure_speed):.1f} kts"
                    route_bearing = ROUTE_BEARINGS.get(r['id']); current_bearing = FLOOD_BEARING if direction == "Flood" else EBB_BEARING
                    if route_bearing is not None:
                        angle_diff = abs((route_bearing - current_bearing + 180) % 360 - 180)
                        if angle_diff < 45: current_effect = "Fair"
                        elif angle_diff > 135: current_effect = "Foul"
                        else: current_effect = "Cross"
                if todays_tide_events:
                     events_in_window = [p for p in todays_tide_events if start_time <= datetime.strptime(p['t'], '%Y-%m-%d %H:%M').astimezone(TZ) < end_time]
                     tide_summary = ", ".join([f"{p['type']} @ {datetime.strptime(p['t'], '%Y-%m-%d %H:%M').strftime('%-I:%M%p')}" for p in events_in_window]) or ""
            except Exception as e: print(f"WARN: Handled a parsing error: {e}")

            rec = {"route_id": r["id"], "name": r["name"], "start_local": start_time.isoformat(), "end_local": end_time.isoformat(), "duration_hours": round(duration, 1), "distance_miles": round(dist, 1), "difficulty": classify(duration, max_gust), "confidence": "High" if d < 3 else "Medium", "wind_range": wind_range, "tide_summary": tide_summary, "current_summary": current_summary, "current_effect": current_effect}
            if r["name"] == "Pier 40 to Pier 39 (Direct)": rec.update({"difficulty": "No-Go", "duration_hours": 0.0, "distance_miles": round(dist, 1), "no_go_reason": "Route too short.", "current_summary":"N/A", "current_effect":"N/A"})
            day_obj["recommendations"].append(rec)
        payload["days"].append(day_obj)
    
    PUBLISH_DIR = os.getenv("PUBLISH_DIR", "docs"); os.makedirs(PUBLISH_DIR or ".", exist_ok=True); out_path = os.path.join(PUBLISH_DIR, "plan.json") if PUBLISH_DIR else "plan.json"
    with open(out_path, "w", encoding="utf-8") as f: json.dump(payload, f, indent=2)
    print(f"Successfully published to {out_path}")

if __name__ == "__main__":
    main()
