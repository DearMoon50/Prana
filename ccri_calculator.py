"""Calculate Compound Climate Risk Index (CCRI)"""
from config import *

class CCRICalculator:
    def __init__(self):
        pass
    
    def calculate_heat_score(self, ndt):
        """
        Calculate heat component score (0-100)
        
        Based on WBGT/NDT thresholds
        
        Args:
            ndt: Neighbourhood Danger Temperature (degC)
        
        Returns:
            Heat score (0-100)
        """
        if ndt < 27:
            return self._linear_scale(ndt, 20, 27, 0, 20)
        elif ndt < 30:
            return self._linear_scale(ndt, 27, 30, 20, 40)
        elif ndt < 32:
            return self._linear_scale(ndt, 30, 32, 40, 60)
        elif ndt < 35:
            return self._linear_scale(ndt, 32, 35, 60, 80)
        else:
            return min(100, self._linear_scale(ndt, 35, 40, 80, 100))
    
    def calculate_pollution_score(self, ha_aqi):
        """
        Calculate air pollution component score (0-100)
        
        Based on HA-AQI values
        
        Args:
            ha_aqi: Heat-Amplified AQI
        
        Returns:
            Pollution score (0-100)
        """
        if ha_aqi is None:
            return 0  # Default if no AQI data
        
        if ha_aqi <= 50:
            return self._linear_scale(ha_aqi, 0, 50, 0, 20)
        elif ha_aqi <= 100:
            return self._linear_scale(ha_aqi, 50, 100, 20, 40)
        elif ha_aqi <= 150:
            return self._linear_scale(ha_aqi, 100, 150, 40, 60)
        elif ha_aqi <= 200:
            return self._linear_scale(ha_aqi, 150, 200, 60, 80)
        else:
            return min(100, self._linear_scale(ha_aqi, 200, 300, 80, 100))
    
    def calculate_ccri(self, ndt, ha_aqi, rds, debug=True):
        """
        Calculate Compound Climate Risk Index
        
        CCRI = (H_score x P_score) x (1 + RDS x 0.3)
        
        Multiplicative structure reflects synergistic mortality
        
        Args:
            ndt: Neighbourhood Danger Temperature (degC)
            ha_aqi: Heat-Amplified AQI
            rds: Recovery Debt Score
            debug: If True, print component scores
        
        Returns:
            CCRI value (0-100+) and risk level
        """
        h_score = self.calculate_heat_score(ndt)
        p_score = self.calculate_pollution_score(ha_aqi) if ha_aqi else 20  # Default moderate if no data
        
        # Base compound risk (multiplicative)
        base_ccri = (h_score * p_score) / 100  # Normalize to 0-100 scale
        
        # Amplify by recovery debt
        rds_multiplier = 1 + (rds / 100) * 0.3  # Max 30% amplification
        
        ccri = base_ccri * rds_multiplier
        
        # DEBUG OUTPUT
        if debug:
            print(f"\n{'='*60}")
            print("CCRI CALCULATION DEBUG")
            print(f"{'='*60}")
            print(f"Heat Score (H):        {h_score:.1f}/100  (from NDT {ndt:.1f} degC)")
            print(f"Pollution Score (P):   {p_score:.1f}/100  (from HA-AQI {ha_aqi if ha_aqi else 'N/A'})")
            if not ha_aqi:
                print(f"  WARNING: Using default P=20 (air quality data unavailable)")
            print(f"RDS:                   {rds:.1f}/100")
            print(f"\nBase CCRI = (H x P) / 100")
            print(f"          = ({h_score:.1f} x {p_score:.1f}) / 100")
            print(f"          = {base_ccri:.1f}")
            print(f"\nRDS Multiplier = 1 + (RDS/100) x 0.3")
            print(f"               = 1 + ({rds:.1f}/100) x 0.3")
            print(f"               = {rds_multiplier:.2f}x")
            print(f"\nFinal CCRI = {base_ccri:.1f} x {rds_multiplier:.2f}")
            print(f"           = {ccri:.1f}/100")
            print(f"{'='*60}\n")
        
        return ccri, self.get_risk_level(ccri)
    
    def get_risk_level(self, ccri):
        """
        Classify CCRI into risk levels
        
        Returns:
            Risk level and description
        """
        if ccri < CCRI_SAFE:
            return "SAFE", "No significant compound risk", "GREEN"
        elif ccri < CCRI_ELEVATED:
            return "ELEVATED", "Monitor conditions, vulnerable groups should be cautious", "YELLOW"
        elif ccri < CCRI_HIGH:
            return "HIGH", "Significant risk - limit outdoor exposure, check on vulnerable", "ORANGE"
        elif ccri < CCRI_CRITICAL:
            return "CRITICAL", "Dangerous conditions - avoid outdoor activity, activate support systems", "RED"
        else:
            return "COMPOUND EMERGENCY", "Life-threatening conditions - emergency protocols active", "CRITICAL"
    
    def _linear_scale(self, value, in_min, in_max, out_min, out_max):
        """Linear interpolation between ranges"""
        value = max(in_min, min(in_max, value))  # Clamp to range
        return out_min + (value - in_min) * (out_max - out_min) / (in_max - in_min)
    
    def generate_alert_message(self, ccri, risk_level, ndt, ha_aqi, rds_message, location_name="your area"):
        """
        Generate personalized alert message
        
        Args:
            ccri: CCRI value
            risk_level: Tuple (level, description, color)
            ndt: Neighbourhood Danger Temperature
            ha_aqi: Heat-Amplified AQI
            rds_message: Recovery debt message
            location_name: Name of ward/location
        
        Returns:
            Alert message string
        """
        level, desc, color = risk_level
        
        message = f"*** PRANA CLIMATE ALERT - {location_name}\n\n"
        message += f"Risk Level: {level} ({ccri:.1f}/100)\n"
        message += f"{desc}\n\n"
        message += f"*** Current Conditions:\n"
        message += f"- Heat Stress (NDT): {ndt:.1f} degC\n"
        
        if ha_aqi:
            message += f"- Air Quality (HA-AQI): {ha_aqi:.0f}\n"
        
        message += f"- Sleep Recovery: {rds_message}\n\n"
        
        # Specific guidance based on risk level
        if level == "SAFE":
            message += "[OK] Conditions are safe. Normal activities can continue."
        elif level == "ELEVATED":
            message += "WARNING: Stay hydrated. Vulnerable individuals should limit outdoor exposure."
        elif level == "HIGH":
            message += "WARNING: HIGH RISK:\n- Stay indoors during peak heat\n- Drink water frequently\n- Check on elderly neighbors"
        elif level == "CRITICAL":
            message += "[CRITICAL] CRITICAL:\n- Avoid outdoor work\n- Seek cool shelter\n- Emergency cooling centers open\n- Contact health workers if feeling unwell"
        else:  # COMPOUND EMERGENCY
            message += "[EMERGENCY] EMERGENCY:\n- STAY INDOORS\n- Activate emergency support\n- Health workers on alert\n- Reply HELP for immediate assistance"
        
        return message


