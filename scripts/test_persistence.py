
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prana.database import init_db, SessionLocal, load_user_rds_state
from prana.models import User, UserProfile, RiskEvaluation, RDSState
from backend.main import app, RegisterRequest, HomeProfile, RiskRequest
from fastapi.testclient import TestClient

client = TestClient(app)

def run_test():
    print("\n" + "="*60)
    print("PRANA PERSISTENCE INTEGRATION TEST")
    print("="*60)

    # 1. Initialize DB
    init_db()
    db = SessionLocal()
    
    # Clean up previous test run if any
    db.query(RiskEvaluation).delete()
    db.query(RDSState).delete()
    db.query(UserProfile).delete()
    db.query(User).delete()
    db.commit()

    # 2. Register a user
    print("\nStep 1: Registering user '9999999999'...")
    reg_payload = {
        "phone": "9999999999",
        "location_name": "Dhaka, Bangladesh",
        "lat": 23.8103,
        "lon": 90.4125,
        "onboarding": {
            "ac": False,
            "roof_material": "tin",
            "floor_level": "top",
            "fan": False,
            "windows_open": False,
            "occupants": 1
        }
    }
    resp = client.post("/register", json=reg_payload)
    user_id = resp.json()["user_id"]
    print(f"User registered with ID: {user_id}")

    # 3. Simulate 3 consecutive hot nights
    # We'll manually call the calculation logic or use the API
    # Since the API fetches real weather, we'll mock the pipeline return in the test
    # or just manually inject records into the DB to simulate 'persistence'.
    
    print("\nStep 2: Simulating 3 consecutive hot nights (34C)...")
    base_date = datetime.now().date()
    historical_temps = []
    
    for i in range(3, 0, -1):
        night_date = base_date - timedelta(days=i)
        # 34C night with Tin roof on top floor = High RFU
        # (We bypass the API and just test the state reconstruction)
        historical_temps.append({'date': night_date, 'temp': 34.0, 'humidity': 80.0})

    from prana.database import save_user_rds_state
    save_user_rds_state(db, user_id, historical_temps)
    print(f"Saved {len(historical_temps)} historical nights to RDSState.")

    # 4. Run calculation for the 4th night
    print("\nStep 3: Running risk calculation for the 4th night (tonight)...")
    # We need to mock the system or ensure the system handles the 4th night
    # For this test, we'll check if load_user_rds_state works correctly
    
    reloaded_temps = load_user_rds_state(db, user_id)
    print(f"Reloaded {len(reloaded_temps)} nights from DB.")
    
    # 5. Verify the RDS Score reflects accumulation
    from prana.rds_calculator import RDSCalculator
    calc = RDSCalculator()
    calc.nighttime_temps = reloaded_temps
    
    # Add tonight (hot)
    calc.add_night_temperature(34.0, humidity=80.0)
    
    # Dhaka hot_humid zone: 34C/80% is extreme
    onb = reg_payload["onboarding"]
    res = calc.calculate_rds(onboarding_data=onb, climate_zone="hot_humid")
    
    print(f"Final RDS Score (accumulated): {res['rds_mid']}")
    
    if res['rds_mid'] > 80:
        print("\n[PASS] RDS correctly accumulated debt across persistent sessions.")
    else:
        print(f"\n[FAIL] Score too low ({res['rds_mid']}), debt not preserved?")
        sys.exit(1)

    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    run_test()
