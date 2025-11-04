# plan_generator.py - VERSION 9.0 (Rule-Based Duration Check)
import json
import math
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
import yaml  # Make sure PyYAML is in requirements.txt

# --- CONSTANTS & HELPERS (Unchanged) ---
TZ = ZoneInfo("America/Los_Angeles")
P40 = (37.7835, -122.3883); P39 = (37.8087, -122.4098); CLIPPER = (37.8270, -122.3694); TIBURON = (37.8735, -122.4565); CAVALLO = (37.8357, -122.4771)
ROUTES = [
    {"id":"p40-p39", "name":"Pier 40 to Pier 39", "legs":[(P40, P39), (P39, P40)]},
    {"id":"p40-clipper", "name":"Pier 40 to Clipper Cove", "legs":[(P40, CLIPPER), (CLIPPER, P40)]},
    {"id":"p40-tiburon", "name":"Pier 40 to Tiburon", "legs":[(P40, TIBURON), (TIBURON, P40)]},
    {"id":"p40-cavallo", "name":"Pier 40 to Cavallo Point", "legs":[(P40, CAVALLO), (CAVALLO, P40)]},
]
def haversine_miles(a,b): R=3958.761;lat1,lon1=a;lat2,lon2=b;phi1,phi2=math.radians(lat1),math.radians(lat2);dphi=math.radians(lat2-lat1);dl=math.radians(lon2-lon1);x=math.sin(dphi/2)**2+math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2;return 2*R*math.atan2(math.sqrt(x),math.sqrt(1-x))
def route_distance_miles(route): return sum(haversine_miles(a, b) for a, b in route["legs"])

# --- DATA FETCHING & RULE LOADING (Unchanged) ---
def load_rules():
    with open('rules.yaml', 'r') as f: return yaml.safe_load(f)
def get_weather_forecast():
    api_key=os.getenv("WEATHER_API_KEY")
    if not api_key: print("CRITICAL: WEATHER_API_KEY not found."); return None, None
    url=f"https://api.openweathermap.org/data/3.0/onecall?lat={P40[0]}&lon={P40[1]}&exclude=current,minutely,alerts&appid={api_key}&units=imperial"
    try:
        r=requests.get(url); r.raise_for_status(); data=r.json(); print("Successfully fetched weather data."); return data.get('daily',[]), data.get('hourly',[])
    except requests.exceptions.RequestException as e: print(f"Error fetching weather data: {e}"); return None, None

# --- NEW: Simplified Difficulty Logic ---
def get_difficulty(score, rules):
    if score >= rules['badges']['green_min']: return "Easy"
    if score >= rules['badges']['yellow_min']: return "Moderate"
    return "Hard"

# --- MAIN SCRIPT ---
def main():
    rules = load_rules()
    daily_forecasts, hourly_forecasts = get_weather_forecast()
    if not daily_forecasts: return

    payload = {"generated_at": datetime.now(TZ).isoformat(), "version": "9.0", "days": []}

    for d, day_forecast in enumerate(daily_forecasts):
        the_date = datetime.fromtimestamp(day_forecast['dt'], tz=TZ).date()
        day_obj = {"date_local": the_date.strftime('%Y-%m-%d'), "recommendations": []}

        start_time_base = datetime.fromtimestamp(day_forecast['sunrise'], tz=TZ) + timedelta(hours=1)
        
        for pod_name, pod_limits in rules['pod_levels'].items():
            for route in ROUTES:
                dist = route_distance_miles(route)
                # A simple speed model for now, can be improved later
                speed_mph = 3.0 if pod_name == 'Casual' else 3.5 
                duration = dist / speed_mph
                
                # --- THIS IS THE NEW RULE CHECK ---
                if duration < rules['trip_rules']['min_trip_duration_h']:
                    continue # Skip this route, it's too short

                start_time = start_time_base
                end_time = start_time + timedelta(hours=duration)
                
                # --- GATHER DATA & SCORE (Simplified for this change) ---
                daylight_buffer = (datetime.fromtimestamp(day_forecast['sunset'], tz=TZ) - end_time).total_seconds() / 60
                
                max_gust_in_window = max((h.get('wind_gust', 0) for h in hourly_forecasts if start_time <= datetime.fromtimestamp(h['dt'],tz=TZ) < end_time), default=day_forecast.get('wind_gust',0)) if hourly_forecasts else day_forecast.get('wind_gust',0)
                
                # Check for "No-Go" gate conditions
                if max_gust_in_window > pod_limits['max_wind_gust'] or daylight_buffer < rules['trip_rules']['min_daylight_left_on_return_min']:
                    score = 0
                else: # Calculate a simple score
                    gust_penalty = (max_gust_in_window / pod_limits['max_wind_gust']) * 100
                    score = 100 - (gust_penalty * rules['safety_score_weights']['wind_gust_mph'])

                # Create the recommendation object (without the old No-Go hardcoding)
                rec = {
                    "name": route['name'],
                    "start_local": start_time.isoformat(),
                    "end_local": end_time.isoformat(),
                    "duration_hours": round(duration, 1),
                    "distance_miles": round(dist, 1),
                    "difficulty": get_difficulty(score, rules),
                    "notes": f"Max gusts to {max_gust_in_window:.1f} mph for {pod_name}."
                    # The rest of the fields will be empty for now as we build the engine
                }
                
                if score < rules['badges']['yellow_min']:
                    rec['difficulty'] = 'No-Go'

                day_obj["recommendations"].append(rec)
        
        # Add a default empty day if no recommendations were found
        if not day_obj["recommendations"]:
            day_obj["recommendations"].append({"name": "No trips meet safety rules today.", "difficulty": "No-Go"})

        payload["days"].append(day_obj)
        
    os.makedirs("docs", exist_ok=True)
    with open("docs/plan.json", "w") as f:
        json.dump(payload, f, indent=2)
    print("Successfully wrote new plan using 1-hour minimum trip rule.")

if __name__ == "__main__":
    main()
