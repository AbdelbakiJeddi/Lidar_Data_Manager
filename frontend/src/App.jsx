import React, { useState, useEffect } from 'react';
import { getDatasets } from './api';
import DatasetList from './components/DatasetList';
import UploadModal from './components/UploadModal';
import ZoneSelector from './components/ZoneSelector';
import { Upload, RefreshCw, Box } from 'lucide-react';

function App() {
  const [datasets, setDatasets] = useState([]);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [selectedDatasetForZone, setSelectedDatasetForZone] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchDatasets = async () => {
    setIsRefreshing(true);
    try {
      const response = await getDatasets();
      setDatasets(response.data.datasets || []);
    } catch (err) {
      console.error('Failed to fetch datasets', err);
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDatasets();
    // Set up polling to check processing status
    const interval = setInterval(() => {
      fetchDatasets();
    }, 10000); // refresh every 10 seconds
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '40px 20px' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '40px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))', padding: '12px', borderRadius: '12px' }}>
            <Box color="white" size={28} />
          </div>
          <div>
            <h1 style={{ fontSize: '2rem', fontWeight: '700', letterSpacing: '-0.5px' }}>LiDAR Studio</h1>
            <p style={{ color: 'var(--text-muted)' }}>Manage and process point cloud data</p>
          </div>
        </div>
        
        <div style={{ display: 'flex', gap: '12px' }}>
          <button className="btn-secondary" onClick={fetchDatasets} disabled={isRefreshing}>
            <RefreshCw size={18} className={isRefreshing ? "spin-animation" : ""} /> Refresh
          </button>
          <button className="btn-primary" onClick={() => setIsUploadModalOpen(true)}>
            <Upload size={18} /> Upload Data
          </button>
        </div>
      </header>

      <main>
        <div className="glass-panel" style={{ padding: '32px', marginBottom: '24px', background: 'linear-gradient(to right, rgba(59, 130, 246, 0.1), rgba(139, 92, 246, 0.05))' }}>
          <h2 style={{ marginBottom: '12px', fontSize: '1.5rem' }}>Welcome to LiDAR Studio</h2>
          <p style={{ color: 'var(--text-muted)', lineHeight: '1.6', maxWidth: '800px' }}>
            A powerful web interface for your LiDAR point cloud data. Upload standard <code>.las</code> or <code>.laz</code> files,
            process them into highly efficient octree structures, and interactively crop and download specific zones using our spatial querying tools.
          </p>
        </div>

        <DatasetList 
          datasets={datasets} 
          onRefresh={fetchDatasets} 
          onSelectZone={setSelectedDatasetForZone} 
        />
      </main>

      <UploadModal 
        isOpen={isUploadModalOpen} 
        onClose={() => setIsUploadModalOpen(false)} 
        onUploadComplete={fetchDatasets}
      />

      {selectedDatasetForZone && (
        <ZoneSelector 
          dataset={selectedDatasetForZone} 
          onClose={() => setSelectedDatasetForZone(null)} 
        />
      )}
      
      <style>{`
        .spin-animation {
          animation: spin 1s linear infinite;
        }
        @keyframes spin { 100% { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}

export default App;
