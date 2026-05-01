import React, { useState, useRef } from 'react';
import { uploadDataset } from '../api';
import { UploadCloud, X } from 'lucide-react';

const UploadModal = ({ isOpen, onClose, onUploadComplete }) => {
  const [datasetName, setDatasetName] = useState('');
  const [file, setFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);

  if (!isOpen) return null;

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) setFile(droppedFile);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!datasetName || !file) {
      setError('Please provide a dataset name and select a file.');
      return;
    }
    
    setIsUploading(true);
    setError('');
    
    try {
      await uploadDataset(datasetName, file, (progressEvent) => {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        setProgress(percentCompleted);
      });
      onUploadComplete();
      onClose();
      // Reset state
      setDatasetName('');
      setFile(null);
      setProgress(0);
    } catch (err) {
      setError('Failed to upload file. Please try again.');
      console.error(err);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content glass-panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2>Upload LiDAR Dataset</h2>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
            <X size={24} />
          </button>
        </div>
        
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>Dataset Name</label>
            <input 
              className="form-input"
              type="text" 
              value={datasetName} 
              onChange={(e) => setDatasetName(e.target.value)} 
              placeholder="e.g. City_Center_Scan_01"
              required
            />
          </div>
          
          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>LiDAR File (.las or .laz)</label>
            <div 
              className="drop-zone"
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current.click()}
            >
              <UploadCloud size={48} color="var(--accent-primary)" style={{ marginBottom: '16px' }} />
              {file ? (
                <p style={{ color: 'var(--success)', fontWeight: '500' }}>{file.name}</p>
              ) : (
                <p>Drag and drop a file here, or click to select</p>
              )}
              <input 
                type="file" 
                ref={fileInputRef} 
                style={{ display: 'none' }} 
                accept=".las,.laz" 
                onChange={(e) => setFile(e.target.files[0])} 
              />
            </div>
          </div>
          
          {error && <p style={{ color: 'var(--error)', marginBottom: '16px' }}>{error}</p>}
          
          {isUploading && (
            <div style={{ marginBottom: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span>Uploading...</span>
                <span>{progress}%</span>
              </div>
              <div style={{ width: '100%', height: '8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{ width: `${progress}%`, height: '100%', background: 'var(--accent-primary)', transition: 'width 0.2s ease' }} />
              </div>
            </div>
          )}
          
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
            <button type="button" className="btn-secondary" onClick={onClose} disabled={isUploading}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={isUploading || !file || !datasetName}>
              {isUploading ? 'Uploading...' : 'Upload'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default UploadModal;
