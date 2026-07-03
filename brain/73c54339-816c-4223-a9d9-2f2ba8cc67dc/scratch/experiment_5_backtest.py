
import json
import sys
import os

# Import the module to override its globals
import prana.rds_calculator

def run_rds(nights, onboarding, db_thr, wb_thr):
    # Override globals in the rds_calculator module
    prana.rds_calculator.RDS_NIGHTTIME_THRESHOLD = db_thr
    prana.rds_calculator.RDS_NIGHTTIME_WETBULB_THRESHOLD = wb_thr
    
    from prana.rds_calculator import RDSCalculator
    from datetime import date, timedelta
    
    calc = RDSCalculator(onboarding)
    # We want to see the score at the end of the month
    today = date(2026, 6, 30)
    
    # Sort nights by date to add them correctly
    for i in range(len(nights)):
        night_date = date(2026, 6, 1) + timedelta(days=i)
        # RDSCalculator internal sort handles reverse order
        calc.add_night_temperature(nights[i]["temp"], date=night_date, humidity=nights[i]["hum"])
        
    return calc.calculate_rds(debug=False)

def main():
    with open("city_nights_data.json", "r") as f:
        city_results = json.load(f)
    with open("zone_thresholds.json", "r") as f:
        zone_thresholds = json.load(f)
    with open("city_to_zone.json", "r") as f:
        city_to_zone = json.load(f)

    # Scenarios
    SCENARIOS = {
        "Cooled Home": {"ac": True, "roof_material": "concrete", "floor_level": "ground"},
        "High-Risk Home": {"ac": False, "roof_material": "tin", "floor_level": "top"}
    }
    
    # Defaults
    GLOBAL_DB = 32.0
    GLOBAL_WB = 28.0
    KARACHI_SPECIAL_DB = 30.0

    print("EXPERIMENT 5: BACKTEST RESULTS (Last Day RDS Mid)")
    print("-" * 140)
    print(f"{'City':<15} | {'Scenario':<15} | {'Old RDS':<8} | {'New RDS':<8} | {'% Diff':<8} | {'Zone'}")
    print("-" * 140)

    # We need to compute "Old" and "New" for every city
    for city_name, nights in city_results.items():
        zone = city_to_zone[city_name]
        new_thr = zone_thresholds[zone]
        
        for sc_name, onboarding in SCENARIOS.items():
            # Scenario 1: Global Baseline
            db_old = KARACHI_SPECIAL_DB if city_name == "Karachi" else GLOBAL_DB
            old_res = run_rds(nights, onboarding, db_old, GLOBAL_WB)
            old_val = old_res["rds_mid"]
            
            # Scenario 2: Zone-based
            new_res = run_rds(nights, onboarding, new_thr["db"], new_thr["wb"])
            new_val = new_res["rds_mid"]
            
            diff = 0
            if old_val > 0:
                diff = (new_val - old_val) / old_val * 100
            elif new_val > 0:
                diff = 100.0 if old_val == 0 else 0
            
            flag = "!" if abs(diff) > 15 else " "
            print(f"{city_name:<15} | {sc_name:<15} | {old_val:8.1f} | {new_val:8.1f} | {diff:7.1f}% {flag} | {zone}")

if __name__ == "__main__":
    sys.path.insert(0, os.getcwd())
    main()
