# plan_generator.py - VERSION 10.0 (GIA's FOUL TIDE FIX)
import json
import math
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests

# (All Constants, ROUTES, and Helper functions are unchanged)
TZ = ZoneInfo("America/Los_Angeles"); P40 = (37.7835, -122.3883); P39 = (37.8087, -122.4098); CLIPPER = (37.8270, -122.3694); TIBURON = (37.8735, -122.4565); CAVALLO = (37.8357, -122.4771); SFYH = (37.8070, -122.4430); AQ_PARK = (37.8081, -122.4223); TORPEDO = (37.8285, -122.4645); CRANE_COVE = (37.7687, -122.3855); BRISBANE = (37.6833, -122.3787); JACK_LONDON = (37.7950, -122.2709); BROOKLYN = (37.7892, -122.2575); BERKELEY = (37.8631, -122.3168); SCHOONMAKER = (37.8546, -122.4764)
ROUTES = [{"id":"p40-p39", "name":"Pier 40 to Pier 39", "legs":[(P40, P39), (P39, P40)]},{"id":"p40-clipper", "name":"Pier 40 to Clipper Cove", "legs":[(P40, CLIPPER), (CLIPPER, P40)]},{"id":"p40-tiburon", "name":"Pier 40 to Tiburon", "legs":[(P40, TIBURON), (TIBURON, P40)]},{"id":"p40-cavallo", "name":"Pier 40 to Cavallo Point", "legs":[(P40, CAVALLO), (CAVALLO, P40)]},{"id":"p40-sfyh", "name":"Pier 40 to SF Yacht Harbor", "legs":[(P40, SFYH), (SFYH, P40)]},{"id":"p40-aqpark", "name":"Pier 40 to Aquatic Park", "legs":[(P40, AQ_PARK), (AQ_PARK, P40)]},{"id":"p40-torpedo", "name":"Pier 40 to Torpedo Wharf", "legs":[(P40, TORPEDO), (TORPEDO, P40)]},{"id":"p40-cranecove", "name":"Pier 40 to Crane Cove", "legs":[(P40, CRANE_COVE), (CRANE_COVE, P40)]},{"id":"p40-brisbane", "name":"Pier 40 to Brisbane Marina", "legs":[(P40, BRISBANE), (BRISBANE, P40)]},{"id":"p40-jacklondon", "name":"Pier 40 to Jack London Sq", "legs":[(P40, JACK_LONDON), (JACK_LONDON, P40)]},{"id":"p40-brooklyn", "name":"Pier 40 to Brooklyn Basin", "legs":[(P40, BROOKLYN), (BROOKLYN, P40)]},{"id":"p40-berkeley", "name":"Pier 40 to Berkeley Marina", "legs":[(P40, BERKELEY), (BERKELEY, P40)]},{"id":"p40-schoonmaker", "name":"Pier 40 to Schoonmaker", "legs":[(P40, SCHOONMAKER), (SCHOONMAKER, P40)]},]
NOAA_TIDE_STATION = "9414290"; NOAA_CURRENT_STATION = "SFB1201"

# --- V2 BACK-PORT: Knowledge of route geography ---
ROUTE_BEARINGS = { "p40-p39": 350, "p40-clipper": 20, "p40-tiburon": 330, "p40-cavallo": 320, "p40-sfyh": 325, "p40-aqpark": 335, "p40-torpedo": 320, "p40-cranecove": 170, "p40-brisbane": 160, "p40-jacklondon": 50, "p40-brooklyn": 60, "p40-berkeley": 10, "p40-schoonmaker": 320, }
EBB_BEARING = 240 # Avg direction of Ebb Current (out the Gate) is SW
FLOOD_BEARING = 60 # Avg direction of Flood Current (in the Gate) is NE

def haversine_miles(a,b):
    R=3958.761;lat1,lon1=a;lat2,lon2=b;phi1,phi2=math.radians(lat1),math.radians(lat2);dphi=math.radians(lat2-lat1);dl=math.radians(lon2-lon1);x=math.sin(dphi/2)**2+math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2;return 2*R*math.atan2(math.sqrt(x),math.sqrt(1-x))
def route_distance_miles(route): return sum(haversine_miles(a, b) for a, b in route["legs"])
def classify(duration_hours, gust_mph):
    if gust_mph > 28: return "No-Go";
    if duration_hours <= 3 and gust_mph <= 17: return "Easy";
    if duration_hours <= 6 and gust_mph <= 23: return "Moderate";
    return "Challenging"
def get_weather_forecast():
    # ... (function is complete and unchanged)
def get_noaa_predictions(station, product):
    # ... (function is complete and unchanged)

# --- MAIN SCRIPT ---
def main():
    daily_forecasts, hourly_forecasts = get_weather_forecast()
    if not daily_forecasts: return

    tide_data = get_noaa_predictions(NOAA_TIDE_STATION, "predictions")
    current_data = get_noaa_predictions(NOAA_CURRENT_STATION, "currents_predictions")
    
    payload = {"generated_at": datetime.now(TZ).isoformat(), "rider_preset": "Casual", "version": "10.0.0-foul-tide-fix", "days": []}

    for d, day_forecast in enumerate(daily_forecasts):
        the_date = datetime.fromtimestamp(day_forecast['dt'], tz=TZ).date()
        day_obj = {"date_local": the_date.strftime('%Y-%m-%d'), "recommendations": []}
        start_time = datetime.fromtimestamp(day_forecast['sunrise'], tz=TZ) + timedelta(hours=1)
        
        todays_tide_events = [p for p in tide_data.get('predictions', []) if 't' in p and datetime.strptime(p['t'], '%Y-%m-%d %H:%M').date() == the_date] if tide_data else []

        for r in ROUTES:
            dist = route_distance_miles(r); duration = dist / 2.7; end_time = start_time + timedelta(hours=duration)
            
            # (Wind logic is unchanged)
            hourly_in_window = [h for h in hourly_forecasts if start_time <= datetime.fromtimestamp(h['dt'],tz=TZ) < end_time] if hourly_forecasts else []
            max_gust = max((h.get('wind_gust', h.get('wind_speed', 0)) for h in hourly_in_window), default=day_forecast.get('wind_gust',0))
            wind_range = f"{round(min([h.get('wind_speed',0) for h in hourly_in_window] or [0]))}-{round(max([h.get('wind_speed',0) for h in hourly_in_window] or [0]))}"
            
            # --- FINAL, ROBUST TIDE AND CURRENT LOGIC ---
            tide_summary, current_summary, current_effect = "N/A", "N/A", "N/A"
            try:
                if current_data and 'data' in current_data:
                    all_currents_today = [p for p in current_data['data'] if 't' in p and 's' in p and datetime.strptime(p['t'], '%Y-%m-%d %H:%M').date() == the_date]
                    if all_currents_today:
                        # Find the single closest data point to the start time
                        departure_current = min(all_currents_today, key=lambda p: abs(datetime.strptime(p['t'], '%Y-%m-%d %H:%M').astimezone(TZ) - start_time))
                        departure_speed = float(departure_current['s'])
                        direction = "Flood" if departure_speed > 0 else "Ebb"
                        
                        # For long trips, show the range. For short trips, show the departure speed.
                        if duration > 1.0:
                            currents_in_window = [p for p in all_currents_today if start_time <= datetime.strptime(p['t'], '%Y-%m-%d %H:%M').astimezone(TZ) < end_time]
                            if currents_in_window:
                                min_c=min(float(p['s']) for p in currents_in_window); max_c=max(float(p['s']) for p in currents_in_window)
                                current_summary = f"{direction} {abs(min_c):.1f}-{abs(max_c):.1f} kts"
                            else: # Fallback for long trips that find no data
                                current_summary = f"{direction} {abs(departure_speed):.1f} kts"
                        else:
                            current_summary = f"{direction} {abs(departure_speed):.1f} kts"
                            
                        # Calculate Foul/Fair effect
                        route_bearing = ROUTE_BEARINGS.get(r['id'])
                        current_bearing = FLOOD_BEARING if direction == "Flood" else EBB_BEARING
                        if route_bearing is not None:
                            angle_diff = abs((route_bearing - current_bearing + 180) % 360 - 180)
                            if angle_diff < 45: current_effect = "Fair" # With you
                            elif angle_diff > 135: current_effect = "Foul" # Against you
                            else: current_effect = "Cross"

                # Simplified tide logic from before
                if todays_tide_events:
                     tide_events_in_window = [p for p in todays_tide_events if start_time <= datetime.strptime(p['t'], '%Y-%m-%d %H:%M').astimezone(TZ) < end_time]
                     tide_summary = ", ".join([f"{p['type']} @ {datetime.strptime(p['t'], '%Y-%m-%d %H:%M').strftime('%-I:%M%p')}" for p in tide_events_in_window]) or " "

            except Exception as e: print(f"WARN: Handled a parsing error: {e}")

            rec = {"route_id": r["id"], "name": r["name"], "start_local": start_time.isoformat(), "end_local": end_time.isoformat(), "duration_hours": round(duration, 1), "distance_miles": round(dist, 1), "difficulty": classify(duration, max_gust), "confidence": "High" if d < 3 else "Medium", "wind_range": wind_range, "tide_summary": tide_summary, "current_summary": current_summary, "current_effect": current_effect}
            if r["id"] == "p40-p39": rec.update({"difficulty": "No-Go", "duration_hours": 0.0, "distance_miles": round(dist, 1), "current_summary": "N/A", "current_effect": "N/A" })
            
            day_obj["recommendations"].append(rec)
        payload["days"].append(day_obj)

    os.makedirs("docs", exist_ok=True)
    with open("docs/plan.json", "w) as f: json.dump(payload, f, indent=2)
    print("Successfully wrote new plan with foul tide logic.")

if __name__ == "__main__":
    main()
