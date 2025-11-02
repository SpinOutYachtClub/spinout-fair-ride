# plan_generator.py - VERSION 2.1 (with hourly wind data)
import json
import math
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests

# --- CONSTANTS ---
TZ = ZoneInfo("America/Los_Angeles")
P40 = (37.7835, -122.3883)
# ... (rest of your constants and ROUTES list remain the same) ...
P39 = (37.8087, -122.4098)
CLIPPER = (37.8270, -122.3694)
TIBURON = (37.8735, -122.4565)
CAVALLO = (37.8357, -122.4771)

ROUTES = [
    {"id":"p40-p39", "name":"Pier 40 to Pier 39", "stops":["Pier 39"], "legs":[(P40, P39), (P39, P40)]},
    {"id":"p40-clipper", "name":"Pier 40 to Clipper Cove", "stops":["Clipper Cove"], "legs":[(P40, CLIPPER), (CLIPPER, P40)]},
    {"id":"p40-tiburon", "name":"Pier 40 to Tiburon", "stops":["Tiburon"], "legs":[(P40, TIBURON), (TIBURON, P40)]},
    {"id":"p40-cavallo", "name":"Pier 40 to Cavallo Point", "stops":["Cavallo Point"], "legs":[(P40, CAVALLO), (CAVALLO, P40)]},
]
# --- HELPER FUNCTIONS ---
# ... (haversine_miles, route_distance_miles, classify, why_line remain the same) ...
def haversine_miles(a, b):
    R = 3958.761; lat1, lon1 = a; lat2, lon2 = b; phi1, phi2 = math.radians(lat1), math.radians(lat2); dphi = math.radians(lat2 - lat1); dl = math.radians(lon2 - lon1); x = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl/2)**2; return 2 * R * math.atan2(math.sqrt(x), math.sqrt(1 - x))
def route_distance_miles(route):
    return sum(haversine_miles(a, b) for a, b in route["legs"])
def classify(duration_hours, gust_mph):
    if gust_mph > 28: return "No-Go";
    if duration_hours <= 3 and gust_mph <= 17: return "Easy";
    if duration_hours <= 6 and gust_mph <= 23: return "Moderate";
    return "Challenging"
def why_line(route_id, difficulty, gust_mph):
    gust_kt = round(gust_mph / 1.15);
    if route_id == "p40-p39": return "Not recommended as a stand-alone out-and-back because it does not meet the two hour minimum under current club rules."
    if route_id == "p40-clipper": return f"Easy; mostly sheltered behind Treasure Island, gusts ≤ {gust_kt} kt, and the round trip is under 3 hours."
    if route_id == "p40-tiburon": return f"Moderate; the route is exposed across the Central Bay, but gusts are manageable at ≤ {gust_kt} kt."
    if route_id == "p40-cavallo": return f"Moderate; Raccoon Strait gives some lee but the approach to the Golden Gate is exposed; gusts are manageable at ≤ {gust_kt} kt."
    return "General recommendation based on forecast."

# --- WEATHER API FUNCTION ---
def get_weather_forecast():
    """Fetches 8-day daily and 2-day hourly forecast from OpenWeatherMap."""
    api_key = os.getenv("WEATHER_API_KEY")
    if not api_key:
        print("CRITICAL: WEATHER_API_KEY secret not found.")
        return None, None
    
    lat, lon = P40
    # UPDATED URL: We now EXCLUDE only 'current' and 'minutely' to get the HOURLY data
    url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&exclude=current,minutely,alerts&appid={api_key}&units=imperial"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        weather_data = response.json()
        print(f"Successfully fetched weather data.")
        return weather_data.get('daily', []), weather_data.get('hourly', [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching weather data: {e}")
        return None, None

# --- MAIN SCRIPT EXECUTION ---
def main():
    rider_preset = "Casual"; base_speed_mph = 3.0; wind_penalty_mph = 0.3
    
    daily_forecasts, hourly_forecasts = get_weather_forecast()

    if not daily_forecasts:
        print("Could not retrieve forecast. Exiting."); return

    payload = {"generated_at": datetime.now(TZ).isoformat(), "timezone": "America/Los_Angeles", "rider_preset": rider_preset, "version": "0.4.0-hourly-wind", "days": [], "disclaimer": "Advisory only..."}

    for d, day_forecast in enumerate(daily_forecasts):
        the_date = datetime.fromtimestamp(day_forecast['dt'], tz=TZ)
        sunrise = datetime.fromtimestamp(day_forecast['sunrise'], tz=TZ)
        sunset = datetime.fromtimestamp(day_forecast['sunset'], tz=TZ)
        
        day_obj = {"date_local": the_date.strftime('%Y-%m-%d'), "sunrise": sunrise.isoformat(), "sunset": sunset.isoformat(), "recommendations": []}
        
        start_time = sunrise + timedelta(hours=1)
        
        for r in ROUTES:
            dist = route_distance_miles(r)
            veff = max(1.2, base_speed_mph - wind_penalty_mph)
            duration = dist / veff
            end_time = start_time + timedelta(hours=duration)
            
            # --- NEW HOURLY LOGIC ---
            max_gust_in_window = 0
            wind_speeds_in_window = []

            # Filter for hourly forecasts that fall within our trip window
            if hourly_forecasts:
                for hour_forecast in hourly_forecasts:
                    hour_dt = datetime.fromtimestamp(hour_forecast['dt'], tz=TZ)
                    if start_time <= hour_dt < end_time:
                        wind_speeds_in_window.append(hour_forecast.get('wind_speed', 0))
                        max_gust_in_window = max(max_gust_in_window, hour_forecast.get('wind_gust', hour_forecast.get('wind_speed', 0)))

            # Fallback to daily gust if window is outside hourly data range (e.g., >2 days out)
            if not wind_speeds_in_window:
                max_gust_in_window = day_forecast.get('wind_gust', day_forecast.get('wind_speed', 0))
                min_wind = max_wind = day_forecast.get('wind_speed', 0)
            else:
                min_wind = min(wind_speeds_in_window)
                max_wind = max(wind_speeds_in_window)

            wind_range_str = f"{round(min_wind)}-{round(max_wind)}"
            # --- END NEW LOGIC ---

            diff = classify(duration, max_gust_in_window)
            confidence = "High" if d < 2 else "Medium" if d < 5 else "Low"

            rec = {
                "route_id": r["id"], "name": r["name"], "stops": r["stops"],
                "start_local": start_time.isoformat(), "end_local": end_time.isoformat(),
                "duration_hours": round(duration, 2), "distance_miles": round(dist, 2),
                "difficulty": diff, "confidence": confidence, "why": why_line(r["id"], diff, max_gust_in_window),
                "wind_range": wind_range_str, # Add new data field
                "notes": f"Max gusts to {max_gust_in_window:.1f} mph."
            }
            if r["id"] == "p40-p39": # Handle No-Go case separately
                rec.update({"difficulty": "No-Go", "duration_hours": 0.0, "distance_miles": 0.0, "no_go_reason": "Route too short to meet two-hour minimum."})

            day_obj["recommendations"].append(rec)
        payload["days"].append(day_obj)
        start_time += timedelta(days=1) # Increment start day for the next loop

    os.makedirs("docs", exist_ok=True)
    with open("docs/plan.json", "w") as f: json.dump(payload, f, indent=2)
    print("Successfully wrote new plan with hourly wind data.")

if __name__ == "__main__":
    main()
