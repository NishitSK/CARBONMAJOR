import React, { createContext, useContext, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const TourContext = createContext(null);

export const TOUR_STEPS = [
  {
    stepIndex: 0,
    page: '/',
    targetId: 'tour-audit-presets',
    title: 'Start from a fictional company',
    badge: 'Placement Audit',
    description: 'Load a preset workload fleet — a food-delivery app, a mid-size SaaS, or a large bank — or edit your own. Everything here runs on simulated data, entirely in this browser.',
    position: 'bottom'
  },
  {
    stepIndex: 1,
    page: '/',
    targetId: 'tour-audit-workloads',
    title: 'Every workload, one row each',
    badge: 'Placement Audit',
    description: 'SLA, data class, current region, size. Notice some workloads hold personal data or need very low latency — those will never move, and the audit will say exactly why.',
    position: 'top'
  },
  {
    stepIndex: 2,
    page: '/',
    targetId: 'tour-audit-summary',
    title: 'The result: move, shift, or stay — with a reason',
    badge: 'Placement Audit',
    description: 'Run the audit. Each workload is triaged, with real ₹ and tonnes-CO₂ numbers, then check individual decisions below — including the ones the audit correctly refuses to move.',
    position: 'bottom'
  },
  {
    stepIndex: 3,
    page: '/console',
    targetId: 'tour-kpis',
    title: 'Under the hood: fleet health',
    badge: 'Console',
    description: 'The engineering console behind the audit — live telemetry across all 12 regions, for anyone who wants to see the mechanism, not just the recommendation.',
    position: 'bottom'
  },
  {
    stepIndex: 4,
    page: '/console',
    targetId: 'tour-dispatcher',
    title: 'Route a workload under residency rules',
    badge: 'Console',
    description: 'Each workload stream is bound to a jurisdiction with fixed data-residency limits. Dispatch one to watch the scheduler choose the cleanest region that jurisdiction actually allows.',
    position: 'top'
  },
  {
    stepIndex: 5,
    page: '/console',
    targetId: 'tour-fleet-table',
    title: 'Per-region telemetry',
    badge: 'Console',
    description: 'Live latency, grid carbon intensity, and the EC2 instance handling each region. Filter by region group to narrow the view.',
    position: 'top'
  },
  {
    stepIndex: 6,
    page: '/forecasting',
    targetId: 'tour-horizon-stages',
    title: 'Pick a planning horizon',
    badge: 'Forecasting',
    description: 'Choose how far ahead to plan — 3, 6, or 12 hours. A longer horizon can reach a deeper carbon dip, but relies on a forecast that is less certain the further out it looks.',
    position: 'bottom'
  },
  {
    stepIndex: 7,
    page: '/forecasting',
    targetId: 'tour-model-compare',
    title: 'Compare the two forecasters',
    badge: 'Forecasting',
    description: 'Two models predict the same region independently: a neural CarbonLSTM and a statistical ARIMA(2,1,2). Each proposes when to start the workload and the carbon intensity it expects at that time.',
    position: 'bottom'
  },
  {
    stepIndex: 8,
    page: '/forecasting',
    targetId: 'tour-forward-table',
    title: 'Read the hour-by-hour forecast',
    badge: 'Forecasting',
    description: 'Projected carbon intensity for every hour out to the horizon. The highlighted row is each model’s recommended start time — the cleanest hour it can see.',
    position: 'top'
  },
  {
    stepIndex: 9,
    page: '/forecasting',
    targetId: 'tour-accuracy',
    title: 'Check the track record before trusting it',
    badge: 'Forecasting',
    description: 'Every past prediction, scored against what actually happened. “Direction correct” is how often the model called the trend right; “regret” is how often acting on its advice to wait turned out worse. LSTM tracks well; ARIMA is currently held back because it does not.',
    position: 'top'
  },
  {
    stepIndex: 10,
    page: '/forecasting',
    targetId: 'tour-guard',
    title: 'How a weak forecast is contained',
    badge: 'Forecasting',
    description: 'Before any forecast is allowed to delay work, the no-regret guard checks the expected saving against a threshold earned from the track record above. If the saving falls short, the job runs now instead of waiting.',
    position: 'top'
  },
  {
    stepIndex: 11,
    page: '/playground',
    targetId: 'tour-solar-trail',
    title: 'Watch a full day of migrations',
    badge: 'Playground',
    description: 'Scrub through 24 hours to see the workload follow the cleanest grid from region to region as demand and renewable generation shift over the day.',
    position: 'bottom'
  },
  {
    stepIndex: 12,
    page: '/pilot',
    targetId: 'tour-pilot-stream',
    title: 'The live pilot',
    badge: 'Pilot',
    description: 'Real hourly runs across the multi-region fleet. Each entry is an actual scheduling decision and the cloud execution record that followed it.',
    position: 'top'
  }
];

export function TourProvider({ children }) {
  const [isTourActive, setIsTourActive] = useState(false);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const navigate = useNavigate();

  const startTour = (step = 0) => {
    setCurrentStepIndex(step);
    setIsTourActive(true);
    const target = TOUR_STEPS[step];
    if (target && target.page) {
      navigate(target.page);
    }
  };

  const nextStep = () => {
    if (currentStepIndex < TOUR_STEPS.length - 1) {
      const nextIdx = currentStepIndex + 1;
      setCurrentStepIndex(nextIdx);
      const nextTarget = TOUR_STEPS[nextIdx];
      if (nextTarget && nextTarget.page) {
        navigate(nextTarget.page);
      }
    } else {
      endTour();
    }
  };

  const prevStep = () => {
    if (currentStepIndex > 0) {
      const prevIdx = currentStepIndex - 1;
      setCurrentStepIndex(prevIdx);
      const prevTarget = TOUR_STEPS[prevIdx];
      if (prevTarget && prevTarget.page) {
        navigate(prevTarget.page);
      }
    }
  };

  const endTour = () => {
    setIsTourActive(false);
    setCurrentStepIndex(0);
  };

  return (
    <TourContext.Provider value={{
      isTourActive,
      currentStepIndex,
      currentStep: TOUR_STEPS[currentStepIndex],
      totalSteps: TOUR_STEPS.length,
      startTour,
      nextStep,
      prevStep,
      endTour
    }}>
      {children}
    </TourContext.Provider>
  );
}

export function useTour() {
  const context = useContext(TourContext);
  if (!context) {
    throw new Error('useTour must be used within a TourProvider');
  }
  return context;
}
