
import json
import numpy as np

# Load data from Exp 3
with open("city_nights_data.json", "r") as f:
    city_results = json.load(f)

# Grouping
ZONES = {
    "Hot Arid/Semi-Arid (Coastal)": ["Karachi"],
    "Humid Tropical (High Heat)": ["Chennai", "Dhaka", "Manila", "Ho Chi Minh City"],
    "Humid Tropical (Moderate Heat)": ["Jakarta"]
}

# Rule: threshold = zone's 75th percentile nighttime wet-bulb temp, rounded to nearest 0.5
# Dry threshold = Wet threshold + 4.0

CURRENT_DB = 32.0
CURRENT_WB = 28.0

def round_to_05(n):
    return round(n * 2) / 2

print("EXPERIMENT 4: DERIVING THRESHOLDS")
print("-" * 100)
print(f"{'Zone':<35} | {'P75 WB':<8} | {'New DB':<8} | {'New WB':<8} | {'Old DB/WB':<10} | {'Nights Crossed (New)':<20}")
print("-" * 100)

zone_thresholds = {}

for zone_name, cities in ZONES.items():
    pooled_temps = []
    pooled_wbs = []
    for city in cities:
        for night in city_results[city]:
            pooled_temps.append(night["temp"])
            pooled_wbs.append(night["wb"])
            
    p75_wb = np.percentile(pooled_wbs, 75)
    new_wb = round_to_05(p75_wb)
    new_db = new_wb + 4.0
    
    zone_thresholds[zone_name] = {"db": new_db, "wb": new_wb}
    
    # Count nights crossed
    crossed = 0
    total = len(pooled_temps)
    for t, wb in zip(pooled_temps, pooled_wbs):
        if t > new_db or wb > new_wb:
            crossed += 1
            
    print(f"{zone_name:<35} | {p75_wb:7.2f}C | {new_db:7.1f}C | {new_wb:7.1f}C | {CURRENT_DB}/{CURRENT_WB} | {crossed}/{total} ({100*crossed/total:.1f}%)")

# Save thresholds for Exp 5
with open("zone_thresholds.json", "w") as f:
    json.dump(zone_thresholds, f)

# Map cities to zones for Exp 5
city_to_zone = {}
for zone, cities in ZONES.items():
    for city in cities:
        city_to_zone[city] = zone
with open("city_to_zone.json", "w") as f:
    json.dump(city_to_zone, f)
