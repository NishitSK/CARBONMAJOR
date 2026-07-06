from dataclasses import dataclass

@dataclass
class Region:
    """
    Represents a cloud region with simulation metrics.
    
    Attributes:
        name (str): Unique identifier for the region (e.g., 'us-east-1').
        carbon (float): Carbon intensity in gCO2/kWh (100-900).
        latency (float): Latency in milliseconds (20-300).
        resources (float): Resource availability percentage (0-100). Higher is better.
        lat (float): Latitude for map visualization.
        lng (float): Longitude for map visualization.
    """
    name: str
    carbon: float
    latency: float
    resources: float
    lat: float = 0.0
    lng: float = 0.0

    def __post_init__(self):
        """Ensure types are correct after initialization."""
        self.carbon = float(self.carbon)
        self.latency = float(self.latency)
        self.resources = float(self.resources)
        self.lat = float(self.lat)
        self.lng = float(self.lng)

    def to_dict(self):
        return {
            "name": self.name,
            "carbon": self.carbon,
            "latency": self.latency,
            "resources": self.resources,
            "lat": self.lat,
            "lng": self.lng
        }
