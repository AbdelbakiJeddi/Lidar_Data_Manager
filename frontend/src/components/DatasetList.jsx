import React from 'react';
import { processDataset } from '../api';
import { Play, Download, Map, HardDrive } from 'lucide-react';

const DatasetList = ({ datasets, onRefresh, onSelectZone }) => {
  const handleProcess = async (datasetId) => {
    try {
      await processDataset(datasetId);
      onRefresh(); // Refresh the list to show "processing"
    } catch (err) {
      console.error('Failed to start processing', err);
      alert('Failed to start processing. See console for details.');
    }
  };

  const formatSize = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="glass-panel" style={{ marginTop: '24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
        <HardDrive color="var(--accent-primary)" />
        <h2>Available Datasets</h2>
      </div>
      
      {datasets.length === 0 ? (
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
          No datasets found. Upload one to get started.
        </div>
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Filename</th>
                <th>Size</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((ds) => (
                <tr key={ds.id}>
                  <td style={{ fontWeight: '500' }}>{ds.dataset_name}</td>
                  <td style={{ color: 'var(--text-muted)' }}>{ds.filename}</td>
                  <td>{formatSize(ds.size)}</td>
                  <td>
                    <span className={`status-badge status-${ds.status}`}>
                      {ds.status.charAt(0).toUpperCase() + ds.status.slice(1)}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      {ds.status === 'uploaded' && (
                        <button className="btn-primary" onClick={() => handleProcess(ds.id)} style={{ padding: '6px 12px', fontSize: '0.85rem' }}>
                          <Play size={14} /> Process
                        </button>
                      )}
                      
                      {ds.status === 'completed' && (
                        <button className="btn-success" onClick={() => onSelectZone(ds)} style={{ padding: '6px 12px', fontSize: '0.85rem' }}>
                          <Map size={14} /> Select Zone
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default DatasetList;
