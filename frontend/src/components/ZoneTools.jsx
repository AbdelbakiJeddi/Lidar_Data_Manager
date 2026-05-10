import React from 'react';
import { X, SquarePen, Download, Eye, Loader2, AlertTriangle } from 'lucide-react';
import { useLidarStore } from '../store/useLidarStore';
import { getCropPreviewUrl } from '../api';

export default function ZoneTools({ onExtract, onClear }) {
  const selectedDataset = useLidarStore(state => state.selectedDataset);
  const boundingBox = useLidarStore(state => state.boundingBox);
  const setDrawMode = useLidarStore(state => state.setDrawMode);
  const setSelectedDataset = useLidarStore(state => state.setSelectedDataset);
  const clearBoundingBox = useLidarStore(state => state.clearBoundingBox);
  
  const [extracting, setExtracting] = React.useState(false);
  const [preparingPreview, setPreparingPreview] = React.useState(false);
  const [extractError, setExtractError] = React.useState('');

  const handleExtract = async () => {
    if (!boundingBox) return;
    setExtracting(true);
    setExtractError('');
    try {
      await onExtract(
        boundingBox.west,
        boundingBox.south,
        boundingBox.east,
        boundingBox.north,
      );
    } catch (err) {
      console.error('Extraction failed:', err);
      const message = err.response?.status === 404
        ? 'No data found in the selected area.'
        : 'Extraction failed. Please try again.';
      setExtractError(message);
    } finally {
      setExtracting(false);
    }
  };

  const handleClear = () => {
    clearBoundingBox();
    setExtractError('');
    onClear?.();
  };

  const handleClose = () => {
    setSelectedDataset(null);
    clearBoundingBox();
    setExtractError('');
  };

  if (!selectedDataset) return null;

  return (
    <div className="zone-tools-panel">
      <div className="zone-tools-header">
        <span className="zone-title">Select Area</span>
        <button onClick={handleClose} className="close-btn-small">
          <X size={12} />
        </button>
      </div>

      {!boundingBox ? (
        <button 
          onClick={() => setDrawMode(true)}
          className="btn-primary full-width"
        >
          <SquarePen size={12} /> Draw Zone
        </button>
      ) : (
        <>
          <div className="bbox-info">
            <p className="bbox-label">Selected Region</p>
            <p className="bbox-coords">
              {boundingBox.south.toFixed(4)}°, {boundingBox.west.toFixed(4)}°
              <span className="bbox-arrow">→</span>
              {boundingBox.north.toFixed(4)}°, {boundingBox.east.toFixed(4)}°
            </p>
          </div>

          {extractError && (
            <div className="error-message">
              <AlertTriangle size={14} />
              <p className="error-text">{extractError}</p>
            </div>
          )}

          <div className="action-buttons">
            <button 
              onClick={handleExtract}
              disabled={extracting}
              className="btn-primary full-width"
            >
              {extracting ? (
                <><Loader2 size={12} className="spin-animation" /> Extracting...</>
              ) : (
                <>Extract</>
              )}
            </button>
            <button 
              onClick={async () => {
                if (!selectedDataset?.id || !boundingBox) return;
                setPreparingPreview(true);
                try {
                  const res = await getCropPreviewUrl(boundingBox);
                  const url = res.data.url;
                  window.open(
                    `/viewer?urls=${encodeURIComponent(JSON.stringify([url]))}`,
                    '_blank'
                  );
                } catch (err) {
                  console.error('Failed to prepare preview:', err);
                  setExtractError('Failed to prepare 3D preview.');
                } finally {
                  setPreparingPreview(false);
                }
              }}
              disabled={preparingPreview}
              className="btn-secondary full-width"
            >
              {preparingPreview ? (
                <><Loader2 size={12} className="spin-animation" /> Preparing...</>
              ) : (
                <>Visualize</>
              )}
            </button>
            <button 
              onClick={handleClear}
              className="btn-clear full-width"
            >
              Clear Selection
            </button>
          </div>
        </>
      )}
    </div>
  );
}