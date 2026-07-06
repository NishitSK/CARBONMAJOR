import json
import random
from typing import List, Optional
from models.region import Region
import config
from services.electricity_service import ElectricityService

class Simulator:
    """
    Handles region data simulation and fetching.
    """
    def __init__(self, seed: Optional[int] = config.DETERMINISTIC_SEED, demo_mode: bool = False):
        self.seed = 42 if demo_mode else seed
        self.demo_mode = demo_mode
        if self.seed is not None:
            random.seed(self.seed)
        self.electricity_service = ElectricityService()

    def load_from_json(self, file_path: str = config.REGIONS_JSON_FILE) -> List[Region]:
        """
        Loads region data from a JSON file and attaches fixed coordinates if known.
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                regions = []
                for r in data:
                    region = Region(**r)
                    # Attach coordinates from the service mapping if available
                    if region.name in ElectricityService.REGION_MAP:
                        meta = ElectricityService.REGION_MAP[region.name]
                        region.lat = meta["lat"]
                        region.lng = meta["lng"]
                    regions.append(region)
                return regions
        except Exception as e:
            from services.utils import log_decision
            log_decision(f"Failed to load JSON: {e}", "ERROR")
            return []

    def generate_random_regions(self, count: int = config.RANDOM_GEN_PARAMS["count"]) -> List[Region]:
        """
        Generates random region data for simulation with coordinates.
        """
        regions = []
        region_list = list(ElectricityService.REGION_MAP.items())
        
        # Use provided count or length of names list
        actual_count = min(count, len(region_list))
        random.shuffle(region_list)
        
        for i in range(actual_count):
            name, meta = region_list[i]
            carbon = random.uniform(*config.RANDOM_GEN_PARAMS["carbon"])
            latency = random.uniform(*config.RANDOM_GEN_PARAMS["latency"])
            resources = random.uniform(*config.RANDOM_GEN_PARAMS["resources"])
            
            regions.append(Region(
                name=name,
                carbon=round(carbon, 2),
                latency=round(latency, 2),
                resources=round(resources, 2),
                lat=meta["lat"],
                lng=meta["lng"]
            ))
            
        return regions

    def get_live_regions(self) -> List[Region]:
        """
        Fetches real-time (snapshot) regions using Electricity Maps API.
        """
        live_data = self.electricity_service.get_all_region_carbon_data()
        regions = []
        
        for name, data in live_data.items():
            # If API fails for a region, use a default fallback
            carbon = data["carbon"] if data["carbon"] is not None else 500.0
            
            # Latency and resources are still simulated in live mode for this demo
            regions.append(Region(
                name=name,
                carbon=carbon,
                latency=round(random.uniform(20, 300), 2),
                resources=round(random.uniform(50, 100), 2),
                lat=data["lat"],
                lng=data["lng"]
            ))
        return regions

    def get_simulation_data(self, mode: str = "fixed") -> List[Region]:
        """
        Retrieves simulation data based on mode ('fixed', 'random', or 'live').
        """
        if mode == "live":
            return self.get_live_regions()
        elif mode == "fixed":
            return self.load_from_json()
        else:
            return self.generate_random_regions()

    def apply_drift(self, regions: List[Region]) -> List[Region]:
        """
        Applies subtle and realistic random fluctuations (drift) to region metrics.
        Mimics solar cover changes, network jitter, and background workload shifts.
        Disabled if demo_mode is active for stability.
        """
        if self.demo_mode:
            return regions
            
        for r in regions:
            # Carbon intensity drift (solar/wind changes or grid peak)
            c_drift = random.uniform(-0.05, 0.05) # ±5%
            r.carbon = max(10, min(1000, r.carbon * (1 + c_drift)))
            
            # Latency drift (network congestion / jitter)
            l_drift = random.uniform(-0.03, 0.03) # ±3%
            r.latency = max(5, min(500, r.latency * (1 + l_drift)))
            
            # Resource availability drift (batch jobs starting/stopping)
            res_drift = random.uniform(-0.04, 0.04) # ±4%
            r.resources = max(0, min(100, r.resources * (1 + res_drift)))
            
            # Optional: Round values for cleanliness
            r.carbon = round(r.carbon, 2)
            r.latency = round(r.latency, 2)
            r.resources = round(r.resources, 2)
            
        return regions
