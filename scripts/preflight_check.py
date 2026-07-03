
"""
PRANA preflight check — verifies the RDS + onboarding integration is wired
correctly across config, calculator, system, and API schema.
"""
from __future__ import annotations
import sys
import os
from datetime import datetime, timedelta

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prana.config import *
from prana.recovery.model import RecoveryModel
from prana.prana_system import PRANASystem
from backend.main import app, HomeProfile, RiskRequest

PASS = "[PASS]"
FAIL = "[FAIL]"
_failures = []

def check(name: str, cond: bool, detail: str = "") -> None:
    line = f"  {PASS if cond else FAIL} {name}"
    if detail:
        line += f"  ({detail})"
    print(line)
    if not cond:
        _failures.append(name)

def section(title: str) -> None:
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)

def main() -> int:
    section("1. IMPORT CHAIN")
    check("prana.config imports", True)
    check("prana.recovery.model imports", True)

    section("2. CLIMATE-ZONE-AWARE PHYSICS (Simpson's Paradox Fix)")
    profile = {'roof_material': 'brick', 'floor_level': 'top'}
    # Dry zone: Top floor should be cooler (-1.02)
    off_dry = RecoveryModel.compute_onboarding_temp_offset(profile, outdoor_temp=30.0, climate_zone="hot_dry")
    check("Delhi (dry) top floor is COOLER", off_dry < 0, f"offset={off_dry}")
    
    # Humid zone: Top floor should be hotter (+0.92)
    off_humid = RecoveryModel.compute_onboarding_temp_offset(profile, outdoor_temp=30.0, climate_zone="hot_humid")
    check("Dhaka (humid) top floor is HOTTER", off_humid > 0, f"offset={off_humid}")
    
    # Defensive safety cap at 36C in dry zone
    off_dry_36 = RecoveryModel.compute_onboarding_temp_offset(profile, outdoor_temp=36.0, climate_zone="hot_dry")
    check("Safety cap: Cooling disabled at 36C", off_dry_36 >= 0, f"offset={off_dry_36}")

    section("3. SYSTEM WIRING (City Lookup)")
    sys_dhaka = PRANASystem(location_name="Dhaka, Bangladesh")
    sys_delhi = PRANASystem(location_name="New Delhi, India")
    sys_unknown = PRANASystem(location_name="Unknown")
    
    check("Dhaka resolved to hot_humid", sys_dhaka.climate_zone == "hot_humid")
    check("Delhi resolved to hot_dry", sys_delhi.climate_zone == "hot_dry")
    check("Unknown resolved to hot_humid (defensive default)", sys_unknown.climate_zone == "hot_humid")

    section("4. RDS END-TO-END IMPACT")
    # Dhaka (hot_humid) vs Delhi (hot_dry) on the same 30C/80% night
    nights_common = [(0, 30.0, 80.0)]
    onb = {'roof_material': 'brick', 'floor_level': 'top'}
    
    def get_rds(city_name):
        s = PRANASystem(location_name=city_name, onboarding_data=onb)
        # Use simple dry/humid to avoid API fetch issues for mock
        s.rds_calculator.add_night_temperature(30.0, humidity=80.0)
        # Manually trigger compute
        res = s.rds_calculator.calculate_rds(climate_zone=s.climate_zone)
        return res['rds_mid']

    dhaka_rds = get_rds("Dhaka")
    delhi_rds = get_rds("Delhi")
    check("Dhaka risk > Delhi risk for top floor", dhaka_rds > delhi_rds, f"dhaka={dhaka_rds} delhi={delhi_rds}")

    section("5. API SCHEMA & DEFAULTS")
    hp = HomeProfile(ac=False, roof_material='tin', floor_level='top', fan=True, windows_open=True, occupants=3)
    check("HomeProfile schema valid", hp.fan is True and hp.occupants == 3)

    section("6. RESULT")
    if _failures:
        print(f"  {FAIL} {len(_failures)} check(s) failed.")
        return 1
    print(f"  {PASS} All checks passed. PRANA is now climate-zone aware.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
