from dataclasses import dataclass


@dataclass
class Workload:
    """
    A unit of compute to be placed by the scheduler.

    latency_type: "latency-sensitive" -> placed immediately in the lowest-carbon
                  region that meets max_latency_ms.
                  "delay-tolerant" -> placed via joint spatial + temporal shifting
                  (see Scheduler.schedule_delay_tolerant), bounded by deadline_hours.
    """
    cpu_util: float        # average CPU utilization, 0-1
    tdp_watts: float        # processor thermal design power, watts
    exec_time_hours: float  # expected execution duration, hours
    pue: float               # data center Power Usage Effectiveness
    latency_type: str         # "latency-sensitive" | "delay-tolerant"
    max_latency_ms: float = 200.0   # used when latency-sensitive
    deadline_hours: float = 4.0     # max allowable delay when delay-tolerant

    def __post_init__(self):
        if self.latency_type not in ("latency-sensitive", "delay-tolerant"):
            raise ValueError(f"Invalid latency_type: {self.latency_type!r}")
