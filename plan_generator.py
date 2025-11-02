# plan_generator.py - VERSION 2.2 (with NOAA Tide & Current Data)
import json
import math
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests

# --- CONSTANTS ---
# (Your existing constants like TZ, P40, ROUTES remain the same)
TZ = ZoneInfo("America/Los_Angeles")
P40 = (37.7835, -122.3883)
P39 = (37.8087, -122.4098); CLIPPER = (37.8270, -122.3694); TIBURON = (37.8735, -122.4565); CAVALLO = (37.8357, -122.4771)
ROUTES = [
    {"id":"p40-p39", "name":"Pier 40 to Pier 39", "stops":["Pier 39"], "legs":[(P40, P39), (P39, P40)]},
    {"id":"p40-clipper", "name":"Pier 40 to Clipper Cove", "stops":["Clipper Cove"], "legs":[(P40, CLIPPER), (CLIPPER, P40)]},
    {"id":"p40-tiburon", "name":"Pier 40 to Tiburon", "stops":["Tiburon"], "legs":[(P40, TIBURON), (TIBURON, P40)]},
    {"id":"p40-cavallo", "name":"Pier 40 to Cavallo Point", "stops":["Cavallo Point"], "legs":[(P40, CAVALLO), (CAVALLO, P40)]},
]
NOAA_TIDE_STATION = "9414290"  # San Francisco, CA
NOAA_CURRENT_STATION = "SFB1201" # SF Bay Bridge

# --- HELPER FUNCTIONS ---
# (haversine_miles, route_distance_miles, classify, why_line remain the same)
def haversine_miles(a,b):
    R=3958.761;lat1,lon1=a;lat2,lon2=b;phi1,phi2=math.radians(lat1),math.radians(lat2);dphi=math.radians(lat2-lat1);dl=math.radians(lon2-lon1);x=math.sin(dphi/2)**2+math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2;return 2*R*math.atan2(math.sqrt(x),math.sqrt(1-x))
def route_distance_miles(route): return sum(haversine_miles(a, b) for a, b in route["legs"])
def classify(duration_hours, gust_mph):
    if gust_mph > 28: return "No-Go";
    if duration_hours <= 3 and gust_mph <= 17: return "Easy";
    if duration_hours <= 6 and gust_mph <= 23: return "Moderate";
    return "Challenging"
def why_line(route_id, difficulty, gust_mph):
    gust_kt = round(gust_mph/1.15);
    if route_id=="p40-p39":return"Not recommended as a stand-alone out-and-back because it does not meet the two hour minimum under current club rules."
    if route_id=="p40-clipper":return f"Easy; mostly sheltered behind Treasure Island, gusts ≤ {gust_kt} kt, and the round trip is under 3 hours."
    if route_id=="p40-tiburon":return f"Moderate; the route is exposed across the Central Bay, but gusts are manageable at ≤ {gust_kt} kt."
    if route_id=="p40-cavallo":return f"Moderate; Raccoon Strait gives some lee but the approach to the Golden Gate is exposed; gusts are manageable at ≤ {gust_kt} kt."
    return"General recommendation based on forecast."

# --- DATA FETCHING FUNCTIONS ---
def get_weather_forecast():
    api_key=os.getenv("WEATHER_API_KEY");
    if not api_key: print("CRITICAL: WEATHER_API_KEY secret not found."); return None, None
    url=f"https://api.openweathermap.org/data/3.0/onecall?lat={P40[0]}&lon={P40[1]}&exclude=current,minutely,alerts&appid={api_key}&units=imperial"
    try:
        r=requests.get(url); r.raise_for_status(); data=r.json(); print("Successfully fetched weather data."); return data.get('daily',[]), data.get('hourly',[])
    except requests.exceptions.RequestException as e: print(f"Error fetching weather data: {e}"); return None, None

# --- NEW: NOAA TIDE & CURRENT FUNCTIONS ---
def get_noaa_predictions(station, product, date_str):
    url = f"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date={date_str}&station={station}&product={product}&datum=MLLW&units=english&time_zone=lst_ldt&format=json"
    try:
        r = requests.get(url); r.raise_for_status(); return r.json()
    except requests.exceptions.RequestException as e: print(f"Error fetching NOAA {product} data for {station}: {e}"); return None

# --- MAIN SCRIPT ---
def main():
    daily_forecasts, hourly_forecasts = get_weather_forecast()
    if not daily_forecasts: print("Exiting due to weather API failure."); return

    payload = {"generated_at": datetime.now(TZ).isoformat(), "version": "0.5.0-tides", "days": [], "disclaimer": "..."}

    for d, day_forecast in enumerate(daily_forecasts):
        the_date = datetime.fromtimestamp(day_forecast['dt'], tz=TZ)
        date_str = the_date.strftime('%Y%m%d')
        
        # Fetch tide and current data for the day
        tide_data = get_noaa_predictions(NOAA_TIDE_STATION, "predictions", date_str)
        current_data = get_noaa_predictions(NOAA_CURRENT_STATION, "currents_predictions", date_str)

        day_obj = {"date_local": the_date.strftime('%Y-%m-%d'), "recommendations": []}

        start_time = datetime.fromtimestamp(day_forecast['sunrise'], tz=TZ) + timedelta(hours=1)

        for r in ROUTES:
            duration = route_distance_miles(r) / 2.7 # Simplified effective speed
            end_time = start_time + timedelta(hours=duration)
            
            # Find max gust in window
            max_gust = next((h.get('wind_gust',0) for h in hourly_forecasts if start_time <= datetime.fromtimestamp(h['dt'],tz=TZ) < end_time), day_forecast.get('wind_gust',0)) if hourly_forecasts else day_forecast.get('wind_gust',0)
            wind_speeds = [h.get('wind_speed',0) for h in hourly_forecasts if start_time <= datetime.fromtimestamp(h['dt'],tz=TZ) < end_time] if hourly_forecasts else [day_forecast.get('wind_speed',0)]
            wind_range = f"{round(min(wind_speeds))}-{round(max(wind_speeds))}" if wind_speeds else "N/A"
            
            # Find key tide & current events in window
            tide_events_in_window = [p for p in tide_data.get('predictions',[]) if start_time <= datetime.strptime(p['t'], '%Y-%m-%d %H:%M').astimezone(TZ) < end_time] if tide_data else []
            tide_summary = ", ".join([f"{'High' if p['type']=='H' else 'Low'} Tide at {datetime.strptime(p['t'], '%Y-%m-%d %H:%M').strftime('%-I:%M%p')}" for p in tide_events_in_window]) or "N/A"
            
            currents_in_window = [p for p in current_data.get('data',[]) if start_time <= datetime.strptime(p['t'], '%Y-%m-%d %H:%M').astimezone(TZ) < end_time] if current_data else []
            current_summary = ""
            if currents_in_window:
                min_current = min(float(p['s']) for p in currents_in_window)
                max_current = max(float(p['s']) for p in currents_in_window)
                direction = "Flood" if float(currents_in_window[0]['s']) > 0 else "Ebb"
                current_summary = f"{direction} {min_current:.1f}-{max_current:.1f} kts"
            
            rec = {
                "route_id": r["id"], "name": r["name"], "stops": r["stops"],
                "start_local": start_time.isoformat(), "end_local": end_time.isoformat(),
                "duration_hours": round(duration, 1), "difficulty": classify(duration, max_gust),
                "confidence": "High" if d < 2 else "Medium",
                "wind_range": wind_range,
                "tide_summary": tide_summary,
                "current_summary": current_summary,
                "notes": f"Max gusts to {max_gust:.1f} mph."
            }
            if r["id"] == "p40-p39": rec.update({"difficulty": "No-Go", "duration_hours": 0.0, "no_go_reason": "Route too short."})
            
            day_obj["recommendations"].append(rec)
        payload["days"].append(day_obj)
        start_time += timedelta(days=1)

    with open("docs/plan.json", "w") as f: json.dump(payload, f, indent=2)
    print("Successfully wrote new plan with NOAA tide/current data.")

if __name__ == "__main__":
    main()
