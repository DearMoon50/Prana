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
            
    extracted_nights = []
    # Sort dates to ensure consistent ordering (chronological)
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
    print("--- FETCHING REAL DATA ---")
    data = fetch_data()
    
    print("\n--- 1. RAW EXTRACTED NIGHTS (immediately after extraction) ---")
    extracted = extract_nighttime_minimums(data)
    for n in extracted:
        # Use string conversion for date to ensure clean representation
        n_copy = n.copy()
        n_copy['date'] = str(n_copy['date'])
        print(json.dumps(n_copy))
    
    print("\n--- 2. DATA FED INTO add_night_temperature() (sequential) ---")
    onboarding = {'ac': False, 'fan': False, 'windows_open': False,
                  'roof_material': 'tin', 'floor_level': 'top', 'occupants': 4}
    calculator = RDSCalculator(onboarding_data=onboarding)
    
    for n in extracted:
        n_copy = n.copy()
        n_copy['date'] = str(n_copy['date'])
        print(f"Feeding: {json.dumps(n_copy)}")
        calculator.add_night_temperature(n['temp'], date=n['date'], humidity=n['humidity'])
    
    print("\n--- 3. RDS CALCULATOR INTERNAL STATE (calculator.nighttime_temps) ---")
    for t in calculator.nighttime_temps:
        t_copy = t.copy()
        t_copy['date'] = str(t_copy['date'])
        print(json.dumps(t_copy))

    print("\n--- 4. FULL DEBUG RDS BREAKDOWN ---")
    results = calculator.calculate_rds(debug=True)
    
    print("\nFINAL RESULTS:")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
