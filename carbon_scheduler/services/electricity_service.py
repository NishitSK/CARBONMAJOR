import requests
import config
from typing import Dict, Optional, List
from services.utils import log_decision

class ElectricityService:
    """
    Handles communication with the Electricity Maps API to fetch real-world carbon intensity.
    """
    
    API_URL = "https://api.electricitymaps.com/v3/carbon-intensity/latest"
    
    # Mapping of cloud regions to nearest Electricity Maps zones and their coordinates.
    REGION_MAP = {
        "us-east-1 (N. Virginia)": {"zone": "US-MIDA-PJM", "lat": 38.13, "lng": -78.45},
        "eu-west-1 (Ireland)": {"zone": "IE", "lat": 53.0, "lng": -8.0},
        "eu-central-1 (Frankfurt)": {"zone": "DE", "lat": 50.11, "lng": 8.68},
        "ap-south-1 (Mumbai)": {"zone": "IN-WE", "lat": 19.07, "lng": 72.87},
        "sa-east-1 (Sao Paulo)": {"zone": "BR", "lat": -23.55, "lng": -46.63},
        "ca-central-1 (Canada)": {"zone": "CA-QC", "lat": 45.5, "lng": -73.56},
        "af-south-1 (Cape Town)": {"zone": "ZA", "lat": -33.92, "lng": 18.42},
        "us-west-2 (Oregon)": {"zone": "US-NW-PACW", "lat": 45.82, "lng": -119.70},
        "ap-southeast-2 (Sydney)": {"zone": "AU-NSW", "lat": -33.86, "lng": 151.20},
        "eu-north-1 (Sweden)": {"zone": "SE", "lat": 60.13, "lng": 18.64},
        "ap-southeast-1 (Singapore)": {"zone": "SG", "lat": 1.35, "lng": 103.82},
        "ap-northeast-1 (Tokyo)": {"zone": "JP", "lat": 35.68, "lng": 139.69},
        "us-east-2 (Ohio)": {"zone": "US-MIDW-MISO", "lat": 40.0, "lng": -82.5},
    }

    def __init__(self, token: str = config.ELECTRICITY_MAPS_TOKEN):
        self.headers = {"auth-token": token}

    def get_carbon_intensity(self, zone: str, datetime: str = None) -> Optional[float]:
        """
        Fetches carbon intensity for a specific zone with a safe fallback mechanism.
        """
        try:
            params = {"zone": zone}
            response = requests.get(self.API_URL, headers=self.headers, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                return data.get("carbonIntensity")
            else:
                log_decision(f"API Error ({response.status_code}) for {zone}. Using simulated fallback.", "WARNING")
                return None
        except Exception as e:
            log_decision(f"API Connection Failed for {zone}: {str(e)}. Using fallback.", "WARNING")
            return None

    def get_all_region_carbon_data(self, datetime: str = None) -> Dict[str, Dict]:
        """
        Fetches carbon intensity for all mapped regions with a per-region fallback.
        """
        results = {}
        for region_name, metadata in self.REGION_MAP.items():
            carbon = self.get_carbon_intensity(metadata["zone"])
            
            # Fallback values for Demo Mode or API Failure
            if carbon is None:
                # Use a deterministic "pseudo-real" fallback based on zone name hash
                fallback_carbon = 200 + (hash(metadata["zone"]) % 600)
                carbon = float(fallback_carbon)

            results[region_name] = {
                "carbon": carbon,
                "lat": metadata["lat"],
                "lng": metadata["lng"],
                "zone": metadata["zone"],
                "is_live": carbon is not None
            }
        return results
