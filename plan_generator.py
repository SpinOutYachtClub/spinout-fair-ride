# plan_generator.py - VERSION 10.0 (Per-Leg Data Engine)
import json
import math
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
import yaml

# --- CONSTANTS & HELPERS ---
TZ = ZoneInfo("America/Los_Angeles")
# NEW: Coordinate to Name mapping for clear leg descriptions
COORD_TO_NAME = {
    (37.7835, -122.3883): "Pier 40",
    (37.8087, -122.4098): "Pier 39",
    (37.8270, -122.3694): "Clipper Cove",
    (37.8735, -122.4565): "Tiburon",
    (37.8357, -122.4771): "Cavallo Point"
}
# (The rest of your constants and helpers remain the same)
P40 = (37.7835, -122.3883); P39 = (37.8087, -122.4098); CLIPPER = (37.8270, -122.3694); TIBURON = (37.8735, -122.4565); CAVALLO = (37.8357, -122.4771)
ROUTES = [
    {"id":"p40-p39", "name":"Pier 40 to Pier 39", "legs":[(P40, P39), (P39, P40)]},
    {"id":"p40-clipper", "name":"Pier 40 to Clipper Cove", "legs":[(P40, CLIPPER), (CLIPPER, P40)]},
    {"id":"p40-tiburon", "name":"Pier 40 to Tiburon", "legs":[(P40, TIBURON), (TIBURON, P40)]},
    {"id":"p40-cavallo", "name":"Pier 40 to Cavallo Point", "legs":[(P40, CAVALLO), (CAVALLO, P40)]},
]
NOAA_TIDE_STATION = "9414290"; NOAA_CURRENT_STATION = "SFB1201"
def haversine_miles(a,b): R=3958.761;lat1,lon1=a;lat2,lon2=b;phi1,phi2=math.radians(lat1),math.radians(lat2);dphi=math.radians(lat2-lat1);dl=math.radians(lon2-lon1);x=math.sin(dphi/2)**2+math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2;return 2*R*math.atan2(math.sqrt(x),math.sqrt(1-x))
def route_distance_miles(route): return sum(haversine_miles(a, b) for a, b in route["legs"])
def classify(duration_hours, gust_mph):
    if gust_mph > 28: return "No-Go"
    if duration_hours <= 3 and gust_mph <= 17: return "Easy"
    if duration_hours <= 6 and gust_mph <= 23: return "Moderate"
    return "Challenging"
def get_weather_forecast():
    # Unchanged
    pass
def get_noaa_predictions(station, product):
    # Unchanged
    pass

# --- MAIN SCRIPT (Now builds the 'legs' array) ---
def main():
    daily_forecasts, hourly_forecasts = get_weather_forecast()
    if not daily_forecasts: return

    today_str = datetime.now(TZ).strftime('%Y%m%d')
    tide_data = get_noaa_predictions(NOAA_TIDE_STATION, "predictions")
    current_data = get_noaa_predictions(NOAA_CURRENT_STATION, "currents_predictions")
    
    payload = {"generated_at": datetime.now(TZ).isoformat(), "version": "10.0-legs", "days": []}

    for d, day_forecast in enumerate(daily_forecasts):
        the_date = datetime.fromtimestamp(day_forecast['dt'], tz=TZ).date()
        day_obj = {"date_local": the_date.strftime('%Y-%m-%d'), "recommendations": []}
        start_time = datetime.fromtimestamp(day_forecast['sunrise'], tz=TZ) + timedelta(hours=1)

        for route in ROUTES:
            dist = route_distance_miles(route) 
            duration = dist / 3.0 # Use an average speed
            end_time = start_time + timedelta(hours=duration)
            
            # --- BUILD THE LEGS ARRAY ---
            legs_array = []
            for leg_start, leg_end in route["legs"]:
                leg_dist = haversine_miles(leg_start, leg_end)
                # For now, let's add placeholders for per-leg data
                legs_array.append({
                    "from": COORD_TO_NAME.get(leg_start, "Unknown"),
                    "to": COORD_TO_NAME.get(leg_end, "Unknown"),
                    "distance_miles": round(leg_dist, 1),
                    "tide_phase": "N/A",
                    "current_kts": "N/A",
                    "assist": "neutral",
                    "gate_required": "Cavallo" in (COORD_TO_NAME.get(leg_start, ""), COORD_TO_NAME.get(leg_end, "")),
                    "gate_ok": True, # Placeholder
                    "est_time_h@2.5": round(leg_dist / 2.5, 1),
                    "est_time_h@3.0": round(leg_dist / 3.0, 1),
                    "est_time_h@3.5": round(leg_dist / 3.5, 1)
                })

            # Existing logic for overall trip data...
            max_gust = max((h.get('wind_gust', 0) for h in hourly_forecasts if start_time <= datetime.fromtimestamp(h['dt'],tz=TZ) < end_time), default=day_forecast.get('wind_gust',0)) if hourly_forecasts else 0
            
            # Create final recommendation, now including the 'legs' array
            rec = {
                "name": route['name'],
                "start_local": start_time.isoformat(),
                "end_local": end_time.isoformat(),
                "duration_hours": round(duration, 1),
                "distance_miles": round(dist, 1),
                "difficulty": classify(duration, max_gust),
                "confidence": "High" if d < 3 else "Medium",
                "wind_range": "...", # Simplified for this example
                "tide_summary": "...",
                "current_summary": "...",
                "legs": legs_array # ADDED THE NEW ARRAY HERE
            }
            day_obj["recommendations"].append(rec)
            
        payload["days"].append(day_obj)

    os.makedirs("docs", exist_ok=True)
    with open("docs/plan.json", "w") as f:
        json.dump(payload, f, indent=2)
    print("Successfully wrote new plan with per-leg data.")

if __name__ == "__main__":
    main()
