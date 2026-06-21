# PRANA - Asia's First Compound Climate Emergency Platform

Compound heat-ozone exposure in Asian cities increased 67% over 18 years (Liu et al., 2025), yet no platform treats these threats as one system. PRANA fuses neighbourhood heat stress, thermally-amplified air quality, and nighttime recovery debt into a ward-level Compound Climate Risk Index, delivering personalised survival alerts.

---

## Quick Component Overview

| Component | File | What It Measures | Data Source | Output |
|-----------|------|-----------------|-------------|---------|
| **NDT** | `ndt_calculator.py` | Heat stress in your neighborhood (not airport) | OpenWeatherMap | 32.9°C (VERY HIGH) |
| **HA-AQI** | `ha_aqi_calculator.py` | Air quality corrected for thermal chemistry | OpenAQ monitors | 210 (VERY UNHEALTHY) |
| **RDS** | `rds_calculator.py` | Cumulative sleep debt from hot nights | Weather forecast | 66.1 (HIGH debt) |
| **CCRI** | `ccri_calculator.py` | Compound risk (multiplies all three) | NDT + HA-AQI + RDS | 64.7/100 (CRITICAL) |

**Geographic Scope:**
- **NDT:** Individual person (your exact coordinates)
- **HA-AQI:** Street/neighborhood (2-10 km from nearest air quality monitor)
- **RDS:** Individual person (your forecast + your sleep history)
- **CCRI:** Individual person (personalized compound risk)

---

## The Problem

Three threats compound into exponential mortality risk:

1. **Urban Heat Islands**: Low-income wards run 3–4°C hotter than airport reference points, carrying 26–45% higher heat mortality risk
2. **Thermal Chemistry**: At 42°C, ozone forms 2.1–2.4× faster — a ward showing AQI 120 at 9am reaches effective AQI 200+ by 3pm
3. **Sleep Deprivation**: Every 10°C rise in nighttime temperature increases sleep insufficiency by 20.1% (Obradovich et al., 2017) — the body never recovers above 32°C at night, making Day 5 mortality risk exponentially higher than Day 1

---

## How PRANA Works: Complete Pipeline

PRANA runs a **7-step pipeline** every 3 hours to calculate your compound climate risk:

```
Current Weather → Forecast → NDT → Air Quality → HA-AQI → RDS → CCRI → Alert
```

Each component feeds into the next, building from raw data to personalized survival guidance.

---

## The Four Core Components (Detailed)

### 1. NDT — Neighbourhood Danger Temperature

**File:** `ndt_calculator.py`

**What It Does:**  
Calculates the **actual heat stress your body experiences** in your specific neighborhood, not the temperature reported by distant airport weather stations.

**Why It Matters:**  
Weather stations are at airports (open, windy, green spaces). Low-income urban wards are 3-4°C hotter due to concrete, lack of trees, and density. Standard weather reports lie to the poor.

**How It Works:**

1. **Gets weather data** from OpenWeatherMap API:
   - Air temperature (dry bulb)
   - Humidity (to calculate wet bulb temperature)
   - Wind speed
   - Atmospheric pressure

2. **Calculates WBGT** (Wet Bulb Globe Temperature) using ISO 7243 standard:
   ```
   WBGT = 0.7 × Wet_Bulb_Temp + 0.2 × Globe_Temp + 0.1 × Dry_Bulb_Temp
   ```
   - **Wet bulb temperature**: What a thermometer covered in wet cloth reads (evaporative cooling)
   - **Globe temperature**: Black sphere temperature (radiant heat)
   - **Dry bulb temperature**: Regular air temperature

3. **Adds urban heat island offset** (2-4°C depending on your ward):
   ```
   NDT = WBGT + urban_heat_offset
   ```

4. **Outputs heat stress level:**
   - Below 27°C: SAFE
   - 27-32°C: MODERATE (caution for prolonged outdoor work)
   - 32-35°C: HIGH (limit strenuous activity)
   - 35-39°C: VERY HIGH (extreme caution, frequent breaks)
   - Above 39°C: EXTREME (emergency conditions, avoid outdoor work)

**Data Source:**  
OpenWeatherMap API → nearest weather station to your coordinates (free tier: 1000 calls/day)

**Geographic Scope:**  
Individual person level - uses YOUR exact coordinates (auto-detected via IP or manually entered)

**Example Output:**
```
NDT: 34.6°C
Heat Stress: VERY HIGH - Extreme caution - limit outdoor activity
```

---

### 2. HA-AQI — Heat-Amplified Air Quality Index

**File:** `ha_aqi_calculator.py`

**What It Does:**  
Corrects the official Air Quality Index (AQI) for **thermal chemistry** — the fact that ozone and other pollutants form faster at higher temperatures. The AQI reading at 9am is not the AQI at 3pm on a hot day.

**Why It Matters:**  
Standard AQI ignores temperature. At 42°C, ozone forms 2.1-2.4× faster than at 25°C. A ward showing "Moderate" AQI (100) at morning can hit "Very Unhealthy" (200+) by afternoon purely from heat accelerating chemistry.

**How It Works:**

1. **Gets base pollutant readings** from OpenAQ API v3:
   - PM2.5 (fine particulate matter)
   - PM10 (coarse particulate matter)
   - O3 (ozone)
   - CO (carbon monoxide)
   - NO2 (nitrogen dioxide)
   - SO2 (sulfur dioxide)

2. **Converts pollutants to EPA AQI standard** using breakpoint tables:
   - Each pollutant has concentration ranges that map to AQI values
   - Example: PM2.5 of 85 µg/m³ = AQI 166 (Unhealthy)
   - Takes the WORST pollutant as the base AQI

3. **Calculates Ozone Amplification Factor (OAF)**:
   ```
   OAF = 1 + 0.04 × max(0, Temperature - 25°C)
   ```
   - At 25°C: OAF = 1.0 (no amplification)
   - At 30°C: OAF = 1.2 (20% worse)
   - At 35°C: OAF = 1.4 (40% worse)
   - At 42°C: OAF = 1.68 (68% worse)
   
   Based on Shen et al. (2020) atmospheric chemistry research.

4. **Applies thermal amplification**:
   ```
   HA-AQI = Base_AQI × OAF
   ```

5. **Forecasts next 6 hours** by applying OAF to temperature forecast:
   - Shows how AQI will worsen as day heats up
   - Critical for planning outdoor work/travel

6. **Outputs health categories:**
   - 0-50: GOOD (green)
   - 51-100: MODERATE (yellow)
   - 101-150: UNHEALTHY FOR SENSITIVE (orange)
   - 151-200: UNHEALTHY (red)
   - 201-300: VERY UNHEALTHY (purple)
   - 301+: HAZARDOUS (maroon)

**Data Source:**  
OpenAQ v3 API → searches for monitors within 25km radius, uses nearest station with ozone data (free tier: unlimited)

**Geographic Scope:**  
Street/neighborhood level - depends on monitor location (typically 2-10 km radius per monitor in Indian cities)

**Example Output:**
```
Base AQI: 166 (from PM2.5)
OAF: 1.26× at 31.6°C
HA-AQI: 210 (VERY UNHEALTHY)

Forecast:
  20:30: Temp 31.6°C → HA-AQI 210 (OAF: 1.26×)
  23:30: Temp 30.9°C → HA-AQI 205 (OAF: 1.23×)
```

**Key Innovation:**  
PRANA is the **first public platform** to apply real-time thermal chemistry correction to AQI using published formulas. Government AQI reports are static snapshots that ignore heat amplification.

---

### 3. RDS — Recovery Debt Score

**File:** `rds_calculator.py`

**What It Does:**  
Tracks **cumulative sleep deprivation** from hot nights over the past 7 days. Your body cannot recover when bedroom temperature stays above 32°C at night. This debt compounds — Day 5 risk is exponentially higher than Day 1.

**Why It Matters:**  
Heat mortality isn't instant. A 35°C day with good sleep is survivable. Five consecutive nights above 32°C with no recovery is deadly. Obradovich et al. (2017) found every 10°C rise in nighttime temperature increases sleep insufficiency by 20.1%. Lancet Countdown 2025 added nighttime sleep loss as an official health indicator.

**How It Works:**

1. **Estimates tonight's minimum temperature** from weather forecast:
   - Looks at forecast points during night hours (10 PM - 6 AM)
   - Finds the lowest temperature in that window
   - Typically 2-3 data points (OpenWeatherMap free tier = 3-hour intervals)
   - Notes accuracy limitation: ±1°C due to sparse sampling

2. **Tracks last 7 nights** in memory:
   - Stores date and minimum temperature for each night
   - Automatically keeps only most recent 7 days
   - Adds tonight's forecast as the newest entry

3. **Calculates Recovery Failure Units (RFU)** for each night:
   ```
   If night_temp < 32°C:  RFU = 0  (full recovery possible)
   If night_temp ≥ 32°C:  RFU = (temp_excess / 10) × 100
   ```
   - 32°C threshold from sleep research (body can't recover above this)
   - Example: 36°C night → excess = 4°C → RFU = 40
   - Example: 28°C night → excess = 0°C → RFU = 0

4. **Applies exponential decay** (recent nights matter more):
   ```
   RDS = Σ(RFU × 0.8^days_ago)
   ```
   - Tonight: weight = 1.0 (full impact)
   - Yesterday: weight = 0.8 (80% impact)
   - 2 days ago: weight = 0.64 (64% impact)
   - 3 days ago: weight = 0.512 (51% impact)
   - etc.

5. **Counts consecutive hot nights** (≥32°C):
   - Used in alert messages to explain severity
   - Example: "3 consecutive hot nights"

6. **Generates honest range-based message**:
   - We don't know your indoor temperature (could be cooler or hotter than outdoor)
   - Message explains outdoor temp and what it means for RDS
   - Example: "Tonight 28°C allows recovery, but past debt lingers"

**RDS Scale:**
- 0-10: LOW (well-rested, no debt)
- 10-30: MODERATE (minor debt accumulating)
- 30-80: HIGH (significant sleep deprivation)
- 80-150: VERY HIGH (severe cumulative debt)
- 150+: CRITICAL (emergency exhaustion levels)

**Data Source:**  
OpenWeatherMap Forecast API → nighttime temperature predictions for next 24-48 hours

**Geographic Scope:**  
Individual person level - uses YOUR coordinates

**Example Output:**
```
Tonight's estimated minimum: 27.8°C
  Note: Only 2 samples across night - actual minimum may differ by ~1°C

RDS Calculation Breakdown:
Date         Temp     RFU      Days Ago   Weight     Contribution
----------------------------------------------------------------------
2026-06-20   27.8°C     0.0          0      1.000          0.0
2026-06-19   36.1°C    41.0          1      0.800         32.8
2026-06-18   35.2°C    32.0          2      0.640         20.5
2026-06-17   34.5°C    25.0          3      0.512         12.8
----------------------------------------------------------------------
Total RDS: 66.1
Consecutive nights ≥32°C: 3 (not counting tonight if below threshold)

Recovery debt: HIGH (RDS: 66.1 from 3 consecutive hot nights — 
tonight cooler at 27.8°C but cumulative sleep debt remains)
```

**Key Innovation:**  
**Range-based output** acknowledges we don't measure indoor temperature. Honest communication: "outdoor temp was 33°C — if your home stayed above 32°C, partial recovery failure." First system to track **cumulative sleep debt** over days, not just current night.

---

### 4. CCRI — Compound Climate Risk Index

**File:** `ccri_calculator.py`

**What It Does:**  
Combines NDT (heat stress), HA-AQI (air pollution), and RDS (sleep debt) into a **single 0-100 risk score** using multiplicative math that reflects how these threats amplify each other.

**Why It Matters:**  
Heat + pollution + sleep deprivation don't just add — they multiply. Gasparrini & Armstrong (2011) showed mortality follows compound exponential curves, not linear addition. A person with 3 days of bad sleep facing 38°C heat and AQI 200 is at **exponentially higher risk** than someone well-rested in the same conditions.

**How It Works:**

1. **Converts NDT to Heat Score (0-100)**:
   ```
   Below 27°C:  H = 0 (safe)
   27-32°C:     H = 0-40 (linear interpolation)
   32-39°C:     H = 40-80 (linear interpolation)
   Above 39°C:  H = 80-100 (extreme)
   ```

2. **Converts HA-AQI to Pollution Score (0-100)**:
   ```
   AQI bands mapped to scores:
   0-50:     P = 0-10 (good)
   50-100:   P = 10-30 (moderate)
   100-150:  P = 30-50 (unhealthy for sensitive)
   150-200:  P = 50-80 (unhealthy)
   200-300:  P = 80-100 (very unhealthy)
   300+:     P = 100 (hazardous)
   ```
   Uses linear interpolation within each band.

3. **Calculates base CCRI** (multiplicative, not additive):
   ```
   Base_CCRI = (H_score × P_score) / 100
   ```
   This is the key: multiplication means both threats must be present for high risk.
   - High heat + low pollution = moderate risk
   - Low heat + high pollution = moderate risk
   - High heat + high pollution = CRITICAL risk

4. **Applies RDS multiplier** (sleep debt amplification):
   ```
   RDS_multiplier = 1 + (RDS/100) × 0.3
   ```
   - RDS = 0: multiplier = 1.0× (no amplification)
   - RDS = 50: multiplier = 1.15× (15% worse)
   - RDS = 100: multiplier = 1.3× (30% worse)

5. **Final CCRI**:
   ```
   CCRI = Base_CCRI × RDS_multiplier
   ```

6. **Outputs risk level and personalized guidance**:
   - **0-20: SAFE** (Green)
     - Normal activities okay
     - Standard precautions

   - **20-40: ELEVATED** (Yellow)
     - Reduce outdoor exposure
     - Monitor vulnerable individuals

   - **40-60: HIGH** (Orange)
     - Stay indoors during peak heat
     - Drink water frequently
     - Check on elderly neighbors

   - **60-80: CRITICAL** (Red)
     - Avoid outdoor work
     - Seek cool shelter
     - Emergency cooling centers open
     - Contact health workers if unwell

   - **80+: COMPOUND EMERGENCY** (Maroon)
     - Do not go outside
     - Activate emergency response
     - Community-wide health alert
     - Hospital surge preparedness

**Data Sources:**  
Integrates all three upstream components (NDT + HA-AQI + RDS)

**Geographic Scope:**  
Individual person level - personalized to YOUR exact conditions and sleep history

**Example Output:**
```
CCRI CALCULATION DEBUG
============================================================
Heat Score (H):        65.8/100  (from NDT 32.9°C)
Pollution Score (P):   82.1/100  (from HA-AQI 210)
RDS:                   66.1/100

Base CCRI = (H × P) / 100
          = (65.8 × 82.1) / 100
          = 54.0

RDS Multiplier = 1 + (RDS/100) × 0.3
               = 1 + (66.1/100) × 0.3
               = 1.20×

Final CCRI = 54.0 × 1.20
           = 64.7/100
============================================================

Risk Level: CRITICAL (64.7/100)
Dangerous conditions - avoid outdoor activity, activate support systems
```

**Key Innovation:**  
**Multiplicative structure** (not additive) reflects synergistic mortality mechanisms from epidemiological research. **RDS amplification** implements Obradovich's sleep deprivation findings. First platform combining all three threats into one actionable score.

---
---

## Supporting Components (Detailed)

### location_detector.py — Auto-Location Detection

**What It Does:**  
Automatically detects your current location using your IP address, so you don't need to manually enter coordinates.

**How It Works:**
1. Tries primary service (ipapi.co)
2. Falls back to backup (ip-api.com) if primary fails
3. Returns latitude, longitude, city, region, country

**Example Output:**
```
Detecting your location...
[OK] Location detected: Chennai, India
     Coordinates: 13.0895, 80.2739
```

**Data Source:** IP geolocation services (free, no API key needed)

---

### data_fetcher.py — API Integration Hub

**What It Does:**  
Handles all communication with external APIs (OpenWeatherMap, OpenAQ). Fetches weather, forecast, and air quality data.

**Key Functions:**

1. **get_current_weather(lat, lon)**
   - Fetches current temperature, humidity, wind, pressure
   - Returns: `{temp, humidity, wind_speed, pressure, timestamp}`

2. **get_forecast(lat, lon, hours=24)**
   - Fetches 3-hour interval forecasts
   - Returns list of: `{timestamp, temp, humidity, wind_speed, pressure}`

3. **get_air_quality(lat, lon)**
   - Searches OpenAQ monitors within 25km radius
   - Finds nearest station with ozone data
   - Fetches measurements from all sensors at that station
   - Converts units (µg/m³ → ppm for gases)
   - Returns: `{pm25, pm10, o3, co, no2, so2}`

4. **calculate_aqi_from_pollutants(pollutants)**
   - Applies EPA AQI breakpoint tables per pollutant
   - PM2.5, O3, CO, NO2, SO2 each have specific ranges
   - Returns highest (worst) AQI among all pollutants
   - Example: PM2.5=166, O3=5, CO=42 → returns 166

**Data Sources:**
- OpenWeatherMap API (weather + forecast)
- OpenAQ v3 API (air quality monitors)

**Units Conversion Critical:**
```
CO:  µg/m³ ÷ 1150 = ppm
O3:  µg/m³ ÷ 2000 = ppm  
NO2: µg/m³ ÷ 1.88 = ppb
```

---

### config.py — Configuration & Constants

**What It Does:**  
Centralized configuration file with all thresholds, API endpoints, and scientific constants.

**Key Settings:**

```python
# API Keys (loaded from .env)
OPENWEATHER_API_KEY
OPENAQ_API_KEY

# WBGT Coefficients (ISO 7243 standard)
WBGT_TW_COEFF = 0.7  # Wet bulb weight
WBGT_TG_COEFF = 0.2  # Globe temperature weight
WBGT_TD_COEFF = 0.1  # Dry bulb weight

# Ozone Amplification (Shen et al. 2020)
OAF_BASE_TEMP = 25.0      # Celsius baseline
OAF_COEFFICIENT = 0.04     # 4% per degree

# Recovery Debt Score
RDS_NIGHTTIME_THRESHOLD = 32.0   # No recovery above this
RDS_DECAY_FACTOR = 0.8           # Exponential decay
RDS_MAX_DAYS = 7                 # Track last 7 nights

# CCRI Risk Thresholds
CCRI_SAFE = 20
CCRI_ELEVATED = 40
CCRI_HIGH = 60
CCRI_CRITICAL = 80
# Above 80 = COMPOUND EMERGENCY

# Update frequency
UPDATE_INTERVAL = 3  # hours
```

---

### prana_system.py — Main Integration System

**What It Does:**  
Orchestrates the complete 7-step pipeline, coordinating all components and generating final alerts.

**The Complete Pipeline:**

```
Step 1: Fetch current weather data
   ↓
Step 2: Fetch weather forecast (24 hours)
   ↓
Step 3: Calculate NDT (WBGT + urban heat island)
   ↓
Step 4: Fetch air quality data from monitors
   ↓  
Step 5: Calculate HA-AQI (thermal chemistry correction)
   ↓
Step 6: Calculate RDS (sleep debt from forecast + history)
   ↓
Step 7: Calculate CCRI (compound risk) and generate alert
```

**Key Methods:**

1. **`__init__(api_key, location_name, urban_heat_offset, openaq_api_key)`**
   - Initialize system with API keys
   - Set urban heat offset (2-4°C for your ward)

2. **`update_all(lat, lon)`**
   - Runs complete 7-step pipeline
   - Returns full result dictionary with all metrics
   - Prints detailed debug output at each step

3. **`add_historical_night_temp(night_temp, date)`**
   - Manually add past night temperatures for RDS tracking
   - Useful for initializing system with historical data

4. **`get_status_summary()`**
   - Quick status check showing last update time and current metrics

**Example Usage:**
```python
prana = PRANASystem(
    api_key="your_key",
    location_name="Chennai, Tamil Nadu",
    urban_heat_offset=3.0,
    openaq_api_key="your_openaq_key"
)

# Add historical nights (optional)
prana.add_historical_night_temp(34.5, "2026-06-17")
prana.add_historical_night_temp(35.2, "2026-06-18")

# Run complete update
result = prana.update_all(lat=13.08, lon=80.27)

# Get alert message for WhatsApp
alert = result['alert_message']
```

---

## Complete Data Flow

Here's exactly what happens when you run PRANA:

### INPUT: Your Location
```
Latitude: 13.0895
Longitude: 80.2739
```

### STEP 1: Weather Data Fetch
```
OpenWeatherMap API Call:
→ Temperature: 31.6°C
→ Humidity: 78%
→ Wind Speed: 3.5 m/s
→ Pressure: 1008 hPa
```

### STEP 2: Weather Forecast Fetch
```
OpenWeatherMap Forecast API:
→ 8 data points (next 24 hours, 3-hour intervals)
→ Each point: timestamp, temp, humidity, wind, pressure
```

### STEP 3: NDT Calculation
```
Input: Weather data + urban_heat_offset (3.0°C)
Process:
  1. Calculate wet bulb temp from humidity
  2. Estimate globe temp from radiation
  3. Apply WBGT formula
  4. Add urban heat offset
Output: NDT = 32.9°C (VERY HIGH heat stress)
```

### STEP 4: Air Quality Data Fetch
```
OpenAQ API Call:
→ Search monitors within 25km
→ Found: Alandur Bus Depot (ID: 378), 5.2 km away
→ Sensors: pm25, o3, co, no2, so2

Measurements:
→ PM2.5: 85.1 µg/m³
→ O3: 11.08 µg/m³ (= 0.006 ppm)
→ CO: 4250.0 µg/m³ (= 3.70 ppm)
→ NO2: 10.51 µg/m³ (= 5.6 ppb)
→ SO2: 5.55 µg/m³
```

### STEP 5: HA-AQI Calculation
```
Input: Pollutants + current temperature (31.6°C)
Process:
  1. Convert each pollutant to AQI:
     - PM2.5: 85.1 µg/m³ → AQI 166
     - O3: 0.006 ppm → AQI 5
     - CO: 3.70 ppm → AQI 42
     - NO2: 5.6 ppb → AQI 5
  2. Base AQI = 166 (worst pollutant: PM2.5)
  3. Calculate OAF = 1 + 0.04×(31.6-25) = 1.26
  4. HA-AQI = 166 × 1.26 = 210
Output: HA-AQI = 210 (VERY UNHEALTHY)
```

### STEP 6: RDS Calculation
```
Input: Forecast + historical nights
Process:
  1. Extract tonight's minimum from forecast:
     - 02:30: 28.1°C
     - 05:30: 27.8°C
     - Minimum: 27.8°C
  2. Combine with historical nights:
     - 2026-06-20 (tonight): 27.8°C → RFU = 0.0
     - 2026-06-19: 36.1°C → RFU = 41.0 × 0.8^1 = 32.8
     - 2026-06-18: 35.2°C → RFU = 32.0 × 0.8^2 = 20.5
     - 2026-06-17: 34.5°C → RFU = 25.0 × 0.8^3 = 12.8
  3. Sum: 0.0 + 32.8 + 20.5 + 12.8 = 66.1
Output: RDS = 66.1 (HIGH recovery debt)
        3 consecutive hot nights before today
```

### STEP 7: CCRI Calculation
```
Input: NDT (32.9), HA-AQI (210), RDS (66.1)
Process:
  1. Heat Score = 65.8/100 (from NDT 32.9°C)
  2. Pollution Score = 82.1/100 (from HA-AQI 210)
  3. Base CCRI = (65.8 × 82.1) / 100 = 54.0
  4. RDS Multiplier = 1 + (66.1/100) × 0.3 = 1.20
  5. Final CCRI = 54.0 × 1.20 = 64.7
Output: CCRI = 64.7/100 (CRITICAL risk)
```

### FINAL OUTPUT: Personalized Alert
```
*** PRANA CLIMATE ALERT - Chennai, Tamil Nadu, India

Risk Level: CRITICAL (64.7/100)
Dangerous conditions - avoid outdoor activity, activate support systems

*** Current Conditions:
• Heat Stress (NDT): 32.9°C
• Air Quality (HA-AQI): 210
• Sleep Recovery: HIGH (RDS: 66.1 from 3 consecutive hot nights — 
  tonight cooler at 27.8°C but cumulative sleep debt remains)

[CRITICAL] CRITICAL:
• Avoid outdoor work
• Seek cool shelter
• Emergency cooling centers open
• Contact health workers if feeling unwell
```

---

## How to Run PRANA

### Option 1: Quick Demo (Simplest)

Just run the main file - it auto-detects your location and runs the full pipeline:

```bash
python prana_system.py
```

This will:
1. Auto-detect your location via IP
2. Fetch weather, forecast, and air quality data
3. Calculate NDT, HA-AQI, RDS, and CCRI
4. Print detailed step-by-step output
5. Show final personalized alert

### Option 2: Python Integration (For Your App)

```python
from prana_system import PRANASystem
from location_detector import get_current_location
from datetime import datetime, timedelta

# Step 1: Get location
location = get_current_location()
lat, lon = location['lat'], location['lon']

# Step 2: Initialize PRANA
prana = PRANASystem(
    api_key="your_openweather_api_key",
    location_name=f"{location['city']}, {location['country']}",
    urban_heat_offset=3.0,  # 2-4°C for urban areas
    openaq_api_key="your_openaq_api_key"
)

# Step 3: (Optional) Add historical night temperatures
# This improves RDS accuracy by tracking past sleep debt
today = datetime.now().date()
prana.add_historical_night_temp(34.5, today - timedelta(days=3))
prana.add_historical_night_temp(35.2, today - timedelta(days=2))
prana.add_historical_night_temp(36.1, today - timedelta(days=1))

# Step 4: Run complete assessment
result = prana.update_all(lat, lon)

# Step 5: Use the results
if result:
    print(f"CCRI Risk Score: {result['ccri']:.1f}/100")
    print(f"Risk Level: {result['risk_level']}")
    print(f"\nFull Alert:\n{result['alert_message']}")
    
    # Access individual metrics
    print(f"\nDetailed Metrics:")
    print(f"  NDT: {result['ndt']:.1f}°C ({result['heat_level']})")
    print(f"  HA-AQI: {result['ha_aqi']:.0f}")
    print(f"  RDS: {result['rds']:.1f}")
    print(f"  {result['rds_message']}")
```

### Option 3: Custom Location

```python
from prana_system import PRANASystem

prana = PRANASystem(
    api_key="your_key",
    location_name="Tondiarpet Ward, Chennai",
    urban_heat_offset=3.5,  # Higher for low-income wards
    openaq_api_key="your_openaq_key"
)

# Manually specify coordinates
result = prana.update_all(lat=13.1143, lon=80.2873)
```

---

### Requirements
```bash
pip install -r requirements.txt
```

### API Keys (Free)

1. **OpenWeatherMap** (required):
   - Get key: https://openweathermap.org/api
   - Free tier: 60 calls/minute, 1,000 calls/day

2. **OpenAQ** (required for air quality):
   - Get key: https://openaq.org
   - Free tier: Unlimited

### Configuration

Create `.env` file:
```env
OPENWEATHER_API_KEY=your_openweather_key_here
OPENAQ_API_KEY=your_openaq_key_here
```

## Usage

### Quick Start

```python
from prana_system import PRANASystem
from location_detector import get_current_location

# Auto-detect your location
location = get_current_location()

# Initialize PRANA
prana = PRANASystem(
    api_key="your_openweather_key",
    location_name=f"{location['city']}, {location['country']}",
    urban_heat_offset=2.0,  # Adjust for your area (0.5-4.0°C)
    openaq_api_key="your_openaq_key"
)

# Run complete climate risk assessment
result = prana.update_all(location['lat'], location['lon'])

# Get WhatsApp-ready alert
print(result['alert_message'])
```

### Output Example

```
🚨 PRANA CLIMATE ALERT - Chennai, Tamil Nadu, India

Risk Level: HIGH (47.5/100)
Significant risk - limit outdoor exposure, check on vulnerable

📊 Current Conditions:
• Heat Stress (NDT): 34.6°C (VERY HIGH)
• Air Quality (HA-AQI): 185 (UNHEALTHY - 54% thermal amplification)
• Sleep Recovery: MODERATE (outdoor 30.2°C, RDS: 28.5)

⚠️ HIGH RISK:
• Stay indoors during peak heat
• Drink water frequently
• Check on elderly neighbors
```

### CCRI Debug Output

```python
result = prana.update_all(lat, lon)
# Automatically prints:

CCRI CALCULATION DEBUG
==========================================================
Heat Score (H):        68.5/100  (from NDT 34.6°C)
Pollution Score (P):   73.9/100  (from HA-AQI 185)
RDS:                   28.5/100

Base CCRI = (H × P) / 100
          = (68.5 × 73.9) / 100
          = 50.6

RDS Multiplier = 1 + (RDS/100) × 0.3
               = 1 + (28.5/100) × 0.3
               = 1.09x

Final CCRI = 50.6 × 1.09
           = 55.1/100
==========================================================
```

## Project Structure

```
prana/
├── config.py                  # Configuration & constants
├── data_fetcher.py           # API integrations (OpenWeatherMap, OpenAQ v3)
├── location_detector.py      # Auto-detect user location via IP
├── ndt_calculator.py         # WBGT + urban heat island
├── ha_aqi_calculator.py      # Thermal chemistry amplification
├── rds_calculator.py         # Sleep debt (range-based)
├── ccri_calculator.py        # Compound risk index
├── prana_system.py           # Main integration system
├── requirements.txt          # Dependencies
├── .env.example              # API key template
└── README.md                 # This file
```

## Scientific References

1. **Liu et al. (2025)** - Compound heat-ozone events, Jiangsu
2. **Obradovich et al. (2017)** - Nature Human Behaviour, 1, 0186 - Nighttime temperature & sleep
3. **Gasparrini & Armstrong (2011)** - Epidemiology, 22(1), 68–73 - Multiplicative mortality
4. **Shen et al. (2020)** - Atmos. Chem. Phys., DOI: 10.5194/acp-20-6807-2020 - Ozone-temperature sensitivity
5. **Lancet Countdown (2025)** - Added nighttime sleep loss as new health indicator
6. **WHO (2023)** - Heat Health Action Plan

## Key Innovations

### 1. Real-Time Thermal Chemistry
First platform modeling ozone amplification via published OAF formula (Shen et al. 2020)

### 2. Range-Based RDS
Honest communication: acknowledges we don't know indoor temperature, outputs as range

### 3. Compound Synergistic Risk
Multiplicative structure (not additive) reflects exponential mortality mechanisms

### 4. Ward-Level Precision
Urban heat island correction per neighborhood type, not airport-calibrated

### 5. WhatsApp Delivery at Scale
487.5M Indian users, zero hardware needed (CARE Bangladesh reached 34.2M via same model)

## Technical Specs

- **Languages:** Python 3.8+
- **Dependencies:** numpy, pandas, requests, python-dotenv
- **APIs:** OpenWeatherMap (free), OpenAQ v3 (free)
- **Update Frequency:** Every 3 hours recommended
- **Delivery:** WhatsApp via Twilio (integrate separately)
- **Cost:** $0 hardware, free-tier APIs
- **Scale:** Ward-level (2-5 km² precision)

## Deployment

### Chennai Pilot (Q3 2026)
- 1 ward: Tondiarpet
- 5,000 users
- ASHA health workers integration

### Three Cities (Q4 2026)
- Chennai, Delhi, Mumbai
- 50,000 users total

### Six-Country Rollout (2027)
- India, Philippines, Bangladesh, Vietnam, Pakistan, Indonesia
- Target: Millions of users
- Platform: WhatsApp chatbot via Twilio

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## License

MIT License - See LICENSE file for details

## Contact

**PRANA Climate Risk System**  
Asia's First Compound Climate Emergency Platform

For hackathons, demos, or deployment inquiries, contact via GitHub issues.

---

**Built with scientific rigor. Deployed for survival. Scaled for Asia.**
