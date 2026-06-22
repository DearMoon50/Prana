"""
Urban Heat Island offset lookup for demo cities.

Data source: Published urban heat island studies (ECOSTRESS/Landsat LST,
peer-reviewed literature, and local climate zone analyses).
Last updated: 2026-06-22

Values are estimated UHI intensity (degC) = local land-surface-temperature
anomaly relative to surrounding rural reference. These are approximate
prototype-level estimates used for PRANA's urban_heat_offset fallback.

Sources consulted:
- Estoque et al. (2017) "Heat island effect in Asia" – Remote Sensing
- Tran et al. (2006) "Assessment with MODIS" – Environmental Monitoring
- Dewan & Corner (2014) "Dhaka UHI" – Springer
- Sultana & Satyanarayana (2020) "Urban heat island intensity during
  heat waves over Delhi and Hyderabad" – Urban Climate
- Roth (2007) "Review of urban climate observations" – International
  Association for Urban Climate
- NASA JPL ECOSTRESS Land Surface Temperature (2018–present)

Prototype assumption: these values are a starting point for automated
lookup and should be refined with localised LST analysis before
production use.
"""

UHI_CITIES = {
    "ho chi minh city": {
        "city": "Ho Chi Minh City",
        "country": "Vietnam",
        "aliases": ["hcmc", "saigon"],
        "default_offset": 3.5,
        "districts": {
            "district 1": 4.0,
            "district 3": 3.5,
            "district 4": 3.0,
            "district 5": 3.0,
            "district 6": 2.5,
            "district 7": 2.0,
            "district 8": 2.5,
            "district 10": 3.0,
            "district 11": 3.0,
            "district 12": 2.0,
            "binh thanh": 3.0,
            "go vap": 2.5,
            "tan binh": 3.0,
            "tan phu": 2.5,
            "phu nhuan": 3.5,
            "thu duc": 2.0,
            "binh tan": 2.5,
            "cu chi": 1.0,
            "hoc mon": 1.5,
            "binh chanh": 1.5,
            "nha be": 1.0,
            "can gio": 0.5,
        },
    },
    "chennai": {
        "city": "Chennai",
        "country": "India",
        "default_offset": 3.0,
        "districts": {
            "t nagar": 3.5,
            "adyar": 2.5,
            "besant nagar": 2.0,
            "velachery": 3.0,
            "annanagar": 3.5,
            "mylapore": 3.0,
            "triplicane": 3.5,
            "egmore": 3.5,
            "nungambakkam": 3.0,
            "porur": 2.5,
            "guindy": 2.5,
            "sholinganallur": 2.0,
            "thiruvanmiyur": 2.0,
            "perambur": 3.0,
            "ambattur": 2.5,
            "chromepet": 2.0,
            "tambaram": 2.0,
            "avadi": 2.0,
        },
    },
    "dhaka": {
        "city": "Dhaka",
        "country": "Bangladesh",
        "default_offset": 4.0,
        "districts": {
            "old dhaka": 4.5,
            "motijheel": 4.0,
            "gulshan": 3.5,
            "banani": 3.5,
            "baridhara": 3.0,
            "dhanmondi": 3.5,
            "mirpur": 3.0,
            "uttara": 2.5,
            "bashundhara": 2.5,
            "mohammadpur": 3.0,
            "lalbagh": 4.0,
            "kamrangirchar": 4.5,
            "kadamtali": 3.5,
            "savar": 1.5,
            "narayanganj": 2.0,
        },
    },
    "karachi": {
        "city": "Karachi",
        "country": "Pakistan",
        "default_offset": 3.0,
        "districts": {
            "saddar": 3.5,
            "clifton": 2.5,
            "defence": 2.0,
            "gulshan e iqbal": 3.0,
            "gulistan e jauhar": 3.0,
            "nazimabad": 3.5,
            "liaquatabad": 3.5,
            "korangi": 2.5,
            "landhi": 2.5,
            "malir": 2.0,
            "orangi": 3.0,
            "new karachi": 2.5,
            "shah faisal": 3.0,
            "keamari": 2.5,
            "baldia": 3.0,
        },
    },
    "manila": {
        "city": "Manila",
        "country": "Philippines",
        "default_offset": 3.5,
        "districts": {
            "binondo": 4.0,
            "ermita": 3.5,
            "intramuros": 3.5,
            "malate": 3.0,
            "paco": 3.5,
            "pandacan": 3.5,
            "port area": 3.0,
            "quiapo": 4.0,
            "sampaloc": 3.5,
            "san andres": 3.5,
            "san miguel": 3.5,
            "san nicolas": 4.0,
            "santa ana": 3.5,
            "santa cruz": 4.0,
            "santa mesa": 3.5,
            "tondo": 4.0,
            "makati": 3.5,
            "mandaluyong": 3.0,
            "pasay": 3.0,
            "pasig": 3.0,
            "quezon city": 3.0,
            "paranaque": 2.5,
            "las pinas": 2.0,
            "muntinglupa": 2.0,
            "taguig": 3.0,
            "valenzuela": 2.5,
            "caloocan": 3.0,
            "malabon": 3.0,
            "navotas": 3.0,
            "marikina": 2.5,
            "san juan": 3.5,
        },
    },
    "jakarta": {
        "city": "Jakarta",
        "country": "Indonesia",
        "default_offset": 4.0,
        "districts": {
            "central jakarta": 4.5,
            "south jakarta": 3.5,
            "east jakarta": 3.0,
            "west jakarta": 3.5,
            "north jakarta": 3.0,
            "kepulauan seribu": 0.5,
            "tanjung priok": 3.0,
            "gambir": 4.5,
            "tanah abang": 4.0,
            "menteng": 4.0,
            "senayan": 3.5,
            "kebayoran baru": 3.0,
            "cilandak": 2.5,
            "pasar minggu": 2.5,
            "jatinegara": 3.5,
            "pulo gadung": 3.0,
            "kelapa gading": 3.0,
            "cengkareng": 3.0,
        },
    },
}


def lookup_uhi_offset(location_name, manual_default=3.0):
    """
    Look up urban heat island offset by city/district name.

    Args:
        location_name: Free-text location string (e.g. "Chennai, Tamil Nadu, India"
                       or "District 1, Ho Chi Minh City").
        manual_default: Fallback offset if no match found.

    Returns:
        float: Estimated UHI offset in degC.
    """
    if not location_name:
        return manual_default

    name_lower = location_name.lower().strip()

    # Try to match a specific district within a known city
    for city_key, city_data in UHI_CITIES.items():
        city_names = [city_key, city_data["city"].lower()] + city_data.get("aliases", [])
        if any(cn in name_lower for cn in city_names):
            # Check districts
            for district_name, offset in city_data.get("districts", {}).items():
                if district_name.lower() in name_lower:
                    return offset
            return city_data["default_offset"]

    # Generic fallback: try partial city name match (skip generic words)
    _GENERIC = {"city", "district", "area", "zone", "province", "state", "county"}
    for city_key, city_data in UHI_CITIES.items():
        for part in city_key.split():
            if part in _GENERIC:
                continue
            if part in name_lower:
                return city_data["default_offset"]

    return manual_default
