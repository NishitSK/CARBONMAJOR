import React from 'react';
import { Layers } from 'lucide-react';
import SectionHeader from '../components/layout/SectionHeader';
import CompactResultRow from '../components/research/CompactResultRow';
import RawJsonDisclosure from '../components/research/RawJsonDisclosure';
import PoolSweepTable from '../components/research/PoolSweepTable';
import StoryCard from '../components/research/StoryCard';
import { useResearchResult } from '../hooks/useResearchResult';

// The lower-key "everything else" section (design principle 3): every
// remaining research file is represented, but collapsed by default behind
// CompactResultRow, so surfacing all 28 files doesn't turn into a wall of
// always-open cards.
export default function SupportingEvidenceSection() {
  const poolSweep = useResearchResult('pool_generalization_sweep');
  const ablation = useResearchResult('resources_ablation');
  const constrained = useResearchResult('hypothetical_constrained_benchmark');
  const baseline = useResearchResult('baseline_comparison');
  const baselineV1 = useResearchResult('baseline_comparison_threshold_v1');
  const histBenchmark = useResearchResult('historical_decision_benchmark');
  const histBenchmarkCloud = useResearchResult('historical_decision_benchmark_cloud_vantage');
  const latencyBias = useResearchResult('latency_bias_analysis');
  const multiVantage = useResearchResult('multi_vantage_latency');
  const cloudLatency = useResearchResult('cloud_latency');
  const pilotReport = useResearchResult('pilot_report');
  const pilotInstances = useResearchResult('pilot_instances');
  const realCpu = useResearchResult('real_workload_cpu');
  const migrationDemo = useResearchResult('workload_migration_demo');
  const stressTest = useResearchResult('synthetic_migration_stress_test');

  return (
    <section className="section supporting-evidence-section" id="supporting-evidence" style={{ maxWidth: '900px' }}>
      <SectionHeader
        eyebrow="Supporting evidence"
        icon={<Layers size={13} />}
        title="Every other check we ran"
        lede="The two findings above are the headline. Everything below is the additional testing that makes them trustworthy — robustness sweeps, comparisons against simpler baselines, corrections for measurement mistakes we caught ourselves, and the live AWS pilot. Click any row to see the detail."
      />

      <h3 className="supporting-group-title">Does this hold up under different assumptions?</h3>
      <div className="compact-result-list">
        {poolSweep.data && (
          <CompactResultRow
            title="What if the region pool were different?"
            plainLanguage="Removing Sweden or Canada individually makes the other one dominate and the adaptivity gain nearly vanishes; removing both roughly triples it — the finding is about which regions are structurally clean, not something specific to one pair."
          >
            <PoolSweepTable poolSweeps={poolSweep.data.pool_sweeps} />
          </CompactResultRow>
        )}
        {ablation.data && (
          <CompactResultRow
            title="Does the resource-availability scoring term actually matter?"
            stat={`${ablation.data.decisions_changed}/${ablation.data.cycles_analyzed} changed`}
            plainLanguage="No — it was a constant value the whole time, so removing it entirely changes zero decisions. Disclosed rather than hidden."
          >
            <RawJsonDisclosure title="resources_ablation.json" data={ablation.data} />
          </CompactResultRow>
        )}
        {constrained.data && (
          <CompactResultRow
            title="What if regions had limited capacity?"
            stat={`${constrained.data.hypothetical_efficiency_pct.toFixed(1)}% efficiency`}
            plainLanguage="A hypothetical capacity-constrained scenario, testing whether the scheduler still finds a good answer when its favorite regions can't take unlimited load."
          >
            <RawJsonDisclosure title="hypothetical_constrained_benchmark.json" data={constrained.data} />
          </CompactResultRow>
        )}
      </div>

      <h3 className="supporting-group-title">How does this compare to simpler baselines?</h3>
      <div className="compact-result-list">
        {baseline.data && baselineV1.data && (
          <CompactResultRow
            title="Scheduler vs. round-robin vs. always-cheapest vs. fixed region"
            stat={`${baseline.data.scheduler_avg_ci.toFixed(0)}g avg CI`}
            plainLanguage="A scoring-logic bug fix (linear → threshold-based latency scoring) improved the scheduler's average from 184.9g to 174.8g on the same 13 real pilot cycles — the raw measurements didn't change, only how they're weighed."
          >
            <RawJsonDisclosure title="baseline_comparison.json (pre-fix)" data={baseline.data} />
            <RawJsonDisclosure title="baseline_comparison_threshold_v1.json (post-fix)" data={baselineV1.data} />
          </CompactResultRow>
        )}
        {histBenchmark.data && histBenchmarkCloud.data && (
          <CompactResultRow
            title="Historical backtest, before and after fixing a latency-measurement bias"
            stat={`${histBenchmark.data.scheduler_avg_ci.toFixed(0)}g → ${histBenchmarkCloud.data.scheduler_avg_ci.toFixed(0)}g`}
            plainLanguage="Using biased, single-vantage-point latency estimates, the scheduler looked far worse (360.7g avg) than it really was — real EC2-to-EC2 latency measurements cut that to 22.1g avg on the same decisions."
          >
            <RawJsonDisclosure title="historical_decision_benchmark.json (biased latency)" data={histBenchmark.data} />
            <RawJsonDisclosure title="historical_decision_benchmark_cloud_vantage.json (real latency)" data={histBenchmarkCloud.data} />
          </CompactResultRow>
        )}
      </div>

      <h3 className="supporting-group-title">Measurement corrections we caught ourselves</h3>
      <div className="compact-result-list">
        {latencyBias.data && (
          <CompactResultRow
            title="The latency bug: distance from one laptop, not real network latency"
            stat={`r² = ${latencyBias.data.model.r_squared.toFixed(2)}`}
            plainLanguage="Our first latency numbers correlated almost perfectly with distance from a single home computer — that's not real network latency, that's a measurement artifact. This is the analysis that caught it."
          >
            <RawJsonDisclosure title="latency_bias_analysis.json" data={latencyBias.data} />
          </CompactResultRow>
        )}
        {multiVantage.data && cloudLatency.data && (
          <CompactResultRow
            title="The fix: real latency, averaged across 6 real vantage points"
            plainLanguage="Real EC2-to-EC2 latency measured from 6 different AWS regions, averaged, to correct the single-vantage bias above. These corrected numbers are what the scheduler's SLA filter uses today."
          >
            <RawJsonDisclosure title="multi_vantage_latency.json (full matrix)" data={multiVantage.data} />
            <RawJsonDisclosure title="cloud_latency.json (averaged, in use)" data={cloudLatency.data} />
          </CompactResultRow>
        )}
      </div>

      <h3 className="supporting-group-title">The live AWS pilot</h3>
      <div className="compact-result-list">
        {pilotReport.data && pilotInstances.data && (
          <CompactResultRow
            title="Real instances, real latency, running in 12 AWS regions"
            stat={`${pilotReport.data.n_cycles} cycles`}
            plainLanguage="The scheduler didn't just run in simulation — it was deployed to real EC2 instances across 12 AWS regions and made real decisions using real, live grid data."
          >
            <RawJsonDisclosure title="pilot_report.json" data={pilotReport.data} />
            <RawJsonDisclosure title="pilot_instances.json" data={pilotInstances.data} />
          </CompactResultRow>
        )}
        {realCpu.data && (
          <CompactResultRow
            title="Real CPU load measured on the pilot instances"
            plainLanguage="Actual CloudWatch CPU utilization captured during real workload execution on the pilot instances — not simulated load."
          >
            <RawJsonDisclosure title="real_workload_cpu.json" data={realCpu.data} />
          </CompactResultRow>
        )}
      </div>

      {migrationDemo.data && (
        <StoryCard title="A real workload, deployed to the scheduler's top-ranked region">
          <p>
            On {new Date(migrationDemo.data.timestamp).toUTCString()}, the scheduler picked{' '}
            <strong style={{ color: 'var(--accent)' }}>{migrationDemo.data.scheduler_decision.region}</strong> (carbon intensity{' '}
            {migrationDemo.data.scheduler_decision.carbon_intensity}g, {migrationDemo.data.scheduler_decision.latency_ms}ms latency).
            A real job was deployed there via SSM and completed successfully, with a confirmed CPU spike of{' '}
            {migrationDemo.data.confirmed_peak_cpu_pct}% captured on CloudWatch.
          </p>
          <p style={{ marginTop: '0.5rem', fontSize: '0.78rem', color: 'var(--text-faint)' }}>
            {migrationDemo.data.scope_note}
          </p>
        </StoryCard>
      )}

      {stressTest.data && (
        <StoryCard title="Migration continuity, stress-tested across repeated region switches">
          <p>
            {stressTest.data.n_migrations} migrations across {stressTest.data.n_cycles} forced cycles, final counter{' '}
            {stressTest.data.final_counter}, continuity confirmed on every single one:{' '}
            <strong style={{ color: stressTest.data.all_continuity_confirmed ? 'var(--spectrum-clean)' : 'var(--danger)' }}>
              {stressTest.data.all_continuity_confirmed ? 'yes, all confirmed' : 'not all confirmed'}
            </strong>.
          </p>
          <RawJsonDisclosure title="synthetic_migration_stress_test.json" data={stressTest.data} />
        </StoryCard>
      )}
    </section>
  );
}
