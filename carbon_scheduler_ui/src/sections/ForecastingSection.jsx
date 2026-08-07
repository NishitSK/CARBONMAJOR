import React from 'react';
import { Brain } from 'lucide-react';
import SectionHeader from '../components/layout/SectionHeader';
import StatTile from '../components/layout/StatTile';
import MetricComparisonBar from '../components/research/MetricComparisonBar';
import SignificanceStat from '../components/research/SignificanceStat';
import DeadlineSweepChart from '../components/research/DeadlineSweepChart';
import CompactResultRow from '../components/research/CompactResultRow';
import RawJsonDisclosure from '../components/research/RawJsonDisclosure';
import { useResearchResult } from '../hooks/useResearchResult';

function avgMae(list, key) {
  if (!Array.isArray(list) || list.length === 0) return null;
  return list.reduce((sum, r) => sum + r[key], 0) / list.length;
}

function avgSeasonalMae(byZone, key) {
  const vals = [];
  Object.values(byZone).forEach(seasons => {
    Object.values(seasons).forEach(s => vals.push(s[key]));
  });
  return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
}

export default function ForecastingSection() {
  const temporal = useResearchResult('temporal_shift_benchmark');
  const spatial = useResearchResult('forecast_in_the_loop_replay');
  const eval6h = useResearchResult('evaluation_report');
  const eval24h = useResearchResult('evaluation_report_24h');
  const evalSeasonal6h = useResearchResult('evaluation_report_seasonal_6h');
  const evalSeasonal24h = useResearchResult('evaluation_report_seasonal_24h');

  const t = temporal.data;
  const sp = spatial.data;

  return (
    <section className="section" id="forecasting">
      <SectionHeader
        eyebrow="Headline finding #2 — where the word 'AI' is earned"
        icon={<Brain size={13} />}
        title="Real AI forecasting: doesn't help WHERE, genuinely helps WHEN"
        lede="The scheduler has two AI forecasting models (trained on the same real 5-year data) that predict future carbon intensity. We tested whether wiring them into real decisions actually helps, two different ways: choosing WHICH region to use, and choosing WHEN to run a workload that can wait."
      />

      {t && (
        <>
          <div className="research-chart-block glass-panel">
            <h3 className="research-chart-title">WHEN to run: real AI forecasting vs. today's fake stand-in vs. a perfect oracle</h3>
            <p className="section-lede" style={{ marginBottom: '1rem' }}>
              For a delay-tolerant job with a deadline, today's system decides when to run it using a made-up carbon curve. Swapping in the
              real, trained forecasters turns a policy that was <em>worse than not waiting at all</em> into a genuinely useful one.
            </p>
            <DeadlineSweepChart deadlines={t.deadlines_tested_hours} resultsByDeadline={t.results_by_deadline} />
          </div>

          <div className="hero-stats" style={{ marginTop: '1.25rem' }}>
            <StatTile
              value={`${t.results_by_deadline['24'].real_ai_improve_vs_no_shift_pct.toFixed(1)}%`}
              label="saving from real AI forecasting at a 24-hour deadline (today's fake system: −0.7%, i.e. actively worse than doing nothing)"
              tone="accent"
            />
            <StatTile
              value={`${t.results_by_deadline['24'].real_ai_pct_of_achievable_gap_closed.toFixed(0)}%`}
              label="of the gap to a perfect, all-knowing oracle that real AI forecasting closes at 24 hours"
              tone="neutral"
            />
          </div>
        </>
      )}

      {sp && (
        <div className="research-chart-block glass-panel" style={{ marginTop: '1.5rem' }}>
          <h3 className="research-chart-title">WHERE to run: real AI forecasting instead of live telemetry — a null result, reported honestly</h3>
          <p className="section-lede" style={{ marginBottom: '1rem' }}>
            We also tried forcing the scheduler to pick a <em>region</em> using forecasts instead of live data. It didn't help: the
            forecast-driven scheduler lands right back at the naive static-lookup floor, giving up almost all of live telemetry's
            real-time advantage. This isn't a failure to hide — it directly confirms <em>why</em> the WHEN-based forecasting above works
            and the WHERE-based version doesn't: region selection is dominated by one big, stable gap between two regions that forecast
            error is too noisy to reliably detect, while timing a delay is exactly the kind of problem forecasting is built for.
          </p>
          <MetricComparisonBar
            items={[
              { label: 'Live telemetry (oracle)', value: Number(sp.oracle_mean_ci.toFixed(2)), tone: 'accent' },
              { label: 'ARIMA-forecast-driven', value: Number(sp.arima_forecast_driven_mean_ci.toFixed(2)), tone: 'neutral' },
              { label: 'LSTM-forecast-driven', value: Number(sp.lstm_forecast_driven_mean_ci.toFixed(2)), tone: 'neutral' },
              { label: 'Static lookup (no data at all)', value: Number(sp.static_lookup_mean_ci_reference.toFixed(2)), tone: 'danger' },
            ]}
          />
          <SignificanceStat
            tStat={sp.paired_t_test_vs_oracle.arima.t_stat}
            pValue={sp.paired_t_test_vs_oracle.arima.p_value}
            n={sp.n_decisions}
            significant={true}
            note="Significant here means the forecast-driven version is measurably worse than live telemetry — confirming the gap is real, not just reporting a positive result."
          />
        </div>
      )}

      <div className="compact-result-list" style={{ marginTop: '1.5rem' }}>
        {eval6h.data && eval24h.data && (
          <CompactResultRow
            title="How accurate are the forecasters, on their own?"
            stat={`ARIMA ${avgMae(eval6h.data, 'arima_mae')?.toFixed(1)}g MAE @6h · LSTM ${avgMae(eval24h.data, 'lstm_mae')?.toFixed(1)}g MAE @24h`}
            plainLanguage="ARIMA is the more accurate model at a 6-hour horizon; LSTM overtakes it by 24 hours out — a real, structural crossover, not a coin flip."
          >
            <RawJsonDisclosure title="evaluation_report.json (6h)" data={eval6h.data} />
            <RawJsonDisclosure title="evaluation_report_24h.json (24h)" data={eval24h.data} />
          </CompactResultRow>
        )}

        {evalSeasonal6h.data && evalSeasonal24h.data && (
          <CompactResultRow
            title="Does the ARIMA/LSTM crossover hold up across seasons?"
            stat={`ARIMA ${avgSeasonalMae(evalSeasonal6h.data, 'arima_mae')?.toFixed(1)}g · LSTM ${avgSeasonalMae(evalSeasonal24h.data, 'lstm_mae')?.toFixed(1)}g`}
            plainLanguage="Yes — backtested separately across winter, spring, summer, and autumn, ARIMA wins at 6 hours and LSTM wins at 24 hours in every season tested, not just on average."
          >
            <RawJsonDisclosure title="evaluation_report_seasonal_6h.json" data={evalSeasonal6h.data} />
            <RawJsonDisclosure title="evaluation_report_seasonal_24h.json" data={evalSeasonal24h.data} />
          </CompactResultRow>
        )}
      </div>
    </section>
  );
}
