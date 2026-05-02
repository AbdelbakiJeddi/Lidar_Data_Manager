import React, { useState, useEffect } from 'react';
import { getDatasets } from './api';
import DatasetList from './components/DatasetList';
import UploadModal from './components/UploadModal';
import ZoneSelector from './components/ZoneSelector';
import { Upload, RefreshCw, Box, Database, Sparkles } from 'lucide-react';

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
    const interval = setInterval(() => {
      fetchDatasets();
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ maxWidth: '1300px', margin: '0 auto', padding: '60px 40px' }}>
      {/* Decorative Background Elements */}
      <div style={{ position: 'fixed', top: '-10%', left: '-5%', width: '40%', height: '40%', background: 'radial-gradient(circle, rgba(59, 130, 246, 0.03) 0%, transparent 70%)', zIndex: -1 }}></div>
      <div style={{ position: 'fixed', bottom: '-10%', right: '-5%', width: '40%', height: '40%', background: 'radial-gradient(circle, rgba(139, 92, 246, 0.03) 0%, transparent 70%)', zIndex: -1 }}></div>

      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '60px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <div style={{ 
            background: 'var(--accent-gradient)', 
            padding: '14px', 
            borderRadius: '16px',
            boxShadow: '0 8px 20px rgba(59, 130, 246, 0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <Box color="white" size={32} strokeWidth={2.5} />
          </div>
          <div>
            <h1 style={{ fontSize: '2.5rem', fontWeight: '800', letterSpacing: '-1px', lineHeight: 1.1 }}>LiDAR Studio</h1>
            <p style={{ color: 'var(--text-muted)', fontSize: '1.1rem', fontWeight: '500' }}>Precision Point Cloud Management</p>
          </div>
        </div>
        
        <div style={{ display: 'flex', gap: '16px' }}>
          <button className="btn-secondary" onClick={fetchDatasets} disabled={isRefreshing}>
            <RefreshCw size={18} className={isRefreshing ? "spin-animation" : ""} /> 
            <span style={{ fontWeight: '600' }}>Refresh Data</span>
          </button>
          <button className="btn-primary" onClick={() => setIsUploadModalOpen(true)}>
            <Upload size={18} /> 
            <span style={{ fontWeight: '700' }}>Upload Dataset</span>
          </button>
        </div>
      </header>

      <main>
        <div className="glass-panel" style={{ 
          padding: '40px', 
          marginBottom: '40px', 
          background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, rgba(139, 92, 246, 0.04) 100%)',
          position: 'relative',
          overflow: 'hidden'
        }}>
          <div style={{ position: 'absolute', top: '-50px', right: '-50px', opacity: 0.1 }}>
            <Database size={200} color="var(--accent-primary)" />
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
            <Sparkles size={18} color="var(--warning)" />
            <span style={{ fontSize: '0.85rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--warning)' }}>New Generation Octree Engine</span>
          </div>
          
          <h2 style={{ marginBottom: '16px', fontSize: '2rem', fontWeight: '700' }}>Cloud-Scale LiDAR Processing</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '1.1rem', lineHeight: '1.7', maxWidth: '900px', fontWeight: '400' }}>
            Transform massive point clouds into streaming-ready octree structures. 
            Select specific spatial zones with pinpoint accuracy using our 3D-aware coordinate selection system 
            and export optimized <code>.las</code> datasets in seconds.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
          <div style={{ width: '4px', height: '24px', background: 'var(--accent-gradient)', borderRadius: '4px' }}></div>
          <h3 style={{ fontSize: '1.25rem', fontWeight: '700' }}>Active Workspace</h3>
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
        
        .text-accent {
          background: var(--accent-gradient);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }
      `}</style>
    </div>
  );
}

export default App;
