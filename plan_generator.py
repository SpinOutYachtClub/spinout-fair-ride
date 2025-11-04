# plan_generator.py - VERSION 11.0 (TIDAL ENGINE)
import json
import math
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
import yaml

# --- CONSTANTS & SETUP ---
TZ = ZoneInfo("America/Los_Angeles")
P40 = (37.7835, -122.3883); P39 = (37.8087, -122.4098); CLIPPER = (37.8270, -122.3694); TIBURON = (37.8735, -122.4565); CAVALLO = (37.8357, -122.4771)
COORD_TO_NAME = { P40: "Pier 40", P39: "Pier 39", CLIPPER: "Clipper Cove", TIBURON: "Tiburon", CAVALLO: "Cavallo Point" }
ROUTES = [{"id":"p40-p39", "name":"Pier 40 to Pier 39", "legs":[(P40, P39), (P39, P40)]},{"id":"p40-clipper", "name":"Pier 40 to Clipper Cove", "legs":[(P40, CLIPPER), (CLIPPER, P40)]},{"id":"p40-tiburon", "name":"Pier 40 to Tiburon", "legs":[(P40, TIBURON), (TIBURON, P40)]},{"id":"p40-cavallo", "name":"Pier 40 to Cavallo Point", "legs":[(P40, CAVALLO), (CAVALLO, P40)]}]
NOAA_TIDE_STATION = "9414290"; NOAA_CURRENT_STATION = "SFB1201"

# --- HELPER & PHYSICS FUNCTIONS ---
def haversine_miles(a,b): R=3958.761;lat1,lon1=a;lat2,lon2=b;phi1,phi2=math.radians(lat1),math.radians(lat2);dphi=math.radians(lat2-lat1);dl=math.radians(lon2-lon1);x=math.sin(dphi/2)**2+math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2;return 2*R*math.atan2(math.sqrt(x),math.sqrt(1-x))
def get_noaa_predictions(station, product, date_str):
    # This function now correctly requests hilo for tides
    params = {"station": station, "product": product, "datum": "MLLW", "units": "english", "time_zone": "lst_ldt", "format": "json", "application": "SpinoutFairRide", "begin_date": date_str, "range": "168"}
    if product == "predictions": params["interval"] = "hilo"
    try:
        r = requests.get("https://api.tidesandcurrents.noaa.gov/api/prod/datagetter", params=params); r.raise_for_status(); return r.json()
    except requests.exceptions.RequestException: return None

# --- NEW: YOUR TIDAL ENGINE LOGIC ---
def get_feet_per_hour_label(fph):
    if abs(fph) < 0.25: return "Float"
    if abs(fph) < 0.75: return "Easy"
    if abs(fph) < 1.50: return "Moderate"
    if abs(fph) < 1.75: return "Fast"
    return "Cray Cray"

def get_bearing_label(degrees):
    if 337.5 <= degrees or degrees < 22.5: return "N"
    if 22.5 <= degrees < 67.5: return "NE"
    if 67.5 <= degrees < 112.5: return "E"
    if 112.5 <= degrees < 157.5: return "SE"
    if 157.5 <= degrees < 202.5: return "S"
    if 202.5 <= degrees < 247.5: return "SW"
    if 247.5 <= degrees < 292.5: return "W"
    return "NW"

# --- MAIN SCRIPT ---
def main():
    with open('data/geography.yaml', 'r') as f: geography = yaml.safe_load(f)
    
    today_str = datetime.now(TZ).strftime('%Y%m%d')
    tide_data = get_noaa_predictions(NOAA_TIDE_STATION, "predictions", today_str)
    
    payload = {"generated_at": datetime.now(TZ).isoformat(), "version": "11.0-tidal-engine", "days": []}
    
    if not tide_data or 'predictions' not in tide_data:
        print("CRITICAL: Could not fetch essential tide data. Exiting."); return

    all_tide_events = [p for p in tide_data['predictions'] if 'type' in p]
    
    # Process for the next 3 days for simplicity
    for d in range(3):
        the_date = (datetime.now(TZ) + timedelta(days=d)).date()
        day_obj = {"date_local": the_date.strftime('%Y-%m-%d'), "recommendations": []}

        # Find the 4 primary tide events for the day (or next available)
        daily_events = [p for p in all_tide_events if datetime.strptime(p['t'], '%Y-%m-%d %H:%M').date() == the_date]
        if len(daily_events) < 2: continue # Not enough data for this day

        for i in range(len(daily_events) - 1):
            start_event = daily_events[i]
            end_event = daily_events[i+1]
            
            # --- CALCULATE YOUR NEW METRICS ---
            tide_start_time = datetime.strptime(start_event['t'], '%Y-%m-%d %H:%M')
            tide_end_time = datetime.strptime(end_event['t'], '%Y-%m-%d %H:%M')
            slack_time = tide_start_time + (tide_end_time - tide_start_time) / 2 # Simplified slack midpoint

            tide_start_height = float(start_event['v'])
            tide_end_height = float(end_event['v'])
            height_diff = tide_end_height - tide_start_height
            duration_hours = (tide_end_time - tide_start_time).total_seconds() / 3600
            
            fph = height_diff / duration_hours if duration_hours > 0 else 0
            fph_label = get_feet_per_hour_label(fph)
            flow_direction_label = get_bearing_label(geography['current_vectors']['default_flood'] if height_diff > 0 else geography['current_vectors']['default_ebb'])
            
            rec = {
                "name": "Full Tide Window",
                "window_start": tide_start_time.isoformat(),
                "window_end": tide_end_time.isoformat(),
                "tide_start": f"{tide_start_height:.1f} ft at {tide_start_time.strftime('%-I:%M%p')}",
                "slack_tide_start": slack_time.strftime('%-I:%M%p'),
                "tide_end": f"{tide_end_height:.1f} ft at {tide_end_time.strftime('%-I:%M%p')}",
                "flow_direction": flow_direction_label,
                "current_speed_kts": "N/A", # Current station data would be integrated here
                "fph_speed_label": f"{fph_label} ({fph:.2f} ft/hr)"
            }
            day_obj["recommendations"].append(rec)
            
        payload["days"].append(day_obj)

    os.makedirs("docs", exist_ok=True)
    with open("docs/plan.json", "w") as f: json.dump(payload, f, indent=2)
    print("Successfully wrote new plan with Tidal Engine.")

if __name__ == "__main__":
    main()
