import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Leaf, Lock, Clock, CheckCircle2, AlertTriangle, ArrowRight, Trash2, Plus, FileText, Building2, Save, ShieldAlert } from 'lucide-react';
import TopNavbar from '../components/layout/TopNavbar';
import { PRESETS, findPreset } from '../sim/presets';
import { REGION_NAMES } from '../sim/regions';
import { allowedRegionsFor } from '../sim/jurisdictions';
import { runAudit } from '../sim/audit';
import { currentHour } from '../sim/carbonModel';
import '../styles/console.css';

const STORAGE_KEY = 'cadss_audit_state_v1';

const KIND_OPTIONS = [
  { value: 'customer-facing', label: 'Customer-facing' },
  { value: 'batch', label: 'Batch' },
  { value: 'deferrable', label: 'Deferrable batch' },
];
const DATA_CLASS_OPTIONS = [
  { value: 'personal_india', label: 'Personal data (India / DPDP)' },
  { value: 'personal_eu', label: 'Personal data (EU / GDPR)' },
  { value: 'anonymised', label: 'Anonymised' },
  { value: 'public', label: 'Public / non-sensitive' },
];
const JURISDICTION_OPTIONS = [
  { value: 'apac_sovereign', label: 'APAC only' },
  { value: 'americas_sovereign', label: 'Americas only' },
  { value: 'global_unconstrained', label: 'Global (any region)' },
];

const VERDICT_META = {
  non_compliant: { label: 'Fix compliance first', icon: ShieldAlert, color: 'var(--dirty)', order: -1 },
  never_move: { label: 'Never move', icon: Lock, color: 'var(--text-muted)', order: 0 },
  blocked_by_cost: { label: 'Blocked by cost', icon: AlertTriangle, color: 'var(--moderate)', order: 1 },
  shift_time: { label: 'Shift in time', icon: Clock, color: 'var(--primary)', order: 2 },
  stay: { label: 'Stay (already optimal)', icon: CheckCircle2, color: 'var(--text-muted)', order: 3 },
  move: { label: 'Move region', icon: ArrowRight, color: 'var(--clean)', order: 4 },
};

function loadSaved() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch (e) { /* ignore */ }
  return null;
}

const CUSTOM_KEY = 'cadss_custom_companies_v1';

// Companies the user builds themselves, kept in this browser alongside the
// three fictional presets.
function loadCustomCompanies() {
  try {
    const parsed = JSON.parse(localStorage.getItem(CUSTOM_KEY) || 'null');
    if (Array.isArray(parsed)) return parsed;
  } catch (e) { /* ignore */ }
  return [];
}

function blankWorkload() {
  return {
    name: 'New workload',
    description: '',
    kind: 'batch',
    dataClass: 'anonymised',
    jurisdiction: 'global_unconstrained',
    latencySlaMs: 300,
    currentRegion: 'ap-south-1 (Mumbai)',
    vcpus: 8,
    hoursPerMonth: 200,
    dataOutGbPerMonth: 20,
    deadlineFlexHours: 6,
  };
}

export default function AuditPage() {
  const navigate = useNavigate();
  const saved = useMemo(loadSaved, []);
  const [presetId, setPresetId] = useState(saved?.presetId || 'quickbite');
  const [companyName, setCompanyName] = useState(saved?.companyName || findPreset(saved?.presetId || 'quickbite').name);
  const [maxInrPerTonne, setMaxInrPerTonne] = useState(saved?.maxInrPerTonne ?? findPreset(saved?.presetId || 'quickbite').maxInrPerTonne);
  const [workloads, setWorkloads] = useState(saved?.workloads || findPreset('quickbite').workloads);
  const [result, setResult] = useState(null);
  const [customCompanies, setCustomCompanies] = useState(loadCustomCompanies);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ presetId, companyName, maxInrPerTonne, workloads }));
    } catch (e) { /* ignore */ }
  }, [presetId, companyName, maxInrPerTonne, workloads]);

  useEffect(() => {
    try {
      localStorage.setItem(CUSTOM_KEY, JSON.stringify(customCompanies));
    } catch (e) { /* ignore */ }
  }, [customCompanies]);

  const isCustomId = (id) => typeof id === 'string' && id.startsWith('custom:');
  const isSavedCustom = isCustomId(presetId) && presetId !== 'custom:new';
  const findCompany = (id) => (isCustomId(id) ? customCompanies.find((c) => c.id === id) || null : findPreset(id));

  const loadPreset = (id) => {
    const p = findCompany(id);
    if (!p) return;
    setPresetId(id);
    setCompanyName(p.name);
    setMaxInrPerTonne(p.maxInrPerTonne);
    setWorkloads(p.workloads.map((w) => ({ ...w })));
    setResult(null);
  };

  const newCompany = () => {
    setPresetId('custom:new');
    setCompanyName('My company');
    setMaxInrPerTonne(12000);
    setWorkloads([blankWorkload()]);
    setResult(null);
  };

  const saveCompany = () => {
    const id = isSavedCustom ? presetId : 'custom:' + Date.now();
    const entry = {
      id,
      name: companyName.trim() || 'My company',
      tagline: 'Your own company — saved in this browser',
      maxInrPerTonne,
      workloads: workloads.map((w) => ({ ...w })),
      custom: true,
    };
    setCustomCompanies((prev) => (isSavedCustom ? prev.map((c) => (c.id === id ? entry : c)) : [...prev, entry]));
    setPresetId(id);
  };

  const deleteCompany = (id) => {
    setCustomCompanies((prev) => prev.filter((c) => c.id !== id));
    if (presetId === id) loadPreset('quickbite');
  };

  // Regions this workload's data class / jurisdiction actually permit. A
  // workload can never legally be running outside them, so "Region today"
  // offers only these, and changing the rules moves an illegal region back
  // inside them.
  const allowedFor = (w) => allowedRegionsFor(w.dataClass, w.jurisdiction, REGION_NAMES) || REGION_NAMES;

  const updateWorkload = (idx, patch) => {
    setWorkloads((prev) => prev.map((w, i) => {
      if (i !== idx) return w;
      const next = { ...w, ...patch };
      if (patch.dataClass !== undefined || patch.jurisdiction !== undefined) {
        const allowed = allowedFor(next);
        if (!allowed.includes(next.currentRegion)) next.currentRegion = allowed[0];
      }
      return next;
    }));
  };
  const removeWorkload = (idx) => setWorkloads((prev) => prev.filter((_, i) => i !== idx));
  const addWorkload = () => setWorkloads((prev) => [...prev, blankWorkload()]);

  const runNow = () => {
    const hour = currentHour();
    const auditResult = runAudit(
      workloads.map((w) => ({ ...w, maxInrPerTonne })),
      { hour, dayIndex: 0 }
    );
    setResult({ ...auditResult, hour });
  };

  const goToReport = () => {
    if (!result) return;
    try {
      localStorage.setItem(
        'cadss_audit_report_v1',
        JSON.stringify({ companyName, maxInrPerTonne, workloads, result, generatedAt: new Date().toISOString() })
      );
    } catch (e) { /* ignore */ }
    navigate('/report');
  };

  const activePreset = findCompany(presetId) || { name: companyName, workloads };
  const groupedDecisions = result
    ? [...result.decisions].sort((a, b) => VERDICT_META[a.verdict].order - VERDICT_META[b.verdict].order)
    : [];

  return (
    <div className="app-layout">
      <TopNavbar />
      <main className="main-content">
        <div className="page-header">
          <h1 className="page-title">Workload Placement Audit</h1>
          <p className="page-subtitle">
            List what you run, where, and under what constraints — get back which workloads should move, which
            should shift to a cleaner hour, and which must stay exactly where they are, with the reason for each.
          </p>
        </div>

        <div className="card" id="tour-audit-presets">
          <div className="card-header">
            <div>
              <h2 className="card-title">Start from a preset, or your own company</h2>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
                The first three are fictional examples — illustrative, not real customers. Build your own with
                New company, then save it to come back to later.
              </p>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
            {[...PRESETS, ...customCompanies].map((p) => (
              <div key={p.id} style={{ position: 'relative', display: 'flex' }}>
                <button
                  onClick={() => loadPreset(p.id)}
                  className="btn"
                  style={{
                    flex: 1,
                    flexDirection: 'column',
                    alignItems: 'flex-start',
                    textAlign: 'left',
                    padding: '1rem 1.25rem',
                    paddingRight: p.custom ? '2.75rem' : '1.25rem',
                    height: 'auto',
                    gap: '0.4rem',
                    background: presetId === p.id ? 'var(--primary-subtle)' : 'var(--surface)',
                    border: `1px solid ${presetId === p.id ? 'var(--primary)' : 'var(--border)'}`,
                    color: 'var(--text-main)',
                  }}
                >
                  <strong style={{ fontSize: '1rem' }}>{p.name}</strong>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>{p.tagline}</span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-faint)' }}>{p.workloads.length} workloads</span>
                </button>
                {p.custom && (
                  <button
                    className="icon-btn icon-btn-danger"
                    style={{ position: 'absolute', top: '0.6rem', right: '0.6rem' }}
                    onClick={() => deleteCompany(p.id)}
                    title={'Delete ' + p.name}
                    aria-label={'Delete ' + p.name}
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
            ))}

            <button
              onClick={newCompany}
              className="btn"
              style={{
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '1rem 1.25rem',
                height: 'auto',
                gap: '0.35rem',
                background: presetId === 'custom:new' ? 'var(--primary-subtle)' : 'transparent',
                border: `1px dashed ${presetId === 'custom:new' ? 'var(--primary)' : 'var(--border)'}`,
                color: 'var(--text-main)',
              }}
            >
              <Plus size={18} />
              <strong style={{ fontSize: '0.95rem' }}>New company</strong>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'center' }}>Start from one blank workload</span>
            </button>
          </div>
        </div>

        {activePreset.enterprise && (
          <div className="card" style={{ background: 'var(--surface-card)' }}>
            <div className="card-header">
              <div>
                <h3 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Building2 size={18} /> Enterprise integration preview
                </h3>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
                  At this scale, placement policy is enforced centrally — in CI, not per-engineer choice. This is a
                  preview of that policy, not a live integration.
                </p>
              </div>
            </div>
            <pre
              className="mono"
              style={{
                background: 'var(--bg-subtle)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                padding: '1rem',
                fontSize: '0.8rem',
                overflowX: 'auto',
                color: 'var(--text-main)',
              }}
            >
              {activePreset.policySnippet}
            </pre>
          </div>
        )}

        <div className="card" id="tour-audit-workloads">
          <div className="card-header">
            <div>
              <h2 className="card-title">Workloads</h2>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
                Edit in place, or add your own. Nothing here leaves your browser.
              </p>
            </div>
            <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Company:
                <input
                  className="fleet-input"
                  style={{ marginLeft: '0.5rem', minWidth: '160px' }}
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                />
              </label>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Max ₹/tonne:
                <input
                  type="number"
                  className="fleet-input"
                  style={{ marginLeft: '0.5rem', width: '110px', minWidth: 0 }}
                  value={maxInrPerTonne}
                  onChange={(e) => setMaxInrPerTonne(Number(e.target.value) || 0)}
                />
              </label>
              <button className="btn btn-outline" style={{ fontSize: '0.8rem' }} onClick={saveCompany}>
                <Save size={14} /> {isSavedCustom ? 'Update saved company' : 'Save as company'}
              </button>
            </div>
          </div>

          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Workload</th>
                  <th>Kind</th>
                  <th>Data class</th>
                  <th>Jurisdiction</th>
                  <th>SLA (ms)</th>
                  <th>Region today</th>
                  <th>vCPUs</th>
                  <th>Hrs/mo</th>
                  <th>Egress GB/mo</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {workloads.map((w, i) => (
                  <tr key={i}>
                    <td>
                      <input
                        className="fleet-input"
                        style={{ minWidth: '140px' }}
                        value={w.name}
                        onChange={(e) => updateWorkload(i, { name: e.target.value })}
                      />
                    </td>
                    <td>
                      <select className="fleet-select" style={{ minWidth: 0 }} value={w.kind} onChange={(e) => updateWorkload(i, { kind: e.target.value })}>
                        {KIND_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>
                    </td>
                    <td>
                      <select className="fleet-select" style={{ minWidth: 0 }} value={w.dataClass} onChange={(e) => updateWorkload(i, { dataClass: e.target.value })}>
                        {DATA_CLASS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>
                    </td>
                    <td>
                      {(w.dataClass === 'anonymised' || w.dataClass === 'public') ? (
                        <select className="fleet-select" style={{ minWidth: 0 }} value={w.jurisdiction} onChange={(e) => updateWorkload(i, { jurisdiction: e.target.value })}>
                          {JURISDICTION_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                        </select>
                      ) : (
                        <span style={{ color: 'var(--text-faint)', fontSize: '0.8rem' }}>set by data class</span>
                      )}
                    </td>
                    <td>
                      <input type="number" className="fleet-input" style={{ width: '70px', minWidth: 0 }} value={w.latencySlaMs} onChange={(e) => updateWorkload(i, { latencySlaMs: Number(e.target.value) || 0 })} />
                    </td>
                    <td>
                      <select className="fleet-select" style={{ minWidth: 0 }} value={w.currentRegion} onChange={(e) => updateWorkload(i, { currentRegion: e.target.value })}>
                        {allowedFor(w).map((r) => <option key={r} value={r}>{r}</option>)}
                      </select>
                    </td>
                    <td><input type="number" className="fleet-input" style={{ width: '60px', minWidth: 0 }} value={w.vcpus} onChange={(e) => updateWorkload(i, { vcpus: Number(e.target.value) || 0 })} /></td>
                    <td><input type="number" className="fleet-input" style={{ width: '60px', minWidth: 0 }} value={w.hoursPerMonth} onChange={(e) => updateWorkload(i, { hoursPerMonth: Number(e.target.value) || 0 })} /></td>
                    <td><input type="number" className="fleet-input" style={{ width: '70px', minWidth: 0 }} value={w.dataOutGbPerMonth} onChange={(e) => updateWorkload(i, { dataOutGbPerMonth: Number(e.target.value) || 0 })} /></td>
                    <td>
                      <button className="icon-btn icon-btn-danger" onClick={() => removeWorkload(i)} title="Remove workload">
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Tour anchor sits on the Run row until results exist, then moves to the summary. */}
          <div
            id={result ? undefined : 'tour-audit-summary'}
            style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem' }}
          >
            <button className="btn btn-outline" onClick={addWorkload}>
              <Plus size={14} /> Add workload
            </button>
            <button className="btn btn-primary" style={{ padding: '0.75rem 1.5rem' }} onClick={runNow}>
              <Leaf size={16} /> Run audit
            </button>
          </div>
        </div>

        {result && (
          <>
            <div className="kpi-ribbon" id="tour-audit-summary">
              <div className="kpi-card">
                <div className="kpi-label">Estimated CO₂ avoided / yr</div>
                <div className="kpi-val mono" style={{ color: 'var(--clean)' }}>{result.summary.tonnesCo2PerYear.toFixed(2)} t</div>
                <div className="kpi-meta">
                  Simulated estimate{result.hour != null && <> · scored at {String(result.hour).padStart(2, '0')}:00 UTC</>}
                </div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">{result.summary.inrDeltaPerYear <= 0 ? 'Money saved / yr' : 'Extra cost / yr'}</div>
                <div className="kpi-val mono" style={{ color: result.summary.inrDeltaPerYear <= 0 ? 'var(--clean)' : 'var(--moderate)' }}>
                  {result.summary.inrDeltaPerYear <= 0 ? '−' : '+'}₹{Math.abs(result.summary.inrDeltaPerYear).toLocaleString('en-IN')}
                </div>
                <div className="kpi-meta">
                  {result.summary.inrDeltaPerYear <= 0
                    ? 'Cheaper than running where you do today'
                    : 'On top of what you spend today'} · compute + egress, simulated pricing
                </div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">Move / Shift / Stay / Blocked</div>
                <div className="kpi-val mono">
                  {result.summary.counts.move || 0} / {result.summary.counts.shift_time || 0} / {result.summary.counts.stay || 0} / {result.summary.counts.blocked_by_cost || 0}
                </div>
                <div className="kpi-meta">Blocked = cheaper to stay than the carbon is worth</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">Never move{result.summary.counts.non_compliant ? ' / non-compliant' : ''}</div>
                <div className="kpi-val mono">
                  {result.summary.counts.never_move || 0}{result.summary.counts.non_compliant ? ` / ${result.summary.counts.non_compliant}` : ''}
                </div>
                <div className="kpi-meta">
                  {result.summary.counts.non_compliant
                    ? 'Some workloads are already outside their own rules'
                    : `Compliance or latency — by design · all ${workloads.length} workloads accounted for`}
                </div>
              </div>
            </div>

            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Per-workload decisions</h2>
                <button className="btn btn-outline" onClick={goToReport}>
                  <FileText size={14} /> View printable report
                </button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {groupedDecisions.map((d, i) => {
                  const meta = VERDICT_META[d.verdict];
                  const Icon = meta.icon;
                  return (
                    <details key={i} className="card" style={{ margin: 0, padding: '1rem 1.25rem' }}>
                      <summary style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', cursor: 'pointer', listStyle: 'none' }}>
                        <Icon size={18} color={meta.color} style={{ flexShrink: 0 }} />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                            <strong style={{ fontSize: '0.95rem' }}>{d.workload.name}</strong>
                            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: meta.color, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                              {meta.label}
                            </span>
                          </div>
                          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>{d.reason}</p>
                        </div>
                        {d.verdict === 'move' && (
                          <span className="mono" style={{ color: 'var(--clean)', fontSize: '0.85rem', fontWeight: 700 }}>
                            −{d.tonnesCo2PerYear.toFixed(2)} t/yr
                          </span>
                        )}
                      </summary>
                      <div style={{ marginTop: '0.85rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border)', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                        <div>Current region: <span className="mono">{d.currentRegion}</span></div>
                        <div>Recommended region: <span className="mono">{d.recommendedRegion}</span>{d.shiftHours ? <> (wait {d.shiftHours}h)</> : null}</div>
                        <div>Allowed regions considered: <span className="mono">{d.allowedRegions.join(', ')}</span></div>
                        {d.verdict === 'move' && (
                          <div>
                            {d.inrDeltaPerYear <= 0 ? 'Cost: saves ' : 'Cost: extra '}
                            <span className="mono">₹{Math.abs(Math.round(d.inrDeltaPerYear)).toLocaleString('en-IN')}/yr</span>
                            {' vs today'}
                          </div>
                        )}
                        {d.verdict === 'blocked_by_cost' && (
                          <div>Would save <span className="mono">{d.wouldSaveTonnes} t/yr</span> at <span className="mono">₹{Math.round(d.wouldCostInr).toLocaleString('en-IN')}/yr</span> extra cost — <span className="mono">₹{Math.round(d.details?.inrPerTonne || 0).toLocaleString('en-IN')}/tonne</span></div>
                        )}
                        {d.details?.currentCi != null && (
                          <div>
                            Grid intensity now: <span className="mono">{Math.round(d.details.currentCi)} g</span>
                            {d.details.bestCi != null && <> → <span className="mono">{Math.round(d.details.bestCi)} g</span> at {d.details.bestRegion || d.recommendedRegion}</>}
                            {d.details.predictedCi != null && <> → <span className="mono">{Math.round(d.details.predictedCi)} g</span> in {d.shiftHours}h ({Math.round(d.details.savingsPct)}% cleaner)</>}
                          </div>
                        )}
                        {d.details?.energyKwhPerYear != null && (
                          <div>Energy: <span className="mono">{Math.round(d.details.energyKwhPerYear).toLocaleString('en-IN')} kWh/yr</span> ({d.workload.vcpus} vCPU × {d.workload.hoursPerMonth} h/mo)</div>
                        )}
                        {d.details?.ranked?.length > 1 && (
                          <div style={{ marginTop: '0.35rem' }}>
                            Allowed regions ranked now:{' '}
                            {d.details.ranked.map((r, n) => (
                              <span key={r.name} className="mono" style={{ color: n === 0 ? 'var(--clean)' : 'var(--text-muted)' }}>
                                {n > 0 ? ' · ' : ''}{r.name.split(' ')[0]} {Math.round(r.ci)}g/{Math.round(r.latency)}ms
                              </span>
                            ))}
                          </div>
                        )}
                        {d.suggestion && (
                          <div style={{ marginTop: '0.5rem', padding: '0.6rem 0.75rem', background: 'var(--bg-subtle)', borderRadius: 'var(--radius-sm)', color: 'var(--text-main)' }}>
                            <strong style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-faint)' }}>What to do</strong>
                            <div style={{ marginTop: '0.2rem' }}>{d.suggestion}</div>
                          </div>
                        )}
                      </div>
                    </details>
                  );
                })}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
