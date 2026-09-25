"""
Automated Interim & Final Report Generator
Freezes a snapshot of live pilot data (e.g., at Day 14 / 336 cycles or Day 30 / 720 cycles),
runs paired t-tests, Wilcoxon signed-rank tests, calculates mean CI and carbon savings,
and outputs Markdown and LaTeX formatted tables.

Usage:
  python scripts/generate_interim_report.py --checkpoint-name "2-week-checkpoint"
  python scripts/generate_interim_report.py --max-cycles 336
"""
import argparse
import datetime
import json
import os
import sys
from typing import Dict, List

import numpy as np
from scipy import stats

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

LOG_FILES = {
    "Adaptive Spatial": os.path.join(config.DATA_DIR, "pilot_adaptive.jsonl"),
    "LSTM Temporal 24h": os.path.join(config.DATA_DIR, "pilot_lstm.jsonl"),
    "ARIMA Temporal 6h": os.path.join(config.DATA_DIR, "pilot_arima.jsonl"),
}

BASELINE_CI = 405.04


def load_series(path: str, max_cycles: int = None) -> List[float]:
    if not os.path.exists(path):
        return []
    series = []
    with open(path, "r") as f:
        for line in f:
            if max_cycles and len(series) >= max_cycles:
                break
            line = line.strip()
            if line:
                try:
                    obj = json.loads(line)
                    val = obj.get("winning_ci") or obj.get("predicted_optimal_ci")
                    if val is not None:
                        series.append(float(val))
                except Exception:
                    pass
    return series


def run_statistics(series_a: List[float], series_b: List[float]):
    min_len = min(len(series_a), len(series_b))
    if min_len < 5:
        return {"n": min_len, "t_stat": None, "p_val_t": None, "p_val_wilcoxon": None}

    a = np.array(series_a[:min_len])
    b = np.array(series_b[:min_len])

    diff = a - b
    if np.all(diff == 0):
        return {"n": min_len, "t_stat": 0.0, "p_val_t": 1.0, "p_val_wilcoxon": 1.0}

    t_stat, p_t = stats.ttest_rel(a, b)
    try:
        w_stat, p_w = stats.wilcoxon(a, b)
    except Exception:
        p_w = None

    return {
        "n": min_len,
        "t_stat": float(t_stat),
        "p_val_t": float(p_t),
        "p_val_wilcoxon": float(p_w) if p_w is not None else None
    }


def generate_report(checkpoint_name: str, max_cycles: int = None):
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    out_md_path = os.path.join(config.BASE_DIR, f"REPORT_{checkpoint_name.upper().replace('-', '_')}.md")

    data = {}
    for name, path in LOG_FILES.items():
        data[name] = load_series(path, max_cycles=max_cycles)

    print(f"\n========================================================")
    print(f" Generating Empirical Report: [{checkpoint_name}]")
    print(f" Timestamp: {now_str}")
    print(f"========================================================")

    lines = []
    lines.append(f"# Empirical Cloud Pilot Report — {checkpoint_name}")
    lines.append(f"**Generated:** {now_str}  ")
    lines.append(f"**Baseline:** Carbon-blind fixed region ({BASELINE_CI:.2f} gCO2/kWh)\n")
    lines.append("## 1. Summary of Results Across Policies\n")
    lines.append("| Policy | Cycles ($N$) | Mean CI (gCO2/kWh) | Std Dev | Total Reduction vs. Baseline | Marginal Gain vs. Adaptive |")
    lines.append("|---|---|---|---|---|---|")


    adaptive_mean = np.mean(data["Adaptive Spatial"]) if data["Adaptive Spatial"] else 0.0

    for name, series in data.items():
        n = len(series)
        if n == 0:
            lines.append(f"| **{name}** | 0 | Pending | -- | -- | -- |")
            continue
        mean_val = float(np.mean(series))
        std_val = float(np.std(series))
        cut_pct = (BASELINE_CI - mean_val) / BASELINE_CI * 100.0
        marg_gain = (adaptive_mean - mean_val) / max(1.0, adaptive_mean) * 100.0 if adaptive_mean > 0 else 0.0
        marg_str = f"+{marg_gain:.2f}%" if marg_gain > 0 else f"{marg_gain:.2f}%"
        lines.append(f"| **{name}** | {n} | **{mean_val:.2f}** | {std_val:.2f} | **{cut_pct:.1f}%** | {marg_str} |")

    lines.append("\n## 2. Statistical Significance Analysis\n")
    lines.append("| Comparison | Concurrent Cycles ($N$) | Paired $t$-Statistic | $p$-Value ($t$-test) | Wilcoxon $p$-Value |")
    lines.append("|---|---|---|---|---|")

    # Comparisons
    pairs = [
        ("Adaptive vs. LSTM Temporal", data["Adaptive Spatial"], data["LSTM Temporal 24h"]),
        ("Adaptive vs. ARIMA Temporal", data["Adaptive Spatial"], data["ARIMA Temporal 6h"]),
        ("ARIMA vs. LSTM Temporal", data["ARIMA Temporal 6h"], data["LSTM Temporal 24h"])
    ]

    for label, s1, s2 in pairs:
        st = run_statistics(s1, s2)
        if st["t_stat"] is None:
            lines.append(f"| {label} | {st['n']} | -- (Insufficient data) | -- | -- |")
        else:
            p_t_fmt = f"{st['p_val_t']:.2e}" if st['p_val_t'] < 0.001 else f"{st['p_val_t']:.4f}"
            p_w_fmt = f"{st['p_val_wilcoxon']:.2e}" if st['p_val_wilcoxon'] is not None and st['p_val_wilcoxon'] < 0.001 else (f"{st['p_val_wilcoxon']:.4f}" if st['p_val_wilcoxon'] is not None else "--")
            lines.append(f"| {label} | {st['n']} | $t = {st['t_stat']:.2f}$ | $p = {p_t_fmt}$ | $p = {p_w_fmt}$ |")

    # 3. Ground-Truth Verified Forecast Accuracy & Realized Savings
    lines.append("\n## 3. Ground-Truth Verified Forecast Accuracy & Realized Savings (1h, 3h, 6h)\n")
    try:
        from services import forecast_tracker
        v_metrics = forecast_tracker.compute_verification_metrics()
        if v_metrics:
            lines.append("| Model | Horizon | Verified Samples ($N$) | MAE (gCO2/kWh) | RMSE | Directional Accuracy | Mean Realized Savings | Regret Rate |")
            lines.append("|---|---|---|---|---|---|---|---|")
            for model, h_data in v_metrics.items():
                for h_key, m in h_data.items():
                    lines.append(f"| **{model}** | {h_key} | {m['sample_count']} | **{m['mae_gco2']} g** | {m['rmse_gco2']} g | {m['directional_accuracy_pct']}% | +{m['mean_realized_savings_pct']}% | {m['regret_rate_pct']}% |")
        else:
            lines.append("*Ground-truth reconciliation is actively accumulating. Checkpoints are verified as target timestamps elapse (1h, 3h, 6h).*")
    except Exception as e:
        lines.append(f"*Verification tracker active: {e}*")

    lines.append("\n## 4. LaTeX Table Output (Ready for Paper Integration)\n")
    lines.append("```latex")
    lines.append("\\begin{table}[htbp]")
    lines.append("\\caption{Live Multi-Account Empirical Pilot Results (" + checkpoint_name + ")}")
    lines.append("\\centering")
    lines.append("\\begin{tabular}{lcccc}")
    lines.append("\\toprule")
    lines.append("Policy & Cycles & Mean CI (\\si{gCO_2/kWh}) & Reduction & $p$-value \\\\")
    lines.append("\\midrule")
    for name, series in data.items():
        if series:
            m = np.mean(series)
            cut = (BASELINE_CI - m) / BASELINE_CI * 100.0
            lines.append(f"{name} & {len(series)} & {m:.2f} & {cut:.1f}\\% & -- \\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")
    lines.append("```\n")

    report_content = "\n".join(lines)
    with open(out_md_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"\nReport generated and saved to:\n  -> {out_md_path}\n")
    print(report_content)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint-name", default="2-week-interim-checkpoint", help="Label for this report")
    parser.add_argument("--max-cycles", type=int, default=None, help="Cap to N cycles (e.g. 336 for Day 14)")
    args = parser.parse_args()

    generate_report(args.checkpoint_name, max_cycles=args.max_cycles)


if __name__ == "__main__":
    main()
