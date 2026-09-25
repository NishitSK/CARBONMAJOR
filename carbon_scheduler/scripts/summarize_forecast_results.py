"""
Summarize Ground-Truth Forecast Verification Performance
Calculates MAE, RMSE, Directional Accuracy, and Regret Rates for all models.
"""

import json
import os
import numpy as np

def run_summary():
    path = os.path.join(os.path.dirname(__file__), "..", "data", "forecast_verification.jsonl")
    if not os.path.exists(path):
        print(f"Error: {path} not found.")
        return

    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    records.append(json.loads(line.strip()))
                except Exception:
                    pass

    print(f"Total Ground-Truth Verified Data Points: {len(records)}")

    groups = {}
    for r in records:
        model = r.get("model_name", r.get("profile", "Unknown"))
        horizon = f"{r.get('horizon_hours', 1)}h"
        key = (model, horizon)
        if key not in groups:
            groups[key] = {
                "ae": [],
                "se": [],
                "dir": [],
                "regret": [],
                "savings": [],
                "predicted": [],
                "actual": []
            }
        groups[key]["ae"].append(r.get("absolute_error", 0))
        groups[key]["se"].append(r.get("squared_error", 0))
        groups[key]["dir"].append(1 if r.get("directional_correct") else 0)
        groups[key]["regret"].append(1 if r.get("regret_occurred") else 0)
        groups[key]["savings"].append(r.get("actual_savings_pct", 0))
        groups[key]["predicted"].append(r.get("predicted_ci", 0))
        groups[key]["actual"].append(r.get("actual_ci", 0))

    print("\n" + "=" * 90)
    print(f"{'Model Name':<18} {'Horizon':<10} {'Samples (N)':<12} {'MAE (gCO2)':<14} {'RMSE (gCO2)':<14} {'Dir Acc (%)':<14} {'Regret (%)':<12}")
    print("=" * 90)
    
    for (model, horizon), d in sorted(groups.items()):
        n = len(d["ae"])
        mae = np.mean(d["ae"])
        rmse = np.sqrt(np.mean(d["se"]))
        dir_acc = np.mean(d["dir"]) * 100
        regret_rate = np.mean(d["regret"]) * 100
        print(f"{model:<18} {horizon:<10} {n:<12} {mae:<14.2f} {rmse:<14.2f} {dir_acc:<14.1f} {regret_rate:<12.1f}")

    print("=" * 90)

    # Statistical significance t-test between LSTM and ARIMA at 6h
    lstm_6h_ae = groups.get(("LSTM", "6h"), {}).get("ae", [])
    arima_6h_ae = groups.get(("ARIMA(2,1,2)", "6h"), {}).get("ae", [])
    
    if lstm_6h_ae and arima_6h_ae:
        from scipy import stats
        min_len = min(len(lstm_6h_ae), len(arima_6h_ae))
        t_stat, p_val = stats.ttest_ind(lstm_6h_ae[:min_len], arima_6h_ae[:min_len])
        print(f"\n[Statistical Test at 6h Horizon]")
        print(f"LSTM MAE: {np.mean(lstm_6h_ae):.2f} g vs ARIMA MAE: {np.mean(arima_6h_ae):.2f} g")
        print(f"t-statistic: {t_stat:.4f} | p-value: {p_val:.4e} {'(Statistically Significant p < 0.05)' if p_val < 0.05 else ''}")

if __name__ == "__main__":
    run_summary()
