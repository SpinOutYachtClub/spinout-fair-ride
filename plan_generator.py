# plan_generator.py - VERSION 8.2 (Adding New Locations)
import json
import math
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests

# --- CONSTANTS ---
TZ = ZoneInfo("America/Los_Angeles")
# Original Locations
P40 = (37.7835, -122.3883)
P39 = (37.8087, -122.4098)
CLIPPER = (37.8270, -122.3694)
TIBURON = (37.8735, -122.4565)
CAVALLO = (37.8357, -122.4771)

# ===============================================
# === NEW LOCATIONS START HERE ==================
# ===============================================
SFYH = (37.8070, -122.4430)         # San Francisco Yacht Harbor
AQ_PARK = (37.8081, -122.4223)      # San Francisco Aquatic Park
TORPEDO = (37.8285, -122.4645)      # Torpedo Wharf
CRANE_COVE = (37.7687, -122.3855)   # Crane Cove Park
BRISBANE = (37.6833, -122.3787)     # Brisbane Marina
JACK_LONDON = (37.7950, -122.2709)  # Jack London Square Marina
BROOKLYN = (37.7892, -122.2575)    # Brooklyn Basin
BERKELEY = (37.8631, -122.3168)     # Berkeley Marina
SCHOONMAKER = (37.8546, -122.4764)  # Schoonmaker Beach (Sausalito)
# ===============================================
# === NEW LOCATIONS END HERE ====================
# ===============================================

ROUTES = [
    # Original Routes
    {"id":"p40-p39", "name":"Pier 40 to Pier 39", "stops":["Pier 39"], "legs":[(P40, P39), (P39, P40)]},
    {"id":"p40-clipper", "name":"Pier 40 to Clipper Cove", "stops":["Clipper Cove"], "legs":[(P40, CLIPPER), (CLIPPER, P40)]},
    {"id":"p40-tiburon", "name":"Pier 40 to Tiburon", "stops":["Tiburon"], "legs":[(P40, TIBURON), (TIBURON, P40)]},
    {"id":"p40-cavallo", "name":"Pier 40 to Cavallo Point", "stops":["Cavallo Point"], "legs":[(P40, CAVALLO), (CAVALLO, P40)]},
    
    # ===============================================
    # === NEW ROUTES START HERE =====================
    # ===============================================
    {"id":"p40-sfyh", "name":"Pier 40 to SF Yacht Harbor", "stops":["SF Yacht Harbor"], "legs":[(P40, SFYH), (SFYH, P40)]},
    {"id":"p40-aqpark", "name":"Pier 40 to Aquatic Park", "stops":["Aquatic Park"], "legs":[(P40, AQ_PARK), (AQ_PARK, P40)]},
    {"id":"p40-torpedo", "name":"Pier 40 to Torpedo Wharf", "stops":["Torpedo Wharf"], "legs":[(P40, TORPEDO), (TORPEDO, P40)]},
    {"id":"p40-cranecove", "name":"Pier 40 to Crane Cove", "stops":["Crane Cove"], "legs":[(P40, CRANE_COVE), (CRANE_COVE, P40)]},
    {"id":"p40-brisbane", "name":"Pier 40 to Brisbane Marina", "stops":["Brisbane Marina"], "legs":[(P40, BRISBANE), (BRISBANE, P40)]},
    {"id":"p40-jacklondon", "name":"Pier 40 to Jack London Square", "stops":["Jack London Square"], "legs":[(P40, JACK_LONDON), (JACK_LONDON, P40)]},
    {"id":"p40-brooklyn", "name":"Pier 40 to Brooklyn Basin", "stops":["Brooklyn Basin"], "legs":[(P40, BROOKLYN), (BROOKLYN, P40)]},
    {"id":"p40-berkeley", "name":"Pier 40 to Berkeley Marina", "stops":["Berkeley Marina"], "legs":[(P40, BERKELEY), (BERKELEY, P40)]},
    {"id":"p40-schoonmaker", "name":"Pier 40 to Schoonmaker Beach", "stops":["Schoonmaker Beach"], "legs":[(P40, SCHOONMAKER), (SCHOONMAKER, P40)]},
    # ===============================================
    # === NEW ROUTES END HERE =======================
    # ===============================================
]

# NOAA Stations (unchanged)
NOAA_TIDE_STATION = "9414290"
NOAA_CURRENT_STATION = "SFB1201"

# --- HELPER FUNCTIONS ---
def haversine_miles(a, b):
    R = 3958.761
    lat1, lon1 = a; lat2, lon2 = b
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl/2)**2
    return 2 * R * math.atan2(math.sqrt(x), math.sqrt(1 - x))

def route_distance_miles(route):
    return sum(haversine_miles(a, b) for a, b in route["legs"])

def classify(duration_hours, gust_mph):
    if gust_mph > 28: return "No-Go"
    if duration_hours <= 3 and gust_mph <= 17: return "Easy"
    if duration_hours <= 6 and gust_mph <= 23: return "Moderate"
    return "Challenging"

# ===============================================
# === WHY_LINE FUNCTION UPDATE START ============
# ===============================================
def why_line(route_id, difficulty, gust_mph):
    gust_kt = round(gust_mph / 1.15)
    # Original Custom Lines
    if route_id == "p40-p39":
        return "Not recommended as a stand-alone out-and-back because it does not meet the two hour minimum under current club rules."
    if route_id == "p40-clipper":
        return f"Easy; mostly sheltered behind Treasure Island, gusts ≤ {gust_kt} kt, and the round trip is under 3 hours."
    if route_id == "p40-tiburon":
        return f"Moderate; the route is exposed across the Central Bay, but gusts are manageable at ≤ {gust_kt} kt."
    if route_id == "p40-cavallo":
        return f"Moderate; Raccoon Strait gives some lee but the approach to the Golden Gate is exposed; gusts are manageable at ≤ {gust_kt} kt."
    
    # NEW: Default case for all other new routes
    return f"General recommendation based on a forecast of {gust_kt} kt gusts."
# ===============================================
# === WHY_LINE FUNCTION UPDATE END ==============
# ===============================================

# (The rest of the file remains exactly the same as our stable V8.1/Version 5.0)
def get_weather_forecast():
    # ... code for get_weather_forecast
def get_noaa_predictions(station, product):
    # ... code for get_noaa_predictions
def main():
    # ... all of the main function code
