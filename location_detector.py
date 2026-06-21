"""
Automatic location detection for PRANA
Uses IP geolocation (free, no API key needed)
"""

import requests
import json


def get_current_location():
    """
    Detect user's current location using IP geolocation
    
    Returns:
        dict with 'lat', 'lon', 'city', 'country'
    """
    try:
        # Method 1: ipapi.co (free, no signup)
        print("Detecting your location...")
        response = requests.get('https://ipapi.co/json/', timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            location = {
                'lat': data.get('latitude'),
                'lon': data.get('longitude'),
                'city': data.get('city', 'Unknown'),
                'region': data.get('region', ''),
                'country': data.get('country_name', 'Unknown'),
                'postal': data.get('postal', '')
            }
            
            print(f"[OK] Location detected: {location['city']}, {location['country']}")
            print(f"     Coordinates: {location['lat']:.4f}, {location['lon']:.4f}\n")
            return location
        
    except Exception as e:
        print(f"Method 1 failed: {e}")
    
    try:
        # Method 2: ip-api.com (backup, also free)
        print("Trying backup location service...")
        response = requests.get('http://ip-api.com/json/', timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            location = {
                'lat': data.get('lat'),
                'lon': data.get('lon'),
                'city': data.get('city', 'Unknown'),
                'region': data.get('regionName', ''),
                'country': data.get('country', 'Unknown'),
                'postal': data.get('zip', '')
            }
            
            print(f"[OK] Location detected: {location['city']}, {location['country']}")
            print(f"     Coordinates: {location['lat']:.4f}, {location['lon']:.4f}\n")
            return location
            
    except Exception as e:
        print(f"Method 2 failed: {e}")
    
    # Fallback: Use Chennai as default
    print("WARNING: Could not auto-detect location. Using Chennai as default.")
    print("         (You can manually specify coordinates when calling update_all())\n")
    return {
        'lat': 13.0827,
        'lon': 80.2707,
        'city': 'Chennai',
        'region': 'Tamil Nadu',
        'country': 'India',
        'postal': ''
    }


def get_location_name(location):
    """Format location name for display"""
    if location['region'] and location['region'] != location['city']:
        return f"{location['city']}, {location['region']}, {location['country']}"
    return f"{location['city']}, {location['country']}"


if __name__ == "__main__":
    print("\n" + "="*70)
    print("LOCATION DETECTION TEST")
    print("="*70 + "\n")
    
    location = get_current_location()
    
    print("="*70)
    print("DETECTED LOCATION")
    print("="*70)
    print(f"City: {location['city']}")
    print(f"Region: {location['region']}")
    print(f"Country: {location['country']}")
    print(f"Latitude: {location['lat']}")
    print(f"Longitude: {location['lon']}")
    if location['postal']:
        print(f"Postal Code: {location['postal']}")
    print("="*70 + "\n")
    
    print("[OK] Location detection working!")
    print(f"\nYour PRANA alerts will be for: {get_location_name(location)}")
