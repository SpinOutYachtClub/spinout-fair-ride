# plan_generator.py - VERSION 8.0 (Rule Engine Integration)
import json
import math
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
import yaml

# --- CONSTANTS AND HELPERS ---
TZ = ZoneInfo("America/Los_Angeles")
P40 = (37.7835, -122.3883); P39 = (37.8087, -122.4098); CLIPPER = (37.8270, -122.3694); TIBURON = (37.8735, -122.4565); CAVALLO = (37.8357, -122.4771)
ROUTES = [{"id":"p40-p39", "name":"Pier 40 to Pier 39", "legs":[(P40, P39), (P39, P40)]},{"id":"p40-clipper", "name":"Pier 40 to Clipper Cove", "legs":[(P40, CLIPPER), (CLIPPER, P40)]},{"id":"p40-tiburon", "name":"Pier 40 to Tiburon", "legs":[(P40, TIBURON), (TIBURON, P40)]},{"id":"p40-cavallo", "name":"Pier 40 to Cavallo Point", "legs":[(P40, CAVALLO), (CAVALLO, P40)]}]
def haversine_miles(a, b): R=3958.761;lat1,lon1=a;lat2,lon2=b;phi1,phi2=math.radians(lat1),math.radians(lat2);dphi=math.radians(lat2-lat1);dl=math.radians(lon2-lon1);x=math.sin(dphi/2)**2+math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2;return 2*R*math.atan2(math.sqrt(x),math.sqrt(1-x))
def route_distance_miles(route): return sum(haversine_miles(a, b) for a, b in route["legs"])

# --- RULE-BASED AND DATA FETCHING FUNCTIONS ---
def load_rules():
    with open('rules.yaml', 'r') as f:
        return yaml.safe_load(f)

def get_weather_forecast():
    api_key=os.getenv("WEATHER_API_KEY");
    if not api_key: print("CRITICAL: WEATHER_API_KEY not found."); return None, None
    url=f"https://api.openweathermap.org/data/3.0/onecall?lat={P40[0]}&lon={P40[1]}&exclude=current,minutely,alerts&appid={api_key}&units=imperial"
    try:
        r=requests.get(url); r.raise_for_status(); data=r.json(); print("Successfully fetched weather data."); return data.get('daily',[]), data.get('hourly',[])
    except requests.exceptions.RequestException as e: print(f"Error fetching weather data: {e}"); return None, None

def calculate_safety_score(trip_data, pod_limits, rules):
    weights = rules['safety_score_weights']
    
    if rules['trip_rules'].get('forbid_small_craft_advisory', False) and trip_data.get('is_small_craft_advisory', False): return 0
    if trip_data['daylight_buffer'] < rules['trip_rules'].get('min_daylight_left_on_return_min', 30): return 0
    if trip_data['wind_gust_mph'] > pod_limits['max_wind_gust']: return 0
    if trip_data['wind_avg_mph'] > pod_limits['max_wind_avg']: return 0

    wind_avg_penalty = (trip_data['wind_avg_mph'] / pod_limits['max_wind_avg']) * 100
    wind_gust_penalty = (trip_data['wind_gust_mph'] / pod_limits['max_wind_gust']) * 100
    current_penalty = (trip_data['adverse_current'] / pod_limits['max_adverse_current_kts']) * 100
    ferry_penalty = 100 if trip_data['has_ferry_conflict'] else 0
    
    total_penalty = (wind_avg_penalty * weights['wind_avg_mph'] +
                     wind_gust_penalty * weights['wind_gust_mph'] +
                     current_penalty * weights['adverse_current_kts'] +
                     ferry_penalty * weights['ferry_conflict'])
                     
    return max(0, 100 - total_penalty)

# --- MAIN SCRIPT ---
def main():
    rules = load_rules()
    daily_forecasts, hourly_forecasts = get_weather_forecast()
    if not daily_forecasts: return

    payload = {"generated_at": datetime.now(TZ).isoformat(), "version": rules.get('version', 'unknown'), "days": []}

    for d, day_forecast in enumerate(daily_forecasts):
        the_date = datetime.fromtimestamp(day_forecast['dt'], tz=TZ).date()
        day_obj = {"date_local": the_date.strftime('%Y-%m-%d'), "recommendations": []}

        for pod_name, pod_limits in rules['pod_levels'].items():
            for route in ROUTES:
                start_time = datetime.fromtimestamp(day_forecast['sunrise'], tz=TZ) + timedelta(hours=1)
                dist = route_distance_miles(route)
                duration = dist / 3.0 # Simplified speed for now
                
                # Check min duration rule if it exists in rules.yaml
                if duration < rules['trip_rules'].get('min_trip_duration_h', 0): continue
                
                end_time = start_time + timedelta(hours=duration)

                trip_data = {}
                hourly_in_window = [h for h in hourly_forecasts if start_time <= datetime.fromtimestamp(h['dt'],tz=TZ) < end_time] if hourly_forecasts else []
                trip_data['wind_avg_mph'] = sum(h.get('wind_speed',0) for h in hourly_in_window) / len(hourly_in_window) if hourly_in_window else day_forecast.get('wind_speed', 0)
                trip_data['wind_gust_mph'] = max((h.get('wind_gust', h.get('wind_speed',0)) for h in hourly_in_window), default=day_forecast.get('wind_gust',0))
                trip_data['daylight_buffer'] = (datetime.fromtimestamp(day_forecast['sunset'],tz=TZ) - end_time).total_seconds() / 60
                trip_data['is_small_craft_advisory'] = trip_data['wind_gust_mph'] > 25
                trip_data['adverse_current'] = 0.0 # Placeholder
                trip_data['has_ferry_conflict'] = False # Placeholder

                score = calculate_safety_score(trip_data, pod_limits, rules)

                badge = "Red"
                if score >= rules['badges']['green_min']: badge = "Green"
                elif score >= rules['badges']['yellow_min']: badge = "Yellow"
                
                rec = {
                    "name": route['name'],
                    "pod_level": pod_name,
                    "start_local": start_time.isoformat(),
                    "end_local": end_time.isoformat(),
                    "safety_score": round(score),
                    "badge": badge,
                    "difficulty": badge, # Let badge determine difficulty for now
                    "conditions": f"Wind {round(trip_data['wind_avg_mph'])} mph, Gusts {round(trip_data['wind_gust_mph'])} mph.",
                }
                day_obj["recommendations"].append(rec)

        payload["days"].append(day_obj)
        
    os.makedirs("docs", exist_ok=True)
    with open("docs/plan.json", "w") as f: json.dump(payload, f, indent=2)
    print("Successfully wrote new plan using full rule engine.")

if __name__ == "__main__":
    main()
