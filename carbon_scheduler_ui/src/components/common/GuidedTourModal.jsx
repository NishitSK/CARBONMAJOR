import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  X, ArrowRight, ArrowLeft, CheckCircle2, Compass, ShieldCheck, 
  Cpu, Activity, Zap, ExternalLink, Play, Sliders, Clock
} from 'lucide-react';

export default function GuidedTourModal({ isOpen, onClose }) {
  const [currentStep, setCurrentStep] = useState(0);
  const navigate = useNavigate();

  if (!isOpen) return null;

  const sampleCases = [
    {
      part: "Part 1: Fleet Console",
      title: "Sample Case: APAC Sovereign Banking Job",
      subtitle: "How to route sensitive workloads under data residency laws",
      badge: "Console & Workload Dispatcher",
      badgeColor: "var(--primary)",
      route: "/console",
      content: (
        <div>
          <div style={{ background: 'var(--bg-subtle)', padding: '1.25rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', marginBottom: '1.25rem' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--primary)', textTransform: 'uppercase', marginBottom: '0.3rem' }}>
              The Scenario:
            </div>
            <p style={{ fontSize: '0.95rem', color: 'var(--text-main)', lineHeight: 1.6 }}>
              A Mumbai financial institution needs to run an overnight risk batch. Under <strong>India DPDP laws</strong>, data cannot leave Asia-Pacific.
            </p>
          </div>

          <div style={{ marginBottom: '1.25rem' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-faint)', marginBottom: '0.5rem' }}>
              How the Controls Work:
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', fontSize: '0.9rem' }}>
              <div style={{ background: 'var(--surface-card)', padding: '0.85rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                <strong>1. Filter by Region</strong>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: '0.2rem' }}>Click <span className="mono" style={{ color: 'var(--primary)' }}>[APAC]</span> to constrain candidate fleet to Mumbai, Tokyo, Singapore, Sydney.</p>
              </div>
              <div style={{ background: 'var(--surface-card)', padding: '0.85rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                <strong>2. Click Dispatch</strong>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: '0.2rem' }}>Click <span className="mono" style={{ color: 'var(--clean)' }}>[Dispatch APAC Workload]</span> to trigger execution via AWS SSM.</p>
              </div>
            </div>
          </div>

          <div style={{ background: 'var(--clean-bg)', border: '1px solid var(--clean-border)', padding: '1rem', borderRadius: 'var(--radius-sm)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span style={{ fontSize: '0.8rem', color: 'var(--clean)', fontWeight: 700 }}>SAMPLE OUTCOME:</span>
                <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-main)', marginTop: '0.1rem' }}>
                  Mumbai (644 gCO2) &rarr; Tokyo T+5h (446 gCO2)
                </div>
              </div>
              <span className="badge-clean" style={{ fontSize: '0.9rem' }}>+30.69% Carbon Cut</span>
            </div>
          </div>
        </div>
      )
    },
    {
      part: "Part 2: Forecasting Engine",
      title: "Sample Case: 3-Stage SLA Deadline Tuning",
      subtitle: "How deadline flexibility unlocks deeper carbon savings",
      badge: "Temporal Multi-Horizon",
      badgeColor: "var(--clean)",
      route: "/forecasting",
      content: (
        <div>
          <div style={{ background: 'var(--bg-subtle)', padding: '1.25rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', marginBottom: '1.25rem' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--clean)', textTransform: 'uppercase', marginBottom: '0.3rem' }}>
              The Scenario:
            </div>
            <p style={{ fontSize: '0.95rem', color: 'var(--text-main)', lineHeight: 1.6 }}>
              An AI training workload has flexible completion deadlines. We want to test how much carbon is saved with <strong>3-hour</strong>, <strong>6-hour</strong>, vs <strong>12-hour</strong> delays.
            </p>
          </div>

          <div style={{ marginBottom: '1.25rem' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-faint)', marginBottom: '0.5rem' }}>
              Interactive Controls:
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
              <span className="btn btn-outline" style={{ fontSize: '0.8rem', padding: '0.4rem 0.75rem' }}>[Stage 1: 3h (+6.5%)]</span>
              <span className="btn btn-outline" style={{ fontSize: '0.8rem', padding: '0.4rem 0.75rem' }}>[Stage 2: 6h (+9.5%)]</span>
              <span className="btn btn-primary" style={{ fontSize: '0.8rem', padding: '0.4rem 0.75rem' }}>[Stage 3: 12h (+30.7%)]</span>
            </div>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Selecting any stage compares the <strong>Neural LSTM</strong> trajectory directly against <strong>ARIMA(2,1,2)</strong> and verifies the 2.5% No-Regret threshold.
            </p>
          </div>

          <div style={{ background: 'var(--surface-card)', padding: '0.85rem 1rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
              <span style={{ color: 'var(--text-faint)' }}>Decision Breakdown:</span>
              <span className="mono" style={{ color: 'var(--clean)', fontWeight: 700 }}>Optimal: T+5h (Tokyo Hydro/Solar Window)</span>
            </div>
          </div>
        </div>
      )
    },
    {
      part: "Part 3: Playground Sandbox",
      title: "Sample Case: 24h Solar Path & Migration Arc",
      subtitle: "Watching workloads follow the sun from East to West",
      badge: "World Map & Solar Trail",
      badgeColor: "var(--moderate)",
      route: "/playground",
      content: (
        <div>
          <div style={{ background: 'var(--bg-subtle)', padding: '1.25rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', marginBottom: '1.25rem' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--moderate)', textTransform: 'uppercase', marginBottom: '0.3rem' }}>
              The Scenario:
            </div>
            <p style={{ fontSize: '0.95rem', color: 'var(--text-main)', lineHeight: 1.6 }}>
              A continuous batch job follows Earth's rotation across daylight hours to stay powered by peak solar and hydro energy.
            </p>
          </div>

          <div style={{ marginBottom: '1.25rem' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-faint)', marginBottom: '0.5rem' }}>
              Controls & Visual Elements:
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', fontSize: '0.9rem' }}>
              <div style={{ background: 'var(--surface-card)', padding: '0.85rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                <strong>1. 24h Flight Arc</strong>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: '0.2rem' }}>Draws dashed curved migration lines from Virginia &rarr; Canada &rarr; Sweden.</p>
              </div>
              <div style={{ background: 'var(--surface-card)', padding: '0.85rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                <strong>2. Hourly Scrubber</strong>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: '0.2rem' }}>Click any hour (00h to 23h) or press [Run 24h Sim] to see dynamic handoffs.</p>
              </div>
            </div>
          </div>

          <div style={{ background: 'var(--clean-bg)', border: '1px solid var(--clean-border)', padding: '1rem', borderRadius: 'var(--radius-sm)' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--clean)', fontWeight: 700 }}>VERIFIED RESULT:</span>
            <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-main)', marginTop: '0.1rem' }}>
              Virginia (437 g) &rarr; Canada (41 g) &rarr; <span style={{ color: 'var(--clean)' }}>+90.52% Avoided Carbon</span>
            </div>
          </div>
        </div>
      )
    },
    {
      part: "Part 4: Pilot Telemetry",
      title: "Sample Case: Live 3-Account AWS Execution",
      subtitle: "Monitoring real-time EC2 instances & zero-port SSM executions",
      badge: "Live AWS Infrastructure",
      badgeColor: "#f43f5e",
      route: "/pilot",
      content: (
        <div>
          <div style={{ background: 'var(--bg-subtle)', padding: '1.25rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', marginBottom: '1.25rem' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f43f5e', textTransform: 'uppercase', marginBottom: '0.3rem' }}>
              The Scenario:
            </div>
            <p style={{ fontSize: '0.95rem', color: 'var(--text-main)', lineHeight: 1.6 }}>
              3 independent AWS accounts run 24/7 across 12 global regions measuring empirical execution via AWS Systems Manager without open SSH ports.
            </p>
          </div>

          <div style={{ marginBottom: '1.25rem' }}>
            <div style={{ fontSize: '0.85rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-faint)', marginBottom: '0.5rem' }}>
              What to Monitor:
            </div>
            <ul style={{ paddingLeft: '1.25rem', fontSize: '0.9rem', color: 'var(--text-muted)', lineHeight: 1.8 }}>
              <li><strong>Live Cycle Feed</strong>: Real-time table parsed from atomic <span className="mono">pilot_*.jsonl</span> logs.</li>
              <li><strong>SSM Status</strong>: Confirms real compute workloads completed with zero errors on remote instances.</li>
              <li><strong>Account Tabs</strong>: Toggle between Adaptive, LSTM, and ARIMA streams.</li>
            </ul>
          </div>

          <div style={{ background: 'var(--surface-card)', padding: '0.85rem 1rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-faint)', fontWeight: 700 }}>INFRASTRUCTURE STATUS:</span>
            <div className="mono" style={{ fontSize: '0.95rem', color: 'var(--clean)', fontWeight: 600, marginTop: '0.1rem' }}>
              12 Instances Active &middot; 2/2 Health Checks Passed &middot; Cloud Orchestrator Live
            </div>
          </div>
        </div>
      )
    }
  ];

  const currentCase = sampleCases[currentStep];

  const handleOpenPage = (route) => {
    onClose();
    navigate(route);
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      width: '100%',
      height: '100%',
      background: 'rgba(5, 8, 15, 0.88)',
      backdropFilter: 'blur(10px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 100,
      padding: '1.5rem'
    }}>
      <div className="card" style={{
        maxWidth: '740px',
        width: '100%',
        background: 'var(--surface)',
        border: '1px solid var(--border-light)',
        padding: '2.5rem 3rem',
        borderRadius: 'var(--radius-lg)',
        boxShadow: '0 25px 60px rgba(0,0,0,0.6)',
        position: 'relative'
      }}>
        {/* Close Button */}
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: '1.5rem',
            right: '1.5rem',
            background: 'transparent',
            border: 'none',
            color: 'var(--text-faint)',
            cursor: 'pointer'
          }}
        >
          <X size={24} />
        </button>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <span className="jurisdiction-badge" style={{ color: currentCase.badgeColor, borderColor: currentCase.badgeColor }}>
              {currentCase.part}
            </span>
            <h2 style={{ fontSize: '1.6rem', fontWeight: 800, color: 'var(--text-main)', marginTop: '0.35rem' }}>
              {currentCase.title}
            </h2>
            <div style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>{currentCase.subtitle}</div>
          </div>

          {/* Quick Jump to Live Page Button */}
          <button
            className="btn btn-primary"
            style={{ fontSize: '0.85rem', padding: '0.5rem 0.95rem' }}
            onClick={() => handleOpenPage(currentCase.route)}
          >
            Open Live {currentCase.part.split(':')[1]} <ExternalLink size={14} />
          </button>
        </div>

        {/* Body Content */}
        <div style={{ minHeight: '260px', marginBottom: '2rem' }}>
          {currentCase.content}
        </div>

        {/* Footer Navigation Controls */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '1.5rem', borderTop: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            {sampleCases.map((_, i) => (
              <div
                key={i}
                onClick={() => setCurrentStep(i)}
                style={{
                  width: i === currentStep ? '28px' : '10px',
                  height: '10px',
                  borderRadius: '5px',
                  background: i === currentStep ? 'var(--primary)' : 'var(--border-light)',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease'
                }}
              />
            ))}
          </div>

          <div style={{ display: 'flex', gap: '0.75rem' }}>
            {currentStep > 0 && (
              <button
                className="btn btn-outline"
                style={{ padding: '0.65rem 1.25rem' }}
                onClick={() => setCurrentStep(prev => prev - 1)}
              >
                <ArrowLeft size={16} /> Previous Case
              </button>
            )}
            
            {currentStep < sampleCases.length - 1 ? (
              <button
                className="btn btn-primary"
                style={{ padding: '0.65rem 1.25rem' }}
                onClick={() => setCurrentStep(prev => prev + 1)}
              >
                Next Case Study <ArrowRight size={16} />
              </button>
            ) : (
              <button
                className="btn btn-primary"
                style={{ background: 'var(--clean)', padding: '0.65rem 1.25rem' }}
                onClick={onClose}
              >
                <CheckCircle2 size={16} /> Complete Tutorial
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
