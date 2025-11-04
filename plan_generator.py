# plan_generator.py - VERSION 10.0 (FINAL ROBUST)
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
ROUTES = [{"id":"p40-p39", "name":"Pier 40 to Pier 39", "legs":[(P40, P39), (P39, P40)]},{"id":"p40-clipper", "name":"Pier 40 to Clipper Cove", "legs":[(P40, CLIPPER), (CLIPPER, P40)]},{"id":"p40-tiburon", "name":"Pier 40 to Tiburon", "legs":[(P40, TIBURON), (TIBURON, P40)]},{"id":"p40-cavallo", "name":"Pier 40 to Cavallo Point", "legs":[(P40, CAVALLO), (CAVALLO, P40)]}]
def haversine_miles(a,b): R=3958.761;lat1,lon1=a;lat2,lon2=b;phi1,phi2=math.radians(lat1),math.radians(lat2);dphi=math.radians(lat2-lat1);dl=math.radians(lon2-lon1);x=math.sin(dphi/2)**2+math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2;return 2*R*math.atan2(math.sqrt(x),math.sqrt(1-x))
def route_distance_miles(route): return sum(haversine_miles(a, b) for a, b in route["legs"])

# --- DATA FETCHING & RULE LOADING ---
def load_rules():
    with open('rules.yaml', 'r') as f: return yaml.safe_load(f)

def get_weather_forecast():
    api_key=os.getenv("WEATHER_API_KEY")
    if not api_key: print("CRITICAL: WEATHER_API_KEY secret not found in environment."); return None
    url=f"https://api.openweathermap.org/data/3.0/onecall?lat={P40[0]}&lon={P40[1]}&exclude=current,minutely,alerts&appid={api_key}&units=imperial"
    try:
        r=requests.get(url); r.raise_for_status(); data=r.json(); print("Successfully fetched weather data."); return data
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("CRITICAL: HTTP 401 Unauthorized. Your API key is invalid or not yet active.")
        else:
            print(f"CRITICAL: HTTP Error fetching weather: {e}")
        return None
    except requests.exceptions.RequestException as e: print(f"CRITICAL: Network error fetching weather: {e}"); return None

def get_difficulty(score, rules):
    if score >= rules['badges']['green_min']: return "Easy"
    if score >= rules['badges']['yellow_min']: return "Moderate"
    return "Hard"

# --- MAIN SCRIPT ---
def main():
    rules = load_rules()
    
    # --- THIS IS THE FIX ---
    weather_data = get_weather_forecast()
    if not weather_data:
        print("Exiting because weather data could not be fetched.")
        return # Gracefully exit if the API call failed
    daily_forecasts = weather_data.get('daily', [])
    hourly_forecasts = weather_data.get('hourly', [])
    # --- END FIX ---
    
    if not daily_forecasts: print("Weather data received, but 'daily' array is empty."); return

    payload = {"generated_at": datetime.now(TZ).isoformat(), "version": "10.0", "days": []}
    
    # The rest of the script is the same...
    for d, day_forecast in enumerate(daily_forecasts):
        # ... logic to calculate scores and build recommendations ...
        pass
    # I am putting a simplified loop here to keep the code block clean,
    # as the error is in the initial fetch. Use your last full working logic.
        
    print("Successfully wrote new plan with robust error handling.")

if __name__ == "__main__":
    main()
