import os
import sys

# Add carbon_scheduler to path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "carbon_scheduler"))

from models.region import Region
from services.scheduler import Scheduler
from services.simulator import Simulator

def test_normalization():
    print("Testing Normalization...")
    scheduler = Scheduler()
    # Standard min/max
    assert scheduler.normalize(100, 100, 200) == 0.0
    assert scheduler.normalize(200, 100, 200) == 1.0
    assert scheduler.normalize(150, 100, 200) == 0.5
    # Edge case: min == max (Safety Fix)
    assert scheduler.normalize(100, 100, 100) == 0.0
    print("Normalization tests passed!")

def test_scoring_and_sla():
    print("\nTesting Scoring and SLA Filtering...")
    scheduler = Scheduler()
    regions = [
        Region("R1", carbon=100, latency=50, resources=100), # Perfect
        Region("R2", carbon=900, latency=50, resources=10),  # Bad carbon/resources
        Region("R3", carbon=500, latency=400, resources=80) # Violation (latency > 200)
    ]
    
    # SLA Filtering
    filtered = scheduler.filter_regions(regions, max_latency=200)
    assert len(filtered) == 2
    
    # Scoring
    weights = {"carbon": 0.4, "latency": 0.3, "resources": 0.3}
    scored = scheduler.calculate_scores(filtered, weights)
    
    best_region = scheduler.get_best_region(scored)
    assert best_region.name == "R1"
    assert scored[0][1] == 0.0
    print("Scoring and SLA tests passed!")

def test_tie_breaker():
    print("\nTesting Tie-Breaker Logic...")
    scheduler = Scheduler()
    # R1 and R2 will have same score if weights are 0.5/0.5/0 and metrics are same
    # But we use normalization, so let's force identical scores
    regions = [
        Region("Winner", carbon=100, latency=50, resources=100),
        Region("Loser", carbon=200, latency=50, resources=100)
    ]
    # If carbon is different, but scores are forced to be same (e.g. weight=0 for carbon)
    # Actually, normalization makes carbon 0 and 1. 
    # Let's use custom weights to see if tie-breaker kicks in.
    
    # Force a tie by using 0 weight for the differing attribute
    weights = {"carbon": 0.0, "latency": 0.5, "resources": 0.5}
    scored = scheduler.calculate_scores(regions, weights)
    
    # Both have latency 50 and resources 100 -> Scores will be identical (0.0)
    assert scored[0][1] == scored[1][1]
    
    # Tie-breaker 1: Lower carbon (Winner has 100, Loser has 200)
    assert scored[0][0].name == "Winner"
    print("Tie-breaker (Carbon) passed!")

if __name__ == "__main__":
    try:
        test_normalization()
        test_scoring_and_sla()
        test_tie_breaker()
        print("\nAll automated logic tests passed successfully!")
    except AssertionError as e:
        print(f"\nTest FAILED: {e}")
        sys.exit(1)
