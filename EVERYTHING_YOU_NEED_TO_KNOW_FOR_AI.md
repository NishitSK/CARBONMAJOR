# Everything you need to know — for AI assistants

Read this before changing anything in this repository. It is written for coding agents
(Claude Code, Copilot, Cursor and similar). The human-oriented version is
[EVERYTHING_YOU_NEED_TO_KNOW_FOR_HUMANS.md](EVERYTHING_YOU_NEED_TO_KNOW_FOR_HUMANS.md).

Last verified against the code and data: 1 October 2026.

## 1. What this project is

CADSS is an SLA-first, carbon-aware cloud scheduler: an undergraduate research project
(Sahyadri College of Engineering and Management). For each workload it filters candidate
regions by a latency limit and data-residency rules, then ranks the survivors by a weighted
score of carbon intensity, latency and resources. On top of that sit two forecasters (ARIMA
and a per-zone LSTM), a no-regret guard that decides whether a forecast may delay work, and a
Workload Placement Audit UI.

The project is in its write-up phase. The live AWS pilot is finished and torn down. Prefer
finishing and correcting what exists over adding features.

## 2. Hard rules

1. **Never publish Electricity Maps data.** Academic access permits use, not redistribution.
   Nothing committed may contain a measured or predicted carbon-intensity level or series.
   Banned as numeric fields: `carbon_intensity`, `carbonIntensity`, `actual_ci`, `origin_ci`,
   `current_ci`, `predicted_*_ci`, forecast series, rankings with intensity values.
   Allowed: error magnitudes (MAE, RMSE), direction flags, regret flags, percentages, counts,
   decisions, offsets, guard status, dispatch outcomes.
2. **Scan before every push:**
   ```bash
   git grep -E '"(carbon_intensity|actual_ci|origin_ci|current_ci)":\s*[0-9]'
   ```
   It must print nothing. Also check `git status` for any new file under
   `carbon_scheduler/data/` that is not in `data/public/`.
3. **Publish evidence only through `scripts/export_public_evidence.py`**, which writes the
   derived subset to `carbon_scheduler/data/public/`. Do not hand-copy raw logs.
4. **Never commit** `.env`, tokens, instance IDs, public IPs, `models/*.pt`, anything under
   `data/history/`, `data/raw_yearly/` or `data/retrain/`. Trained weights are derived from
   licensed data and stay local.
5. **Do not run `scripts/download_ci_history.py` over an existing multi-year history.** It
   fetches the trailing 10 days and replaces each `data/history/ci_history_{zone}.json`. Use
   `scripts/download_history_range.py`, which writes to `data/retrain/` instead.
6. **Three tracked files are scrubbed copies:** `data/forecast_calibration.json`,
   `data/workload_migration_demo.json`, `data/regions.json`. Any sync from a raw source must
   exclude them, or measured values come back into tracked files.
7. **Do not re-enable a forecaster automatically.** `scripts/reverify_and_calibrate.py`
   recommends thresholds; a human edits the `applied` block of `forecast_calibration.json`.
8. **Do not start AWS resources without the owner's explicit request.** The fleet costs money
   and `aws/cloud_teardown_check.sh` has a `TEARDOWN_DATE` that must be set before any launch.
9. **No invented numbers.** Every figure in a doc must trace to a script output or a file in
   `data/`. If you did not run it, say so.
10. **Style:** no emoji, no decorative banners in new docs, match the surrounding code.

## 3. Facts that are easy to get wrong

- The pilot ran in **one AWS account** with three policy pipelines. Never write "three
  accounts". (`aws/provision_multi_account.py` exists but was not how the pilot ran.)
- The pilot ran **9 to 28 September 2026** and is **over**. Do not describe it as running.
- Final record: **390 / 390 / 391 cycles** (reactive / CarbonLSTM / ARIMA) and
  **38,185 verified forecasts**. The raw verification file has 38,187 lines; two are corrupt
  and every script skips them.
- The **Tokyo instance existed but was stopped** from 13 September 14:33 UTC. Dispatches to it
  failed; it was not missing.
- 13 electricity zones are forecast and scored; the fleet was 12 instances plus an orchestrator
  in `us-east-1`.
- **Guard at teardown:** ARIMA disabled at 1, 3, 6 and 12 h. CarbonLSTM disabled at 1 h, 15%
  promised-saving threshold at 3, 6 and 12 h. A threshold of `1000.0` in
  `forecast_calibration.json` means "never delay".
- The 1 h guard change **never altered a live decision**: the runner's 1 h stage has a single
  candidate hour (`preds[:1]`) so it cannot delay, and dispatch used the 6 h stage.
- CarbonLSTM takes a 24-hour window and outputs **6 hours**. Hour-of-day features assume a
  gap-free hourly series.
- `train_zone()` is full-batch, 60 epochs, **unseeded**. Two runs on the same data differ. Seed
  it from the caller if you need a comparison (see `scripts/retrain_lstm_sets.py`).
- The headline replay saving (about 94.7% against a fixed carbon-blind region) is almost all
  **static region choice**. The adaptive part is +6.5% in-sample and +2.7% on the 2024–2025
  held-out split. Do not present 94.7% as the benefit of adaptivity.
- Forecast error does not predict decision quality. ARIMA had the lower 1 h error and the
  worse decisions. Persistence beats the LSTM on error in most zones and never delays, so it
  saves nothing. Keep error metrics and decision metrics separate in any write-up.

## 4. Repository map

```text
carbon_scheduler/                 FastAPI backend (Python 3.10+, tested on 3.11)
  api.py                          /score, /forecast, /forecasting/*, /pilot/telemetry, ...
  history_api.py                  licensed history lookup; 403 unless CADSS_SERVE_LICENSED_HISTORY=1
  research_api.py                 manifest of reproducible results shown on the site
  config.py                       paths, DEFAULT_WEIGHTS (carbon 0.4, latency 0.3, resources 0.3),
                                  DEFAULT_MAX_LATENCY 200 ms, SCORING_METHOD_VERSION "threshold_v1"
  services/
    scheduler.py                  SLA filter + weighted score (the core engine)
    forecaster.py                 ARIMA(2,1,2)
    lstm_forecaster.py            CarbonLSTM: model, train_zone(), predict()
    real_temporal_forecaster.py   forecast-driven temporal shifting
    failsafe_engine.py            failsafe logic + no-regret guard
    forecast_tracker.py           records forecasts, verifies them at the target hour
    forecast_calibration.py       calibration instrument (recommends thresholds)
    electricity_service.py        Electricity Maps client, REGION_MAP (region -> zone)
  aws/                            orchestrator deploy, three pilot runners, SSM dispatch,
                                  latency measurement, provisioning, teardown
  scripts/                        one script per reported result (see section 6)
  data/                           result JSON (tracked) and raw logs (gitignored)
  data/public/                    derived, publishable evidence
  models/                         region.py, workload.py; *.pt weights are gitignored

carbon_scheduler_ui/              React 18 + Vite 5 frontend
  src/pages/                      Audit, AuditReport, Console, Forecasting, PilotTelemetry,
                                  Playground, Home, About
  src/sim/                        in-browser port of the scorer and audit model
  src/sim/__tests__/              parity tests against the Python engine
```

Everything else at the repository root on the owner's machine (paper drafts, reports, notes,
`HANDOFF.md`) is gitignored and is not part of the published repo.

## 5. Run and test

```bash
# backend, from carbon_scheduler/
pip install fastapi uvicorn pydantic python-dotenv requests statsmodels torch
python -m uvicorn api:app --host 127.0.0.1 --port 8001 --reload

# frontend, from carbon_scheduler_ui/
npm install
npm run dev        # http://localhost:5173, proxies /api/* to :8001
npm test           # vitest: scoring, audit and Python-parity tests
```

`ELECTRICITY_MAPS_TOKEN` goes in `.env` at the repository root (copy `.env.example`). Without
licensed history and weights, the scoring engine, the audit and the UI still work; historical
replay and LSTM forecasting do not.

If you change the Python scoring logic, regenerate the parity fixture
(`scripts/export_scoring_fixture.py`) and run `npm test`. The JS port in `src/sim/scoring.js`
must stay in step with `services/scheduler.py`.

## 6. Which script produces which result

| Result | Script | Output |
|---|---|---|
| Five-year replay vs fixed and round-robin | `historical_decision_benchmark.py` | `data/historical_decision_benchmark.json` |
| Static lookup baseline (+6.5% in-sample) | `static_lookup_baseline.py` | `data/static_lookup_baseline.json` |
| Held-out split (+2.7%, n_eff about 1,221) | `held_out_generalization_test.py` | `data/held_out_generalization_test.json` |
| Significance of the adaptive gain | `significance_test_adaptivity.py` | `data/significance_test_adaptivity.json` |
| Offline forecaster backtests | `evaluate_forecasters*.py` | `data/evaluation_report*.json` (gitignored) |
| Live verification summary | `summarize_forecast_results.py` | stdout |
| Guard calibration | `reverify_and_calibrate.py` | recommendation into `forecast_calibration.json` |
| Public evidence | `export_public_evidence.py` | `data/public/*.jsonl` |
| Retraining experiment | `download_history_range.py`, `retrain_lstm_sets.py`, `backtest_lstm_retrain.py` | `data/public/lstm_retrain_backtest.json` |

## 7. State of the work (1 October 2026)

Done:
- Scoring engine, forecasters, guard, verification tracker, audit UI.
- Live pilot, 9–28 September 2026, final evidence exported to `data/public/`.
- Retraining experiment: the LSTM retrained through July 2026 is slightly better than the
  pilot weights on held-out August–September data (regret 21.8% to 19.3%, saving per decision
  4.37% to 4.61%), but the gain is within retraining noise and each set was trained once.
  Treat it as unconfirmed.

Open:
- Confirm the retraining result with several seeds per set before claiming it.
- Known pilot defects to fix before any second pilot: no start-up check that every instance is
  running; no dispatch-target liveness check in the SLA filter; the 1 h stage cannot delay;
  verification scores a promise at the horizon instead of at the chosen offset; decision and
  verification records carry no `model_version` field.
- Limits to state in any write-up: one provider, 19 days, one season, average (not marginal)
  carbon intensity, irregular cycles in the first week.

## 8. Working agreement

- Read before you overwrite. Check for an existing file before creating one with the same job.
- Keep docs true. If you change behaviour, update `README.md` and both
  `EVERYTHING_YOU_NEED_TO_KNOW_*` files in the same commit, and update the "last verified" date.
- Report what actually happened: failing tests, skipped steps, numbers you did not reproduce.
- Ask before changing core scoring or guard logic, deleting data, or touching cloud resources.
