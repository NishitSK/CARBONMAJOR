import sys
import os

# Add local directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.simulator import Simulator
from services.scheduler import Scheduler
from services.utils import format_table, log_decision, print_section_header
import config

def get_float_input(prompt: str, default: float = None) -> float:
    """Helper to get and validate float input from user."""
    while True:
        user_input = input(prompt).strip()
        if not user_input and default is not None:
            return default
        try:
            val = float(user_input)
            if val < 0:
                print("Error: Please enter a non-negative number.")
                continue
            return val
        except ValueError:
            print("Error: Invalid numeric input. Please retry.")

def get_weights_input() -> dict:
    """Prompt user for weights and validate sum to 1.0."""
    while True:
        print("\nEnter weights for scoring (values 0-1, sum must be ~1.0):")
        w_carbon = get_float_input(f"Carbon Weight [Default {config.DEFAULT_WEIGHTS['carbon']}]: ", config.DEFAULT_WEIGHTS['carbon'])
        w_latency = get_float_input(f"Latency Weight [Default {config.DEFAULT_WEIGHTS['latency']}]: ", config.DEFAULT_WEIGHTS['latency'])
        w_resources = get_float_input(f"Resource Weight [Default {config.DEFAULT_WEIGHTS['resources']}]: ", config.DEFAULT_WEIGHTS['resources'])
        
        total = w_carbon + w_latency + w_resources
        # Allow +/- 0.01 tolerance
        if abs(total - 1.0) <= 0.01:
            print(f"\n>>> Using weights -> Carbon: {w_carbon} | Latency: {w_latency} | Resources: {w_resources} <<<")
            return {"carbon": w_carbon, "latency": w_latency, "resources": w_resources}
        else:
            print(f"Error: Weights sum to {total:.3f}. They must sum to 1.0 (±0.01). Please retry.")

def display_rejected_regions(rejected_regions, max_latency):
    """Prints a table of regions that failed SLA constraints."""
    if not rejected_regions:
        return
    
    headers = ["Region Name", "Latency (ms)", "Reason"]
    data = [[r.name, r.latency, f"Exceeds max_latency ({max_latency}ms)"] for r in rejected_regions]
    
    print_section_header("Rejected Regions (SLA Violations)")
    print(format_table(headers, data))

def display_regions(regions, title="Regions Data"):
    """Formats and prints region data in a table."""
    headers = ["Name", "Carbon (g/kWh)", "Latency (ms)", "Resources (%)"]
    data = [[r.name, r.carbon, r.latency, f"{r.resources}%"] for r in regions]
    print(f"\n### {title} ###")
    print(format_table(headers, data))

def run_simulation(is_demo=False):
    """Main simulation orchestration logic."""
    print_section_header("Carbon-Aware Cloud Scheduler")
    
    # 1. Initialize services
    # If demo mode, use seed 42. Else no seed.
    simulator = Simulator(seed=config.DETERMINISTIC_SEED if is_demo else None)
    scheduler = Scheduler()
    
    # 2. Load data
    if is_demo:
        print("Demo Mode Active: Using deterministic/fixed dataset.")
        all_regions = simulator.get_simulation_data("fixed")
    else:
        print("Random Mode Active: Generating dynamic region data.")
        all_regions = simulator.get_simulation_data("random")
    
    if not all_regions:
        log_decision("No region data found. Exiting.", "ERROR")
        return

    # 3. Display Initial Data
    print_section_header("Step 1: All Available Regions")
    display_regions(all_regions, "Full Region Dataset")

    # 4. Get User Constraints & Weights
    max_latency = get_float_input(f"\nEnter Maximum Allowable Latency (SLA) [Default {config.DEFAULT_MAX_LATENCY}]: ", config.DEFAULT_MAX_LATENCY)
    weights = get_weights_input()

    # 5. Filter Regions (SLA Constraint)
    filtered = scheduler.filter_regions(all_regions, max_latency)
    rejected = [r for r in all_regions if r not in filtered]
    
    # Display Rejections
    display_rejected_regions(rejected, max_latency)
    
    if not filtered:
        print_section_header("Filtered Results")
        print(f"No regions meet SLA constraints (Latency <= {max_latency}ms).")
        log_decision(f"All regions rejected due to SLA (Latency > {max_latency}ms).", "WARNING")
        return

    # 6. Score Regions (Normalization happens ONLY on filtered regions)
    scored_results = scheduler.calculate_scores(filtered, weights)
    best_region = scheduler.get_best_region(scored_results)

    # 7. Final Output
    print_section_header("Scoring Results")
    
    headers = ["Rank", "Region Name", "Carbon", "Latency", "Res %"]
    if config.DEBUG_MODE:
        headers += ["C_Norm", "L_Norm", "R_Pen"]
    headers.append("Final Score")

    table_data = []
    for i, (region, score, metadata) in enumerate(scored_results):
        rank = i + 1
        row = [rank, region.name, region.carbon, region.latency, f"{region.resources}%"]
        if config.DEBUG_MODE:
            row += [metadata["c_norm"], metadata["l_norm"], metadata["r_penalty"]]
        row.append(f"{score:.4f}")
        table_data.append(row)
    
    print(format_table(headers, table_data))
    
    print_section_header("Final Decision")
    if best_region:
        print(f">>> BEST REGION SELECTED: {best_region.name} <<<")
        log_decision(f"Final Selection: {best_region.name} (Score: {scored_results[0][1]})")

def main():
    """Application entry point with loop."""
    print_section_header("Project Startup")
    demo_input = input("Run in Demo Mode? (y/n) [y]: ").lower()
    is_demo = demo_input != 'n'

    try:
        while True:
            run_simulation(is_demo)
            
            cont = input("\nRun another simulation? (y/n) [y]: ").lower()
            if cont == 'n':
                print("Exiting Carbon-Aware Scheduler. Goodbye!")
                break
    except KeyboardInterrupt:
        print("\nSimulation aborted by user.")

if __name__ == "__main__":
    main()
