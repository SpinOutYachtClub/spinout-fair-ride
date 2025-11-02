# plan_generator.py - VERSION 2.6 (Adds Distance to Output)
import json
import math
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests

# --- CONSTANTS (Unchanged) ---
TZ = ZoneInfo("America/Los_Angeles")
P40 = (37.7835, -122.3883)
P39 = (37.8087, -122.4098); CLIPPER = (37.8270, -122.3694); TIBURON = (37.8735, -122.4565); CAVALLO = (37.8357, -122.4771)
ROUTES = [
    {"id":"p40-p39", "name":"Pier 40 to Pier 39", "stops":["Pier 39"], "legs":[(P40, P39), (P39, P40)]},
    {"id":"p40-clipper", "name":"Pier 40 to Clipper Cove", "stops":["Clipper Cove"], "legs":[(P40, CLIPPER), (CLIPPER, P40)]},
    {"id":"p40-tiburon", "name":"Pier 40 to Tiburon", "stops":["Tiburon"], "legs":[(P40, TIBURON), (TIBURON, P40)]},
    {"id":"p40-cavallo", "name":"Pier 40 to Cavallo Point", "stops":["Cavallo Point"], "legs":[(P40, CAVALLO), (CAVALLO, P40)]},
]
NOAA_TIDE_STATION = "9414290"
NOAA_CURRENT_STATION = "SFB1201"

# --- HELPER FUNCTIONS (Unchanged) ---
def haversine_miles(a,b):
    R=3958.761;lat1,lon1=a;lat2,lon2=b;phi1,phi2=math.radians(lat1),math.radians(lat2);dphi=math.radians(lat2-lat1);dl=math.radians(lon2-lon1);x=math.sin(dphi/2)**2+math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2;return 2*R*math.atan2(math.sqrt(x),math.sqrt(1-x))
def route_distance_miles(route): return sum(haversine_miles(a, b) for a, b in route["legs"])
def classify(duration_hours, gust_mph):
    if gust_mph > 28: return "No-Go";
    if duration_hours <= 3 and gust_mph <= 17: return "Easy";
    if duration_hours <= 6 and gust_mph <= 23: return "Moderate";
    return "Challenging"

# --- DATA FETCHING FUNCTIONS (Unchanged) ---
def get_weather_forecast():
    api_key=os.getenv("WEATHER_API_KEY");
    if not api_key: print("CRITICAL: WEATHER_API_KEY secret not found."); return None, None
    url=f"https://api.openweathermap.org/data/3.0/onecall?lat={P40[0]}&lon={P40[1]}&exclude=current,minutely,alerts&appid={api_key}&units=imperial"
    try:
        r=requests.get(url); r.raise_for_status(); data=r.json(); print("Successfully fetched weather data."); return data.get('daily',[]), data.get('hourly',[])
    except requests.exceptions.RequestException as e: print(f"Error fetching weather data: {e}"); return None, None

def get_noaa_predictions(station, product, date_str):
    base_url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    params = {"station": station, "product": product, "datum": "MLLW", "units": "english", "time_zone": "lst_ldt", "format": "json", "application": "SpinoutFairRidePlanner", "date": date_str}
    try:
        r = requests.get(base_url, params=params); r.raise_for_status(); return r.json()
    except requests.exceptions.RequestException as e:
        print(f"INFO: Could not fetch NOAA {product} data for {station} on {date_str}. Error: {e}"); return None

# --- MAIN SCRIPT ---
def main():
    daily_forecasts, hourly_forecasts = get_weather_forecast()
    if not daily_forecasts: print("Exiting due to weather API failure."); return

    real_today = datetime.now(TZ).date()
    
    payload = {"generated_at": datetime.now(TZ).isoformat(), "rider_preset": "Casual", "version": "0.6.0-with-distance", "days": [], "disclaimer": "..."}

    for d, day_forecast in enumerate(daily_forecasts):
        display_date = datetime.fromtimestamp(day_forecast['dt'], tz=TZ).date()
        noaa_date_for_loop = real_today + timedelta(days=d)
        noaa_date_str = noaa_date_for_loop.strftime('%Y%m%d')

        tide_data = get_noaa_predictions(NOAA_TIDE_STATION, "predictions", noaa_date_str)
        current_data = get_noaa_predictions(NOAA_CURRENT_STATION, "currents_predictions", noaa_date_str)
        
        day_obj = {"date_local": display_date.strftime('%Y-%m-%d'), "recommendations": []}
        start_time = datetime.fromtimestamp(day_forecast['sunrise'], tz=TZ) + timedelta(hours=1)

        for r in ROUTES:
            dist = route_distance_miles(r) # Distance is calculated here
            duration = dist / 2.7
            end_time = start_time + timedelta(hours=duration)
            
            # Wind Logic
            hourly_in_window = [h for h in hourly_forecasts if start_time <= datetime.fromtimestamp(h['dt'],tz=TZ) < end_time] if hourly_forecasts else []
            max_gust = max((h.get('wind_gust', h.get('wind_speed', 0)) for h in hourly_in_window), default=day_forecast.get('wind_gust',0))
            wind_speeds = [h.get('wind_speed',0) for h in hourly_in_window] or [day_forecast.get('wind_speed',0)]
            wind_range = f"{round(min(wind_speeds))}-{round(max(wind_speeds))
