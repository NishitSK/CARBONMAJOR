import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { TourProvider } from './context/TourContext';
import { DataModeProvider } from './data/DataModeContext';
import AwsSpotlightTour from './components/common/AwsSpotlightTour';
import AuditPage from './pages/AuditPage';
import AuditReportPage from './pages/AuditReportPage';
import ConsolePage from './pages/ConsolePage';
import ForecastingPage from './pages/ForecastingPage';
import PilotTelemetryPage from './pages/PilotTelemetryPage';
import PlaygroundPage from './pages/PlaygroundPage';
import AboutPage from './pages/AboutPage';

function App() {
  return (
    <BrowserRouter>
      <DataModeProvider>
        <TourProvider>
          <Routes>
            <Route path="/" element={<AuditPage />} />
            <Route path="/report" element={<AuditReportPage />} />
            <Route path="/console" element={<ConsolePage />} />
            <Route path="/forecasting" element={<ForecastingPage />} />
            <Route path="/pilot" element={<PilotTelemetryPage />} />
            <Route path="/playground" element={<PlaygroundPage />} />
            <Route path="/about" element={<AboutPage />} />
          </Routes>
          <AwsSpotlightTour />
        </TourProvider>
      </DataModeProvider>
    </BrowserRouter>
  );
}

export default App;
