import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path so we can import prana
sys.path.append(os.getcwd())

from prana.rds_calculator import RDSCalculator
from backend.database import load_nighttime_temps

def main():
    lat, lon = 13.0827, 80.2707
    print(f"Calculating RDS for Chennai ({lat}, {lon})")
    
    # Load stored data
    temps = load_nighttime_temps(lat, lon)
    if not temps:
        print("No historical data found for Chennai.")
        return
        
    print(f"Found {len(temps)} night(s) of historical data.")
    for t in temps:
        print(f"  {t['date']}: {t['temp']}C ({t.get('humidity', 'N/A')}% humidity)")
        
    # Initialize calculator
    # Using some default onboarding data to see potential offsets
    onboarding = {
        'ac': False,
        'fan': False,
        'windows_open': False,
        'roof_material': 'tin',
        'floor_level': 'top',
        'occupants': 4
    }
    
    calc = RDSCalculator(onboarding_data=onboarding)
    for t in temps:
        calc.add_night_temperature(t['temp'], date=t['date'], humidity=t.get('humidity'))
        
    # Calculate RDS
    rds_dict = calc.calculate_rds(debug=True)
    
    print("\nRDS Calculation Result:")
    print(json.dumps(rds_dict, indent=2))
    
    # Get message
    message, color = calc.get_rds_message(rds_dict)
    print(f"\nMessage: {message}")
    print(f"Color: {color}")

if __name__ == "__main__":
    main()
