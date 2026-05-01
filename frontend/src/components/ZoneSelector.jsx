import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet-draw'; // Import the side-effect
import { downloadZone } from '../api';
import { X, Download, AlertTriangle } from 'lucide-react';

import 'leaflet/dist/leaflet.css';
import 'leaflet-draw/dist/leaflet.draw.css';

// Fix for default marker icons in Leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// A small sub-component to handle the Draw logic within the Map context
const DrawManager = ({ onCreated, onDeleted }) => {
  const map = useMap();
  const drawControlRef = useRef(null);
  const drawnItemsRef = useRef(new L.FeatureGroup());

  useEffect(() => {
    map.addLayer(drawnItemsRef.current);

    const drawControl = new L.Control.Draw({
      edit: {
        featureGroup: drawnItemsRef.current,
        remove: true
      },
      draw: {
        rectangle: true,
        polygon: false,
        circle: false,
        circlemarker: false,
        marker: false,
        polyline: false,
      }
    });

    drawControlRef.current = drawControl;
    map.addControl(drawControl);

    const handleCreated = (e) => {
      const layer = e.layer;
      drawnItemsRef.current.addLayer(layer);
      onCreated(e);
    };

    const handleDeleted = () => {
      onDeleted();
    };

    map.on(L.Draw.Event.CREATED, handleCreated);
    map.on(L.Draw.Event.DELETED, handleDeleted);

    return () => {
      map.removeControl(drawControl);
      map.off(L.Draw.Event.CREATED, handleCreated);
      map.off(L.Draw.Event.DELETED, handleDeleted);
    };
  }, [map, onCreated, onDeleted]);

  return null;
};

const ZoneSelector = ({ dataset, onClose }) => {
  const [boundingBox, setBoundingBox] = useState(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState('');
  
  const [minZ, setMinZ] = useState(-1000);
  const [maxZ, setMaxZ] = useState(1000);

  const _onCreated = (e) => {
    const layer = e.layer;
    const bounds = layer.getBounds();
    setBoundingBox({
      min_x: bounds.getWest(),
      min_y: bounds.getSouth(),
      max_x: bounds.getEast(),
      max_y: bounds.getNorth(),
    });
  };

  const _onDeleted = () => {
    setBoundingBox(null);
  };

  const handleDownload = async () => {
    if (!boundingBox) return;
    setIsDownloading(true);
    setError('');
    
    try {
      const bboxWithZ = {
        ...boundingBox,
        min_z: parseFloat(minZ),
        max_z: parseFloat(maxZ),
      };
      await downloadZone(dataset.id, bboxWithZ);
      // Optional: keep modal open or close it
    } catch (err) {
      console.error('Download failed', err);
      setError('Failed to process and download zone. ' + (err.response?.data?.detail || ''));
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content glass-panel" style={{ maxWidth: '800px', height: '85vh', display: 'flex', flexDirection: 'column' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2>Select Zone for {dataset.dataset_name}</h2>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
            <X size={24} />
          </button>
        </div>
        
        <div style={{ flex: 1, borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--border-light)', marginBottom: '16px' }}>
          <MapContainer 
            center={[48.8566, 2.3522]} 
            zoom={13} 
            style={{ height: '100%', width: '100%', background: '#242424' }}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <DrawManager onCreated={_onCreated} onDeleted={_onDeleted} />
          </MapContainer>
        </div>
        
        <div style={{ display: 'flex', gap: '20px', alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>Min Z (Elevation)</label>
            <input type="number" className="form-input" value={minZ} onChange={e => setMinZ(e.target.value)} style={{ margin: 0 }} />
          </div>
          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>Max Z (Elevation)</label>
            <input type="number" className="form-input" value={maxZ} onChange={e => setMaxZ(e.target.value)} style={{ margin: 0 }} />
          </div>
          
          <button 
            className="btn-primary" 
            onClick={handleDownload} 
            disabled={!boundingBox || isDownloading}
            style={{ height: '43px', minWidth: '160px', justifyContent: 'center' }}
          >
            {isDownloading ? 'Processing...' : <><Download size={18} /> Download Zone</>}
          </button>
        </div>
        
        {error && (
          <div style={{ marginTop: '16px', color: 'var(--warning)', display: 'flex', alignItems: 'center', gap: '8px', padding: '12px', background: 'rgba(245, 158, 11, 0.1)', borderRadius: '8px', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
            <AlertTriangle size={18} /> {error}
          </div>
        )}
      </div>
    </div>
  );
};

export default ZoneSelector;
