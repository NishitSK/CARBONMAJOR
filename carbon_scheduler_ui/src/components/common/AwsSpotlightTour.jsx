import React, { useEffect } from 'react';
import { useTour } from '../../context/TourContext';
import { X, ArrowRight, ArrowLeft, CheckCircle2, Play, Compass, ExternalLink } from 'lucide-react';

export default function AwsSpotlightTour() {
  const { isTourActive, currentStep, currentStepIndex, totalSteps, nextStep, prevStep, endTour } = useTour();

  useEffect(() => {
    if (!isTourActive || !currentStep?.targetId) return;

    let el = null;
    let tries = 0;
    const highlight = () => {
      el = document.getElementById(currentStep.targetId);
      if (!el) return false;
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.classList.add('tour-highlight');
      return true;
    };

    // Retry briefly: on a cross-page step the target isn't mounted yet when
    // this effect first runs, so poll until it appears (up to ~1.6s).
    let interval = null;
    if (!highlight()) {
      interval = setInterval(() => {
        tries += 1;
        if (highlight() || tries > 20) clearInterval(interval);
      }, 80);
    }

    return () => {
      if (interval) clearInterval(interval);
      if (el) el.classList.remove('tour-highlight');
    };
  }, [isTourActive, currentStep]);

  if (!isTourActive || !currentStep) return null;

  return (
    <div style={{
      position: 'fixed',
      bottom: '2.5rem',
      right: '2.5rem',
      maxWidth: '480px',
      width: 'calc(100% - 5rem)',
      background: 'var(--surface)',
      border: '2px solid var(--primary)',
      borderRadius: 'var(--radius-lg)',
      padding: '1.75rem 2rem',
      boxShadow: 'var(--shadow-md)',
      zIndex: 9999,
      animation: 'slideUp 0.3s ease'
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <span style={{
            background: 'var(--primary)',
            color: '#fff',
            fontSize: '0.75rem',
            fontWeight: 800,
            padding: '0.25rem 0.65rem',
            borderRadius: 'var(--radius-sm)',
            textTransform: 'uppercase',
            letterSpacing: '0.06em'
          }}>
            {currentStep.badge || 'Guided Tour'}
          </span>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-faint)', fontWeight: 600 }}>
            Step {currentStepIndex + 1} of {totalSteps}
          </span>
        </div>

        <button
          onClick={endTour}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-faint)',
            cursor: 'pointer',
            padding: '0.2rem'
          }}
          title="Exit Walkthrough"
        >
          <X size={20} />
        </button>
      </div>

      {/* Step Title & Description */}
      <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-main)', marginBottom: '0.5rem' }}>
        {currentStep.title}
      </h3>
      <p style={{ fontSize: '0.95rem', color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: '1.5rem' }}>
        {currentStep.description}
      </p>

      {/* Progress Track & Navigation Buttons */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', gap: '6px' }}>
          {Array.from({ length: totalSteps }).map((_, i) => (
            <div
              key={i}
              style={{
                width: i === currentStepIndex ? '22px' : '8px',
                height: '8px',
                borderRadius: '4px',
                background: i === currentStepIndex ? 'var(--primary)' : 'var(--border-light)',
                transition: 'all 0.2s ease'
              }}
            />
          ))}
        </div>

        <div style={{ display: 'flex', gap: '0.6rem' }}>
          {currentStepIndex > 0 && (
            <button
              className="btn btn-outline"
              style={{ padding: '0.5rem 0.9rem', fontSize: '0.85rem' }}
              onClick={prevStep}
            >
              <ArrowLeft size={14} /> Back
            </button>
          )}

          <button
            className="btn btn-primary"
            style={{ padding: '0.5rem 1.1rem', fontSize: '0.85rem' }}
            onClick={nextStep}
          >
            {currentStepIndex < totalSteps - 1 ? (
              <>Next Step <ArrowRight size={14} /></>
            ) : (
              <><CheckCircle2 size={14} /> Done</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
