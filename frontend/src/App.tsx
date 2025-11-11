/**
 * Main App component with routing
 */

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { DashboardPage } from './pages/DashboardPage';
import { ExtractionPage } from './pages/ExtractionPage';
import { CalculationInputPage } from './pages/CalculationInputPage';
import { CalculationResultsPage } from './pages/CalculationResultsPage';
import { NotFoundPage } from './pages/NotFoundPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/extraction/:documentId" element={<ExtractionPage />} />
        <Route path="/calculation/:documentId/input" element={<CalculationInputPage />} />
        <Route path="/calculation/:calculationId/results" element={<CalculationResultsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
