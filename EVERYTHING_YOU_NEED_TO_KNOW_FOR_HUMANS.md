# Everything you need to know — for humans

A plain-language guide to this project: what it does, what it found, how to run it, and what
it does not claim. If you are an AI assistant, read
[EVERYTHING_YOU_NEED_TO_KNOW_FOR_AI.md](EVERYTHING_YOU_NEED_TO_KNOW_FOR_AI.md) instead.

Last updated: 1 October 2026.

## The idea in one paragraph

A cloud workload can usually run in more than one region, and the electricity behind each
region is cleaner or dirtier depending on the place and the hour. CADSS decides where, and
sometimes when, to run a workload so that it causes less carbon, without breaking the
workload's latency limit or its data-residency rules. The limits come first; carbon is only
optimised among the options that are still allowed.

## How it decides

1. **Filter.** Remove every region that breaks the latency limit (200 ms by default) or the
   workload's residency rule.
2. **Score.** Rank what is left by a weighted score: carbon intensity 40%, latency 30%,
   available resources 30%. The weights can be changed.
3. **Explain.** Return the ranking, the rejected regions with the reason for each, and the pick.
4. **Optionally wait.** If the workload can be delayed, a forecast may suggest a cleaner hour.
   A guard decides whether that forecast is trustworthy enough to act on.

## The parts

- **Scoring engine** — the filter-and-score step above. One endpoint, `POST /score`.
- **Forecasters** — ARIMA, a classical statistical model, and CarbonLSTM, a small neural
  network trained per electricity zone. Each predicts carbon intensity a few hours ahead.
- **No-regret guard** — a rule that only lets a forecaster delay work if its past forecasts,
  checked against what really happened, actually saved carbon.
- **Placement Audit** — the web app. It sorts a fleet into: move, shift in time, stay, blocked
  by cost, never move, or fix compliance first, with the reason and the tonnes of CO2 for each.
- **Live pilot** — the same logic running on real AWS machines for 19 days.

## What it found

**1. Most of the saving comes from picking a clean region once.**
Replayed over five years of hourly grid data (2021–2025, 13 zones, 7,304 decisions), the
scheduler cut mean carbon intensity by about 94.7% against always using one fixed region. But
simply always choosing the historically cleanest region gets nearly all of that. The extra
gained by re-deciding every hour is 6.5% on the data it was tuned on and 2.7% on two held-out
years (2024–2025). That 2.7% is statistically real, and it is small.

**2. A forecast with lower error can still make worse decisions.**
In the live pilot, every forecast was later checked against the measured value: 38,185
forecasts in total. ARIMA had the smaller error one hour ahead, yet the delays it recommended
lost carbon overall, so the guard switched it off. The LSTM was right about the direction of
change 63% to 78% of the time depending on how far ahead it looked, and stayed enabled at 3, 6
and 12 hours.

**3. The guard can also withdraw trust.**
On 20 September the same rule found the LSTM's 1-hour forecasts were not paying off and
disabled that horizon too. In this pilot that changed no real decision, because the 1-hour
stage could not delay anything anyway. The point is that the rule works in both directions.

**4. Retraining on newer data helped a little, and it is not yet proven.**
After the pilot, the LSTM was retrained with data up to July 2026 and tested on August and
September 2026, which no model had seen.

| Model | Bad delays (regret) | Carbon saved per decision |
|---|---|---|
| Weights used in the pilot | 21.8% | 4.37% |
| Same data, retrained again (control) | 20.8% | 4.40% |
| Retrained with 2026 data | 19.3% | 4.61% |

The retrained model is better, but the control row shows that retraining alone, with no new
data, moves the numbers by a similar amount. Each model was trained once, so this is a small,
unconfirmed improvement.

## The live pilot at a glance

| | |
|---|---|
| When | 9 to 28 September 2026 |
| Where | One AWS account, 12 instances across regions, one orchestrator in `us-east-1` |
| What ran | Three policies side by side: reactive (never delays), CarbonLSTM, ARIMA |
| How much | 390, 390 and 391 scheduling cycles; 38,185 verified forecasts |
| Status | Finished. All instances terminated. |

## What this project does not claim

- It was tested on **one cloud provider** for **19 days in one season**.
- It uses **average** carbon intensity, not marginal. The two can disagree about which hour
  is cleanest.
- Scheduling cycles were irregular in the first week, and the Tokyo instance was stopped from
  13 September, so jobs sent there failed.
- For the first days of the pilot, a defect made the live forecasters learn from year-old
  history. Results are reported both pooled and split by period for that reason.
- The 94.7% figure is not the benefit of clever scheduling. It is mostly the benefit of not
  running in a dirty region.

## Run it yourself

You need Python 3.10 or newer and Node.js.

Backend:

```bash
cd carbon_scheduler
pip install fastapi uvicorn pydantic python-dotenv requests statsmodels torch
python -m uvicorn api:app --host 127.0.0.1 --port 8001 --reload
```

Frontend, in a second terminal:

```bash
cd carbon_scheduler_ui
npm install
npm run dev
```

Open `http://localhost:5173`. The pages:

| Page | What it is for |
|---|---|
| `/` | Placement Audit: triage a fleet of workloads |
| `/forecasting` | Both models' forecasts and the guard's verdict |
| `/pilot` | What the live pilot decided and dispatched |
| `/console` | Score one workload across your own servers |
| `/playground` | Change weights and servers and watch the pick change |
| `/report` | Printable audit |
| `/about` | Claims and limits |

The scoring, audit and UI work straight from a clone. Historical replay and LSTM forecasting
need carbon-intensity history, which is not included (see below).

## About the data

Carbon-intensity data comes from [Electricity Maps](https://www.electricitymaps.com) under
academic access. Their terms allow academic use but not redistribution, so this repository
contains no measured carbon-intensity values and no trained model weights. What is published,
in `carbon_scheduler/data/public/`, is derived evidence: forecast errors, whether the
direction was right, whether a delay was regretted, percentage savings, decisions and
dispatch outcomes. That is enough to recompute every table in the report.

To reproduce the replay and forecasting results you need your own Electricity Maps token in a
`.env` file (copy `.env.example`), then `scripts/import_yearly_csv.py` and
`scripts/train_lstm.py`. Academic access is free on an institutional address.

One warning: `scripts/download_ci_history.py` replaces the history files with only the last
10 days. Do not run it after importing several years of data.

## Where things are

```text
carbon_scheduler/        Python backend: API, scoring, forecasters, guard, AWS pilot code
  scripts/               one re-runnable script per result in the report
  data/                  result files; data/public/ is the publishable evidence
carbon_scheduler_ui/     React web app
README.md                overview, API reference, architecture
```

## Words used here

- **Carbon intensity** — grams of CO2-equivalent emitted per kilowatt-hour of electricity.
- **Zone** — an electricity grid area, for example Sweden or the US Mid-Atlantic grid.
- **SLA** — the service limits a workload must meet; here, mainly a latency limit.
- **Horizon** — how far ahead a forecast looks: 1, 3, 6 or 12 hours.
- **Regret** — a delay that turned out worse than running immediately.
- **Persistence** — the simplest forecast: assume the next hours equal the current hour.
- **Guard threshold** — the minimum saving a forecast must promise before it may delay work.

## Credits

Undergraduate research project, Sahyadri College of Engineering and Management. Data by
Electricity Maps. If you build on this work, attribute the underlying data to them.
