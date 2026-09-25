import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import TopNavbar from '../components/layout/TopNavbar';
import GuidedTourModal from '../components/common/GuidedTourModal';
import { useTour } from '../context/TourContext';
import { 
  Compass, ShieldCheck, Cpu, Zap, Activity, BookOpen, 
  HelpCircle, ArrowRight, Play, CheckCircle2, ExternalLink 
} from 'lucide-react';

export default function AboutPage() {
  const [isTourOpen, setIsTourOpen] = useState(false);
  const { startTour } = useTour();
  const navigate = useNavigate();

  const caseStudies = [
    {
      title: "1. Fleet Console & Workload Dispatcher",
      badge: "Console Walkthrough",
      color: "var(--primary)",
      route: "/console",
      desc: "Region fleet and jurisdiction-constrained dispatch. Shows how data sovereignty (India DPDP, US HIPAA) locks each workload stream to a set of regions.",
      sample: "Each stream is scored only over its allowed regions; the chosen region and cut are computed live, so the numbers move with the grid.",
      controls: "Filter by region group, then press Dispatch to score a stream. Dispatch is simulated \u2014 no cloud command is sent."
    },
    {
      title: "2. 3-Stage Temporal Forecasting",
      badge: "Forecasting Walkthrough",
      color: "var(--clean)",
      route: "/forecasting",
      desc: "Dual-model trajectory comparison: Neural CarbonLSTM vs Statistical ARIMA(2,1,2). Evaluates SLA sensitivity across 3h, 6h, and 12h windows.",
      sample: "Verified track record decides what is trusted: CarbonLSTM is ~68-72% directionally correct, ARIMA ~45-53%, so ARIMA is held at run-now.",
      controls: "Click Stage 1 (3h), Stage 2 (6h), or Stage 3 (12h) to inspect step-by-step hourly forecasts."
    },
    {
      title: "3. 24-Hour Solar Trail & Flight Arcs",
      badge: "Playground Walkthrough",
      color: "var(--moderate)",
      route: "/playground",
      desc: "Interactive global simulation tracking Earth's rotation. Draws dynamic curved flight paths from Virginia to optimal hydro and solar datacenters.",
      sample: "Define the regions you run in, set a latency budget, and watch the ranking change as weights and the hour change.",
      controls: "Click [Run 24h Sim] or scrub the 24-hour timeline bar to see dynamic multi-hop handoffs."
    },
    {
      title: "4. Live 3-Account Cloud Stream",
      badge: "Pilot Telemetry Walkthrough",
      color: "#f43f5e",
      route: "/pilot",
      desc: "Continuous empirical cloud pilot: three independent policy pipelines (Adaptive, LSTM, ARIMA) running in one AWS account, executed over AWS Systems Manager (SSM) with no open SSH ports.",
      sample: "Real t3.micro instances across the region fleet; cycles are hourly-triggered, with 10-21 completing per day in practice.",
      controls: "Toggle between account stream logs and monitor real-time SSM execution command statuses."
    }
  ];

  return (
    <div className="app-layout">
      <TopNavbar />
      
      {/* Interactive Tour Modal */}
      <GuidedTourModal isOpen={isTourOpen} onClose={() => setIsTourOpen(false)} />

      <main className="main-content">
        {/* Header Ribbon with Interactive Tutorial Launcher */}
        <div className="card" style={{ background: 'var(--surface-card)', border: '1px solid var(--border-light)', padding: '2.5rem 3rem', marginBottom: '3rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '2rem' }}>
            <div style={{ maxWidth: '750px' }}>
              <span className="jurisdiction-badge" style={{ color: 'var(--primary)', borderColor: 'rgba(59, 130, 246, 0.4)' }}>
                Interactive Application Guide & Case Studies
              </span>
              <h1 className="page-title" style={{ fontSize: '2.4rem', marginTop: '0.5rem' }}>
                About CADSS Carbon-Aware Scheduler
              </h1>
              <p className="page-subtitle" style={{ fontSize: '1.15rem', lineHeight: 1.6 }}>
                A decision-support system for where — and when — cloud workloads should run, under data-residency
                and latency constraints. Its main finding: choosing the right region once captures about 97% of the
                achievable carbon savings; real-time adaptivity adds only +2.7% on held-out data.
              </p>
            </div>

            {/* Launch Guided Tutorial Button */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', alignItems: 'center' }}>
              <button
                className="btn btn-primary"
                style={{ padding: '1.1rem 2.25rem', fontSize: '1.2rem', fontWeight: 800, borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', gap: '0.75rem', boxShadow: '0 10px 25px rgba(59, 130, 246, 0.3)' }}
                onClick={() => startTour(0)}
              >
                <Play size={22} fill="#fff" /> Start Live On-Screen Tour
              </button>
              <button
                className="btn btn-outline"
                style={{ padding: '0.6rem 1.25rem', fontSize: '0.9rem' }}
                onClick={() => setIsTourOpen(true)}
              >
                <BookOpen size={16} /> Open Case Study Modal
              </button>
            </div>
          </div>
        </div>

        {/* Interactive Case Studies: Walkthrough of Each Part */}
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title" style={{ fontSize: '1.5rem' }}>Sample Case Studies & Control Guides (By Application Part)</h2>
              <p style={{ fontSize: '0.95rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
                Select any part below to understand the real-world scenario, interactive controls, and open the live page
              </p>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.75rem', marginTop: '1rem' }}>
            {caseStudies.map((cs, i) => (
              <div key={i} className="card" style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)', padding: '1.75rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', marginBottom: 0 }}>
                <div>
                  <span className="jurisdiction-badge" style={{ color: cs.color, borderColor: cs.color }}>
                    {cs.badge}
                  </span>
                  <h3 style={{ fontSize: '1.25rem', fontWeight: 700, margin: '0.4rem 0 0.6rem' }}>{cs.title}</h3>
                  <p style={{ fontSize: '0.95rem', color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: '1rem' }}>
                    {cs.desc}
                  </p>

                  <div style={{ background: 'var(--surface)', padding: '0.85rem 1rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', marginBottom: '0.75rem' }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-faint)', textTransform: 'uppercase' }}>Key Controls:</div>
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-main)', marginTop: '0.2rem' }}>{cs.controls}</div>
                  </div>

                  <div style={{ background: 'var(--clean-bg)', border: '1px solid var(--clean-border)', padding: '0.85rem 1rem', borderRadius: 'var(--radius-sm)', marginBottom: '1.25rem' }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--clean)', textTransform: 'uppercase' }}>Sample Outcome:</div>
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-main)', marginTop: '0.2rem', fontWeight: 600 }}>{cs.sample}</div>
                  </div>
                </div>

                <button
                  className="btn btn-outline"
                  style={{ width: '100%', justifyContent: 'center', fontSize: '0.95rem', padding: '0.75rem' }}
                  onClick={() => navigate(cs.route)}
                >
                  Open Live {cs.badge.split(' ')[0]} <ExternalLink size={16} />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* 3 Pillars of CADSS Architecture */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '2rem', marginBottom: '3rem' }}>
          {/* Pillar 1 */}
          <div className="card" style={{ marginBottom: 0 }}>
            <div style={{ background: 'var(--bg-subtle)', width: '48px', height: '48px', borderRadius: 'var(--radius-sm)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1.25rem', border: '1px solid var(--border)' }}>
              <Compass size={24} color="var(--primary)" />
            </div>
            <h2 style={{ fontSize: '1.35rem', fontWeight: 700, marginBottom: '0.6rem' }}>1. Sovereign Spatial Routing</h2>
            <p style={{ fontSize: '0.95rem', color: 'var(--text-muted)', lineHeight: 1.7 }}>
              Routes unconstrained workloads dynamically to global clean power hubs (Sweden hydro, Quebec hydro) while enforcing strict jurisdictional fences (APAC DPDP, US HIPAA) for sensitive enterprise workloads.
            </p>
          </div>

          {/* Pillar 2 */}
          <div className="card" style={{ marginBottom: 0 }}>
            <div style={{ background: 'var(--bg-subtle)', width: '48px', height: '48px', borderRadius: 'var(--radius-sm)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1.25rem', border: '1px solid var(--border)' }}>
              <Cpu size={24} color="var(--clean)" />
            </div>
            <h2 style={{ fontSize: '1.35rem', fontWeight: 700, marginBottom: '0.6rem' }}>2. 3-Stage Temporal Shifting</h2>
            <p style={{ fontSize: '0.95rem', color: 'var(--text-muted)', lineHeight: 1.7 }}>
              Combines deep neural <strong>CarbonLSTM</strong> models with <strong>ARIMA(2,1,2)</strong> statistical models across 3 SLA horizons (3h tight, 6h standard, 12h diurnal) to shift delay-tolerant batch jobs into solar/wind peaks.
            </p>
          </div>

          {/* Pillar 3 */}
          <div className="card" style={{ marginBottom: 0 }}>
            <div style={{ background: 'var(--bg-subtle)', width: '48px', height: '48px', borderRadius: 'var(--radius-sm)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1.25rem', border: '1px solid var(--border)' }}>
              <ShieldCheck size={24} color="var(--moderate)" />
            </div>
            <h2 style={{ fontSize: '1.35rem', fontWeight: 700, marginBottom: '0.6rem' }}>3. 6-Layer Failsafe Engine</h2>
            <p style={{ fontSize: '0.95rem', color: 'var(--text-muted)', lineHeight: 1.7 }}>
              Each forecaster earns its own threshold from its verified track record: CarbonLSTM may delay a job only when it forecasts a <strong>&ge; 15%</strong> saving, while ARIMA is held at run-now until its accuracy recovers. Latency SLA guards apply on top.
            </p>
          </div>
        </div>

        {/* Frequently Asked Questions (FAQ) */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title" style={{ fontSize: '1.5rem' }}>Frequently Asked Questions (FAQ)</h2>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.35rem' }}>
                Q: Why don't all workloads just run in Sweden?
              </h3>
              <p style={{ fontSize: '0.95rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                While Sweden is powered by hydro and nuclear (~18 gCO2/kWh), enterprise regulations like US HIPAA, EU GDPR, and India DPDP forbid moving sensitive customer data out of their origin country. CADSS uses temporal shifting to find optimal green hours <em>inside</em> compliant regions, saving +30% carbon without violating sovereignty.
              </p>
            </div>

            <div style={{ paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.35rem' }}>
                Q: What is the No-Regret Guard?
              </h3>
              <p style={{ fontSize: '0.95rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                Forecasts are noisy, and a wrong one costs queue time for no benefit. Before any delay is allowed, the guard checks the predicted saving against a threshold each model earned from its own verified accuracy (CarbonLSTM: &ge; 15%; ARIMA: never, at present). If the saving falls short, the job runs at t=0.
              </p>
            </div>

            <div style={{ paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.35rem' }}>
                Q: Is what I am looking at real, or simulated?
              </h3>
              <p style={{ fontSize: '0.95rem', color: 'var(--text-muted)', lineHeight: 1.6 }}>
                By default, simulated. Every page runs on a simulated grid model so the app needs no AWS account, no backend and no licensed carbon data; the Dev Options control in the top bar shows the current source and unlocks live data with a PIN. The pilot behind Pilot Telemetry is real: real EC2 instances across the region fleet, executed over AWS Systems Manager without open SSH ports, and real measured grid data — but it runs as three independent policy pipelines inside one AWS account, not three separate accounts.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
