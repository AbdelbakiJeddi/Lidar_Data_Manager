import React, { lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Dashboard from './pages/Dashboard';

// Lazy-load the heavy Potree viewer so it's only downloaded when navigated to
const PotreeViewerPage = lazy(() => import('./pages/PotreeViewerPage'));

function App() {
  return (
    <Router>
      <Suspense fallback={
        <div className="w-screen h-screen bg-black flex items-center justify-center">
          <div className="text-center space-y-3">
            <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mx-auto" />
            <p className="text-gray-400 text-sm">Loading viewer...</p>
          </div>
        </div>
      }>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/viewer" element={<PotreeViewerPage />} />
        </Routes>
      </Suspense>
    </Router>
  );
}

export default App;
