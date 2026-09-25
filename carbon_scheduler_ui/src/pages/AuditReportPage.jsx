import React, { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Printer, ArrowLeft } from 'lucide-react';
import TopNavbar from '../components/layout/TopNavbar';

const VERDICT_LABEL = {
  non_compliant: 'Fix compliance first',
  never_move: 'Never move',
  blocked_by_cost: 'Blocked by cost',
  shift_time: 'Shift in time',
  stay: 'Stay',
  move: 'Move region',
};

function loadReport() {
  try {
    const raw = localStorage.getItem('cadss_audit_report_v1');
    if (raw) return JSON.parse(raw);
  } catch (e) { /* ignore */ }
  return null;
}

export default function AuditReportPage() {
  const report = useMemo(loadReport, []);

  if (!report) {
    return (
      <div className="app-layout">
        <TopNavbar />
        <main className="main-content">
          <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
            <p style={{ color: 'var(--text-muted)', marginBottom: '1rem' }}>
              No audit has been run yet in this browser.
            </p>
            <Link to="/" className="btn btn-primary">Run a Placement Audit</Link>
          </div>
        </main>
      </div>
    );
  }

  const { companyName, maxInrPerTonne, result, generatedAt } = report;
  const decisions = [...result.decisions].sort((a, b) => a.workload.name.localeCompare(b.workload.name));
  const date = new Date(generatedAt).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });

  return (
    <div className="app-layout">
      <style>{`
        @media print {
          .navbar, .no-print { display: none !important; }
          .main-content { max-width: none; padding: 0; }
          body { background: #fff; }
          .card { break-inside: avoid; box-shadow: none !important; }
        }
      `}</style>
      <div className="no-print"><TopNavbar /></div>

      <main className="main-content" style={{ maxWidth: '900px' }}>
        <div className="no-print" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
          <Link to="/" className="btn btn-outline"><ArrowLeft size={14} /> Back to Audit</Link>
          <button className="btn btn-primary" onClick={() => window.print()}>
            <Printer size={14} /> Print / Save as PDF
          </button>
        </div>

        <div style={{ borderBottom: '2px solid var(--border)', paddingBottom: '1.5rem', marginBottom: '1.5rem' }}>
          <div className="simulated-chip" style={{ marginBottom: '1rem' }}>Simulated estimates — not billing-grade</div>
          <h1 className="page-title" style={{ marginBottom: '0.4rem' }}>Workload Placement Audit</h1>
          <p style={{ fontSize: '1.05rem', color: 'var(--text-main)' }}>{companyName}</p>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Generated {date}
            {result.hour != null && <> · grid data as of {String(result.hour).padStart(2, '0')}:00 UTC</>}
            {' · '}Cost policy ceiling ₹{maxInrPerTonne.toLocaleString('en-IN')}/tonne CO₂
          </p>
        </div>

        <div className="kpi-ribbon">
          <div className="kpi-card">
            <div className="kpi-label">Estimated CO₂ avoided / yr</div>
            <div className="kpi-val mono" style={{ color: 'var(--clean)' }}>{result.summary.tonnesCo2PerYear.toFixed(2)} t</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">{result.summary.inrDeltaPerYear <= 0 ? 'Money saved / yr' : 'Extra cost / yr'}</div>
            <div className="kpi-val mono">
              {result.summary.inrDeltaPerYear <= 0 ? '−' : '+'}₹{Math.abs(result.summary.inrDeltaPerYear).toLocaleString('en-IN')}
            </div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Workloads audited</div>
            <div className="kpi-val mono">{decisions.length}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Recommended to move</div>
            <div className="kpi-val mono">{(result.summary.counts.move || 0) + (result.summary.counts.shift_time || 0)}</div>
          </div>
        </div>

        <div className="card">
          <div className="card-header"><h2 className="card-title">Per-workload decisions</h2></div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Workload</th>
                  <th>Verdict</th>
                  <th>Current region</th>
                  <th>Recommendation</th>
                  <th>Reason</th>
                  <th>t CO₂/yr</th>
                </tr>
              </thead>
              <tbody>
                {decisions.map((d, i) => (
                  <tr key={i}>
                    <td>{d.workload.name}</td>
                    <td>{VERDICT_LABEL[d.verdict]}</td>
                    <td className="mono" style={{ fontSize: '0.85rem' }}>{d.currentRegion}</td>
                    <td className="mono" style={{ fontSize: '0.85rem' }}>{d.recommendedRegion}{d.shiftHours ? ` (+${d.shiftHours}h)` : ''}</td>
                    <td style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                      {d.reason}
                      {d.suggestion && <div style={{ marginTop: '0.3rem', color: 'var(--text-main)' }}>{d.suggestion}</div>}
                    </td>
                    <td className="mono">{d.tonnesCo2PerYear != null ? d.tonnesCo2PerYear.toFixed(2) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <div className="card-header"><h2 className="card-title">Methodology &amp; limitations</h2></div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: 1.7 }}>
            <p style={{ marginBottom: '0.75rem' }}>
              <strong style={{ color: 'var(--text-main)' }}>Carbon model:</strong> a simulated diurnal carbon-intensity curve
              per region, calibrated to each grid's typical cleanliness and daily pattern — not a live feed. Carbon savings are
              computed from <em>average</em> grid carbon intensity, not marginal emissions actually displaced; the two can diverge,
              particularly on grids where the marginal generator differs from the average mix.
            </p>
            <p style={{ marginBottom: '0.75rem' }}>
              <strong style={{ color: 'var(--text-main)' }}>Cost model:</strong> illustrative compute and egress prices, not a
              billing quote. A recommendation is only made when the cost per tonne of CO₂ avoided falls under your policy
              ceiling (₹{maxInrPerTonne.toLocaleString('en-IN')}/tonne here).
            </p>
            <p style={{ marginBottom: '0.75rem' }}>
              <strong style={{ color: 'var(--text-main)' }}>Why placement, not live scheduling:</strong> across a 5-year
              historical replay, static region selection captured roughly 97% of the carbon savings a real-time adaptive
              scheduler could achieve — real-time adaptivity added only +2.7% held-out. The placement decision, made once,
              is where nearly all of the value is; this audit reflects that finding directly.
            </p>
            <p style={{ marginBottom: '0.75rem' }}>
              <strong style={{ color: 'var(--text-main)' }}>Shift-in-time recommendations:</strong> gated by a no-regret guard
              — a delay is only recommended when a forecaster's verified accuracy earns the trust to act on it. The
              simulated forecaster here reflects the calibration observed in this project's live pilot.
            </p>
            <p>
              <strong style={{ color: 'var(--text-main)' }}>Intended use:</strong> a starting point for engineering review and
              sustainability disclosure preparation (e.g. BRSR), not an auditor-certified emissions statement.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
