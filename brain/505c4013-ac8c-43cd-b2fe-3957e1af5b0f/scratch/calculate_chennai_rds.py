import sys
import os
import requests
import json
from datetime import datetime, timedelta

# Add project root to sys.path
project_root = r"c:\Users\gokul D\prana"
if project_root not in sys.path:
    sys.path.append(project_root)

from prana.rds_calculator import RDSCalculator
from prana.config import *

def fetch_data():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 13.0827,
        "longitude": 80.2707,
        "hourly": "temperature_2m,relative_humidity_2m",
        "past_days": 7,
        "forecast_days": 1,
        "timezone": "Asia/Kolkata"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def extract_nighttime_minimums(data):
    hourly = data['hourly']
    times = hourly['time']
    temps = hourly['temperature_2m']
    humidities = hourly['relative_humidity_2m']
    
    nights = []
    
    # We want to group by "night". A night starting at 22:00 on Date X.
    # Night range: 22h, 23h, 00h, 01h, 02h, 03h, 04h, 05h, 06h.
    
    # Group points by which "night" they belong to.
    # A point at T belongs to night starting at (T - 7 hours) .date() if hour <= 6
    # or T.date() if hour >= 22.
    
    night_data = {} # night_start_date -> list of (temp, hum)
    
    for t_str, temp, hum in zip(times, temps, humidities):
        t = datetime.strptime(t_str, "%Y-%m-%dT%H:%M")
        
        night_start_date = None
        if t.hour >= 22:
            night_start_date = t.date()
        elif t.hour <= 6:
            night_start_date = (t - timedelta(days=1)).date()
            
        if night_start_date:
            if night_start_date not in night_data:
                night_data[night_start_date] = []
            night_data[night_start_date].append({'temp': temp, 'hum': hum, 'time': t_str})
            
    # Now find the minimum for each night
    extracted_nights = []
    for d in sorted(night_data.keys()):
        points = night_data[d]
        if not points: continue
        
        # Coldest dry-bulb temperature
        min_point = min(points, key=lambda x: x['temp'])
        extracted_nights.append({
            'date': d, 
            'temp': min_point['temp'], 
            'humidity': min_point['hum']
        })
        
    return extracted_nights

def main():
    print("--- 1. FETCHING REAL DATA ---")
    data = fetch_data()
    # Print hourly arrays (truncated for readability if needed, but user said "at least the hourly arrays")
    print("HOURLY DATA ARRAYS:")
    print(json.dumps(data['hourly'], indent=2))
    print("\n")
    
    print("--- 2. EXTRACTING NIGHTTIME MINIMUMS ---")
    extracted = extract_nighttime_minimums(data)
    print("REAL EXTRACTED NIGHTTIME DATA:")
    for n in extracted:
        print(f"{{'date': {n['date']}, 'temp': {n['temp']}, 'humidity': {n['humidity']}}}")
    print("\n")
    
    scenarios = {
        "a) cooled home": {'ac': False, 'fan': True, 'windows_open': True,
                           'roof_material': 'concrete', 'floor_level': 'ground', 'occupants': 2},
        "b) high-risk home": {'ac': False, 'fan': False, 'windows_open': False,
                               'roof_material': 'tin', 'floor_level': 'top', 'occupants': 4}
    }
    
    for name, onboarding in scenarios.items():
        print(f"--- 3. RUNNING RDS CALCULATOR FOR SCENARIO: {name} ---")
        calculator = RDSCalculator(onboarding_data=onboarding)
        for n in extracted:
            calculator.add_night_temperature(n['temp'], date=n['date'], humidity=n['humidity'])
        
        # calculate_rds(debug=True) will print the breakdown via the logger
        results = calculator.calculate_rds(debug=True)
        
        print("\nFINAL RESULTS:")
        print(f"RDS Low: {results['rds_low']}")
        print(f"RDS Mid: {results['rds_mid']}")
        print(f"RDS High: {results['rds_high']}")
        print(f"Consecutive Nights: {results['consecutive_nights']}")
        print("-" * 40 + "\n")

if __name__ == "__main__":
    main()
