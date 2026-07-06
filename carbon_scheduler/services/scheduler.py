from typing import List, Dict, Optional, Tuple
from models.region import Region
from models.workload import Workload
from services import forecaster
import config


def build_joint_region_pool() -> List[Region]:
    """The six-region pool used by joint spatial+temporal shifting."""
    return [Region(**r) for r in config.JOINT_SHIFT_REGION_POOL]


class Scheduler:
    """
    Implements weighted scoring and region selection logic.
    """
    
    @staticmethod
    def normalize(value: float, min_val: float, max_val: float) -> float:
        """
        Normalized value using Min-Max (0-1).
        If max_val == min_val, returns 0.0 to avoid division by zero.
        """
        if max_val == min_val:
            return 0.0
        return (value - min_val) / (max_val - min_val)

    @staticmethod
    def threshold_normalize(value: float, threshold: float, max_val: float) -> float:
        """
        Step-based normalization for values that already passed a binary
        acceptability filter: anything at or below `threshold` scores 0 (no
        penalty), since the filter that admitted it already treats that
        range as operationally acceptable. Only the excess above the
        threshold is scaled toward 1.
        """
        if value <= threshold:
            return 0.0
        denom = max_val - threshold
        if denom <= 0:
            return 0.0
        return min((value - threshold) / denom, 1.0)

    def filter_regions(self, regions: List[Region], max_latency: float) -> List[Region]:
        """
        Filters regions based on SLA (latency constraint).
        """
        return [r for r in regions if r.latency <= max_latency]

    def calculate_scores(self, regions: List[Region], weights: Dict[str, float]) -> List[Tuple[Region, float, Dict[str, float]]]:
        """
        Calculates weighted scores for each filtered region.
        Returns a list of (Region, Score, Metadata) tuples.
        """
        if not regions:
            return []
            
        # Get min/max for normalization (Computed only on filtered regions)
        carbons = [r.carbon for r in regions]
        latencies = [r.latency for r in regions]

        min_c, max_c = min(carbons), max(carbons)
        max_l = max(latencies)

        scored_results = []
        for region in regions:
            # Normalize (0-1). Handle min == max.
            c_norm = self.normalize(region.carbon, min_c, max_c)
            # Threshold-based latency scoring: regions already passed the
            # binary SLA filter (config.DEFAULT_MAX_LATENCY), which treats
            # anything under that ceiling as operationally indistinguishable.
            # Continuing to reward sub-threshold latency differences linearly
            # contradicts that filter's own model - so latency only starts
            # incurring a penalty once it exceeds the same ceiling the filter
            # already uses, deriving both from one source of truth instead of
            # a second, independently-tunable threshold.
            l_norm = self.threshold_normalize(region.latency, config.DEFAULT_MAX_LATENCY, max_l)
            
            # Resources normalization (percentage / 100)
            r_norm = region.resources / 100.0
            r_penalty = 1.0 - r_norm
            
            # Weighted Score
            score = (
                weights.get("carbon", 0.4) * c_norm +
                weights.get("latency", 0.3) * l_norm +
                weights.get("resources", 0.3) * r_penalty
            )
            
            # Metadata for explainability
            metadata = {
                "c_norm": round(c_norm, 3),
                "l_norm": round(l_norm, 3),
                "r_penalty": round(r_penalty, 3),
                "strengths": []
            }
            
            if c_norm < 0.3: metadata["strengths"].append("Low Carbon")
            if l_norm < 0.3: metadata["strengths"].append("Low Latency")
            if r_penalty < 0.3: metadata["strengths"].append("High Resource Availability")
            
            scored_results.append((region, round(score, 4), metadata))
            
        # Sort by score ascending, then apply tie-breakers:
        # 1. carbon (ascending), 2. latency (ascending), 3. resources (descending)
        return sorted(
            scored_results, 
            key=lambda x: (x[1], x[0].carbon, x[0].latency, -x[0].resources)
        )

    def get_best_region(self, scored_results: List[Tuple]) -> Optional[Region]:
        """
        Returns the Region object from the top-ranked (lowest score) result.
        Returns None if the scored_results list is empty.
        """
        if not scored_results:
            return None
        return scored_results[0][0]

    @staticmethod
    def estimate_total_carbon_kg(operational_co2_kg: float, exec_hours: float, cpu_fraction: float = 1.0) -> Dict[str, float]:
        """
        Lifecycle carbon = operational (grid) emissions + allocated embodied
        (manufacturing/Scope 3) share for the duration of execution.
        See guide sec 4.2 (Gupta et al., 2022 — embodied carbon can exceed 50%
        of lifecycle emissions on clean grids).
        """
        allocated_embodied_kg = config.EMBODIED_CO2_PER_HOUR_KG * exec_hours * cpu_fraction
        total_kg = operational_co2_kg + allocated_embodied_kg
        return {
            "operational_co2_kg": round(operational_co2_kg, 4),
            "embodied_co2_kg": round(allocated_embodied_kg, 4),
            "total_co2_kg": round(total_kg, 4)
        }

    @staticmethod
    def elastic_vcore_count(base_vcores: int, ci_current: float) -> Dict:
        """
        CarbonScaler-style elastic scaling for delay-tolerant batch jobs (guide sec 4.3).
        Scale parallelism up when grid carbon is clean, down when it's dirty.
        """
        low = config.ELASTIC_CI_THRESHOLD_LOW
        high = config.ELASTIC_CI_THRESHOLD_HIGH
        if ci_current < low:
            vcores = min(base_vcores * 2, config.ELASTIC_MAX_VCORES)
            action = "scale_up"
        elif ci_current > high:
            vcores = max(base_vcores // 2, config.ELASTIC_MIN_VCORES)
            action = "scale_down"
        else:
            vcores = base_vcores
            action = "hold"
        return {"vcores": vcores, "action": action, "ci_current": ci_current}

    def schedule_delay_tolerant(self, workload: Workload, region_pool: List[Region], weights: Dict[str, float] = None) -> Dict:
        """
        Joint spatial + temporal shifting for delay-tolerant workloads:

          1. Spatial shift  - pick the lowest-carbon region from the pool.
          2. Temporal shift - within that region, look ahead LOOKAHEAD_HOURS
             (default 4h) in STEP_MINUTES increments (default 15min) using
             the carbon-intensity forecast, and run at the lowest-carbon
             step that still completes before the workload's deadline.

        This is a two-stage greedy search (region first, then time), not an
        exhaustive joint optimum over every region x timestep combination -
        matching the requested "first pick a region, then shift in time
        within it" behaviour rather than a full cross-product search.
        """
        weights = weights or config.JOINT_SHIFT_WEIGHTS

        # 1. Spatial shift: lowest-carbon region in the pool.
        best_region = min(region_pool, key=lambda r: r.carbon)

        # 2. Temporal shift: forecast within that region, capped by the deadline.
        steps_per_hour = 60 // config.STEP_MINUTES
        max_steps = min(
            config.LOOKAHEAD_HOURS * steps_per_hour,
            max(1, int(workload.deadline_hours * steps_per_hour))
        )
        forecast_window = forecaster.forecast_quarter_hour_window(
            best_region.carbon,
            hours=config.LOOKAHEAD_HOURS,
            seed=hash(best_region.name) % (2**31)
        )
        candidate_steps = forecast_window[:max_steps]
        best_step_idx = min(range(len(candidate_steps)), key=lambda i: candidate_steps[i])
        predicted_ci = candidate_steps[best_step_idx]
        start_offset_minutes = (best_step_idx + 1) * config.STEP_MINUTES

        # 3. Carbon footprint at the chosen (region, time).
        footprint_g = (
            workload.cpu_util * workload.tdp_watts * workload.exec_time_hours
            * workload.pue * predicted_ci
        )

        # 4. Sustainability score for explainability (normalized across the pool).
        carbons = [r.carbon for r in region_pool]
        latencies = [r.latency for r in region_pool]
        c_norm = self.normalize(best_region.carbon, min(carbons), max(carbons))
        l_norm = self.normalize(best_region.latency, min(latencies), max(latencies))
        p_norm = 1.0 - (best_region.resources / 100.0)
        score = weights["w1"] * c_norm + weights["w2"] * l_norm + weights["w3"] * p_norm

        return {
            "workload_type": "delay-tolerant",
            "region": best_region.to_dict(),
            "start_offset_minutes": start_offset_minutes,
            "predicted_carbon_intensity": predicted_ci,
            "estimated_carbon_footprint_g": round(footprint_g, 4),
            "score": round(score, 4),
            "score_breakdown": {
                "C_norm": round(c_norm, 3),
                "L_norm": round(l_norm, 3),
                "P_norm": round(p_norm, 3)
            },
            "forecast_window": forecast_window
        }

    def schedule_latency_sensitive(self, workload: Workload, region_pool: List[Region], weights: Dict[str, float] = None) -> Dict:
        """Unchanged behaviour: lowest-carbon region meeting the latency SLA, run now."""
        weights = weights or config.JOINT_SHIFT_WEIGHTS
        eligible = self.filter_regions(region_pool, workload.max_latency_ms)
        if not eligible:
            return {
                "workload_type": "latency-sensitive",
                "region": None,
                "error": f"No region meets the {workload.max_latency_ms}ms latency constraint."
            }

        score_weights = {"carbon": weights["w1"], "latency": weights["w2"], "resources": weights["w3"]}
        scored = self.calculate_scores(eligible, score_weights)
        best_region, score, metadata = scored[0]

        footprint_g = (
            workload.cpu_util * workload.tdp_watts * workload.exec_time_hours
            * workload.pue * best_region.carbon
        )

        return {
            "workload_type": "latency-sensitive",
            "region": best_region.to_dict(),
            "start_offset_minutes": 0,
            "predicted_carbon_intensity": best_region.carbon,
            "estimated_carbon_footprint_g": round(footprint_g, 4),
            "score": score,
            "score_breakdown": {
                "C_norm": metadata["c_norm"],
                "L_norm": metadata["l_norm"],
                "P_norm": metadata["r_penalty"]
            }
        }

    def schedule(self, workload: Workload, region_pool: List[Region], weights: Dict[str, float] = None) -> Dict:
        """
        Entry point: dispatches to joint spatio-temporal shifting for
        delay-tolerant workloads, or immediate SLA-constrained placement
        for latency-sensitive ones.
        """
        if workload.latency_type == "delay-tolerant":
            return self.schedule_delay_tolerant(workload, region_pool, weights)
        return self.schedule_latency_sensitive(workload, region_pool, weights)

    def explain_decision(self, best_result: Tuple[Region, float, Dict]) -> Dict:
        """
        Generates a human-readable explanation for the selected region.
        """
        region, score, meta = best_result
        strengths = meta["strengths"]
        
        summary = f"Selected {region.name} as the optimal placement."
        if strengths:
            summary += f" It excels in: {', '.join(strengths)}."
        else:
            summary += " It offers the best balanced score across all metrics."
            
        return {
            "summary": summary,
            "details": {
                "carbon_impact": "Excellent" if meta["c_norm"] < 0.2 else "Optimized",
                "performance": "High" if meta["l_norm"] < 0.2 else "Stable",
                "capacity": "Ample" if meta["r_penalty"] < 0.2 else "Sufficient"
            }
        }
