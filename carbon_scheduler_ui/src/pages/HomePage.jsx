import React from 'react';
import TopNavbar from '../components/layout/TopNavbar';
import SectionNav from '../components/layout/SectionNav';
import HeroSection from '../sections/HeroSection';
import HistoricalReplaySection from '../sections/HistoricalReplaySection';
import DecompositionSection from '../sections/DecompositionSection';
import ForecastingSection from '../sections/ForecastingSection';
import SupportingEvidenceSection from '../sections/SupportingEvidenceSection';
import '../styles/demo.css';
import '../styles/sections.css';

export default function HomePage() {
  return (
    <div className="dashboard-container">
      <TopNavbar />
      <SectionNav />
      <main>
        <HeroSection />
        <HistoricalReplaySection />
        <DecompositionSection />
        <ForecastingSection />
        <SupportingEvidenceSection />
      </main>
    </div>
  );
}
