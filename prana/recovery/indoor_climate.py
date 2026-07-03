"""Outdoor night temperature -> effective indoor sleeping temperature.

Reuses the fitted South-Asia envelope coefficients (RDS_CLIMATE_ZONE_COEFFS) and
wires the ASHRAE Global Thermal Comfort DB II AC finding as a temp-dependent
offset, replacing the flat -3.0 AC assumption.
"""
from prana.config import (
    RDS_CLIMATE_ZONE_COEFFS,
    RDS_ONBOARDING_FAN_OFFSET,
    RDS_ONBOARDING_WINDOW_OFFSET,
    RDS_ONBOARDING_PER_EXTRA_OCCUPANT_OFFSET,
    RDS_INDOOR_OFFSET_BAND_WIDTH,
    RDS_AC_EXTRA_BAND_WIDTH,
    RDS_ASHRAE_AC_BASELINE,
    RDS_ASHRAE_AC_INTERACTION,
)


def ashrae_ac_offset(outdoor_temp) -> float:
    """Effective indoor cooling from AC, temp-dependent (ASHRAE DB II).

    baseline + interaction * T. ~-3.5C at 30C outdoor, widening with heat.
    """
    T = float(outdoor_temp if outdoor_temp is not None else 25.0)
    return RDS_ASHRAE_AC_BASELINE + RDS_ASHRAE_AC_INTERACTION * T


def compute_onboarding_temp_offset(onboarding_data, outdoor_temp=None, climate_zone="default") -> float:
    """Effective indoor temperature offset from onboarding categorical inputs.

    Same signature and semantics as the legacy RDSCalculator static method, with
    the AC term upgraded from a flat -3.0 to the temp-dependent ASHRAE curve.
    """
    if not onboarding_data:
        return 0.0
    offset = 0.0
    T = float(outdoor_temp if outdoor_temp is not None else 25.0)

    # Cooling devices
    if onboarding_data.get('ac'):
        offset += ashrae_ac_offset(T)
    if onboarding_data.get('fan'):
        offset += RDS_ONBOARDING_FAN_OFFSET
    if onboarding_data.get('windows_open'):
        offset += RDS_ONBOARDING_WINDOW_OFFSET

    # Building envelope (climate-zone-aware, temperature-dependent)
    zone_cfg = RDS_CLIMATE_ZONE_COEFFS.get(climate_zone, RDS_CLIMATE_ZONE_COEFFS["default"])

    roof = str(onboarding_data.get('roof_material', 'brick')).lower()
    roof_cfg = zone_cfg["roof"].get(roof, zone_cfg["roof"].get('brick', {"baseline": 0.0, "interaction": 0.0}))
    offset += roof_cfg['baseline'] + (roof_cfg['interaction'] * T)

    floor = str(onboarding_data.get('floor_level', '')).lower()
    if floor == 'top':
        f_off = zone_cfg["floor"].get("top", 0.0)
        # Longwave sky cooling breaks down under extreme heat: cap cooling at 0 above 35C.
        if T > 35.0 and f_off < 0:
            f_off = 0.0
        offset += f_off

    # Structural cooling cannot physically zero out an extreme air mass.
    offset = max(offset, -4.0)

    # Occupancy (metabolic heat load)
    try:
        occupants = int(onboarding_data.get('occupants', 1) or 1)
    except (TypeError, ValueError):
        occupants = 1
    if occupants > 1:
        offset += (occupants - 1) * RDS_ONBOARDING_PER_EXTRA_OCCUPANT_OFFSET

    return round(offset, 2)


def compute_band_width(onboarding_data) -> float:
    """Half-width of the indoor-offset uncertainty band. AC widens it."""
    width = RDS_INDOOR_OFFSET_BAND_WIDTH
    if onboarding_data and onboarding_data.get('ac'):
        width += RDS_AC_EXTRA_BAND_WIDTH
    return width


def effective_indoor_temp(outdoor_temp, offset) -> float:
    """Effective indoor sleeping temperature = outdoor night min + offset."""
    return outdoor_temp + offset
