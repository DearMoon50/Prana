
import requests
import numpy as np
import math
from datetime import datetime, timedelta

def stull_wet_bulb(temp_c, humidity_percent):
    if temp_c is None or humidity_percent is None:
        return None
    T = float(temp_c)
    RH = float(humidity_percent)
    return (
        T * math.atan(0.151977 * math.sqrt(RH + 8.313659))
        + math.atan(T + RH)
        - math.atan(RH - 1.676331)
        + 0.00391838 * (RH ** 1.5) * math.atan(0.023101 * RH)
        - 4.686035
    )

CITIES = [
    {"name": "Ho Chi Minh City", "lat": 10.7626, "lon": 106.6601},
    {"name": "Chennai", "lat": 13.0827, "lon": 80.2707},
    {"name": "Dhaka", "lat": 23.8103, "lon": 90.4125},
    {"name": "Karachi", "lat": 24.8607, "lon": 67.0011},
    {"name": "Manila", "lat": 14.5995, "lon": 120.9842},
    {"name": "Jakarta", "lat": -6.2088, "lon": 106.8456},
]

END_DATE = "2026-06-30"
START_DATE = "2026-06-01"

def fetch_city_data(city):
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": city["lat"],
        "longitude": city["lon"],
        "start_date": START_DATE,
        "end_date": END_DATE,
        "hourly": "temperature_2m,relative_humidity_2m",
        "timezone": "auto"
    }
    response = requests.get(url, params=params)
    data = response.json()
    return data

def process_city(city, data):
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    humidities = hourly.get("relative_humidity_2m", [])
    
    night_data = [] # List of (min_temp, humidity_at_min_temp) per night
    
    # Group by date
    daily_data = {}
    for t, temp, hum in zip(times, temps, humidities):
        dt = datetime.fromisoformat(t)
        date = dt.date()
        hour = dt.hour
        
        # Nighttime is 22:00 to 06:00
        # Wait, the prompt says nighttime (22:00-06:00) 
        # A "night" crosses two calendar dates. 
        # Let's define a night by its start date (e.g. night of June 1st is Jun 1 22:00 to Jun 2 06:00)
        
        # Shift time by 2 hours so 22:00 becomes 00:00 of the "night"
        night_dt = dt - timedelta(hours=22)
        night_date = night_dt.date()
        
        # If hour is between 22 and 23 or 0 and 6, it's nighttime
        if hour >= 22 or hour <= 6:
            if night_date not in daily_data:
                daily_data[night_date] = []
            daily_data[night_date].append({"temp": temp, "hum": hum})
            
    processed_nights = []
    for night_date, readings in daily_data.items():
        if not readings: continue
        # Find min temp of that night
        min_reading = min(readings, key=lambda x: x["temp"])
        min_temp = min_reading["temp"]
        hum = min_reading["hum"]
        wb = stull_wet_bulb(min_temp, hum)
        processed_nights.append({"temp": min_temp, "hum": hum, "wb": wb})
        
    return processed_nights

print(f"EXPERIMENT 3: SUMMARY STATS (June 1 - June 30 2026)")
print("-" * 120)
print(f"{'City':<20} | {'Mean Min T':<10} | {'Mean Hum':<10} | {'90th Temp':<10} | {'90th WetBulb':<12}")
print("-" * 120)

city_results = {}

for city in CITIES:
    data = fetch_city_data(city)
    nights = process_city(city, data)
    city_results[city["name"]] = nights
    
    temps = [n["temp"] for n in nights]
    hums = [n["hum"] for n in nights]
    wbs = [n["wb"] for n in nights]
    
    mean_temp = np.mean(temps)
    mean_hum = np.mean(hums)
    p90_temp = np.percentile(temps, 90)
    p90_wb = np.percentile(wbs, 90)
    
    print(f"{city['name']:<20} | {mean_temp:8.1f}C | {mean_hum:8.1f}% | {p90_temp:8.1f}C | {p90_wb:10.1f}C")

# Save results for next experiments
import json
with open("city_nights_data.json", "w") as f:
    json.dump(city_results, f)
