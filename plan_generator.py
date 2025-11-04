# plan_generator.py - VERSION 8.0 (FINAL PARSER FIX)
import json
import math
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
import yaml

# --- CONSTANTS & HELPERS ---
TZ = ZoneInfo("America/Los_Angeles")
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

# --- DATA FETCHING FUNCTIONS ---
def get_weather_forecast():
    # Unchanged
    pass
def get_noaa_predictions(station, product):
    # Unchanged, includes the hilo fix
    pass

# --- MAIN SCRIPT ---
def main():
    # The setup is unchanged...
    # ...
    # Loop through days and routes...
        # ...
            # Tide/Current Logic
            tide_summary, current_summary = "", ""
            try:
                if tide_data and 'predictions' in tide_data:
                    # Unchanged Tide logic
                    pass
            except Exception as e: print(f"WARN: Handled a tide parsing error: {e}")
                
            try:
                # --- THIS IS THE FINAL FIX ---
                # It correctly looks for `current_predictions['cp']` instead of just `data`
                if current_data and 'current_predictions' in current_data and 'cp' in current_data['current_predictions']:
                    currents = [p for p in current_data['current_predictions']['cp'] if 'Time' in p and 'Velocity_Major' in p and start_time <= datetime.strptime(p['Time'], '%Y-%m-%d %H:%M').astimezone(TZ) < end_time]
                    if currents:
                        min_c=min(float(p['Velocity_Major']) for p in currents); max_c=max(float(p['Velocity_Major']) for p in currents)
                        direction="Flood" if float(currents[0]['Velocity_Major']) > 0 else "Ebb"
                        current_summary = f"{direction} {abs(min_c):.1f}-{abs(max_c):.1f} kts"
            except Exception as e: print(f"WARN: Handled a current parsing error: {e}")

            # ...
            # The rest of the script is the same...
            # ...
    # Write to file
    pass

if __name__ == "__main__":
    main()
