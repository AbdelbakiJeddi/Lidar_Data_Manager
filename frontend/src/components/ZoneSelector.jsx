import React, { useState, useEffect, useRef, useMemo } from 'react';
import { MapContainer, TileLayer, useMap, Rectangle } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet-draw';
import { downloadZone } from '../api';
import { X, Download, AlertTriangle, Layers, Maximize2, Crosshair, HelpCircle, Info, RefreshCw } from 'lucide-react';

import 'leaflet/dist/leaflet.css';
import 'leaflet-draw/dist/leaflet.draw.css';

// Fix for default marker icons in Leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Component to handle map centering and reference bounds
const MapEffects = ({ dataset }) => {
  const map = useMap();

  useEffect(() => {
    const geoBbox = dataset.geographic_bbox || dataset.bbox;
    if (geoBbox) {
      const bounds = L.latLngBounds(
        [geoBbox.min_y, geoBbox.min_x],
        [geoBbox.max_y, geoBbox.max_x]
      );
      map.fitBounds(bounds, { padding: [50, 50], animate: true });
    }
  }, [map, dataset]);

  return null;
};

// Draw logic manager
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
        rectangle: {
          shapeOptions: {
            color: '#3b82f6',
            weight: 2,
            fillOpacity: 0.2
          }
        },
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
      drawnItemsRef.current.clearLayers(); // Only allow one selection at a time
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

const ZoneSelector = ({ dataset: initialDataset, onClose }) => {
  const [dataset, setDataset] = useState(initialDataset);
  const [boundingBox, setBoundingBox] = useState(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isLoadingMetadata, setIsLoadingMetadata] = useState(false);
  const [error, setError] = useState('');
  
  const [minZ, setMinZ] = useState(dataset.bbox?.min_z?.toFixed(2) || -100);
  const [maxZ, setMaxZ] = useState(dataset.bbox?.max_z?.toFixed(2) || 100);

  // Fetch missing metadata if needed
  useEffect(() => {
    const fetchMetadata = async () => {
      if (!dataset.geographic_bbox) {
        setIsLoadingMetadata(true);
        try {
          const response = await fetch(`${import.meta.env.VITE_API_URL}/lidar/datasets/${dataset.id}/info`);
          const info = await response.json();
          setDataset(prev => ({
            ...prev,
            bbox: info.bbox,
            geographic_bbox: info.geographic_bbox,
            srs_wkt: info.srs_wkt
          }));
        } catch (err) {
          console.error('Failed to fetch metadata', err);
        } finally {
          setIsLoadingMetadata(false);
        }
      }
    };
    fetchMetadata();
  }, [dataset.id]);

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
    } catch (err) {
      console.error('Download failed', err);
      setError('Extraction failed. Ensure your selection overlaps with the dataset area.');
    } finally {
      setIsDownloading(false);
    }
  };

  const datasetBounds = useMemo(() => {
    const geoBbox = dataset.geographic_bbox;
    if (!geoBbox) return null;
    return [
      [geoBbox.min_y, geoBbox.min_x],
      [geoBbox.max_y, geoBbox.max_x]
    ];
  }, [dataset.geographic_bbox]);

  return (
    <div className="modal-overlay">
      <div className="modal-content glass-panel" style={{ padding: 0, display: 'flex', flexDirection: 'row', height: '80vh' }}>
        
        {/* Left: Interactive Map */}
        <div style={{ flex: 1, position: 'relative', borderRight: '1px solid var(--border-light)' }}>
          <MapContainer 
            center={[48.8566, 2.3522]} 
            zoom={13} 
            style={{ height: '100%', width: '100%' }}
            zoomControl={false}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.carto.com/">CARTO</a>'
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            />
            {datasetBounds && (
              <Rectangle 
                bounds={datasetBounds} 
                pathOptions={{ color: '#8b5cf6', weight: 1, dashArray: '5, 5', fillOpacity: 0.05 }} 
              />
            )}
            <MapEffects dataset={dataset} />
            <DrawManager onCreated={_onCreated} onDeleted={_onDeleted} />
          </MapContainer>
          
          {isLoadingMetadata && (
            <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 2000, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(4px)' }}>
              <RefreshCw className="spin-animation" size={32} color="var(--accent-primary)" />
              <p style={{ marginTop: '16px', fontWeight: '600', color: 'var(--text-main)' }}>Extracting Spatial Metadata...</p>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: '4px' }}>Analyzing dataset coordinate system</p>
            </div>
          )}

          <div style={{ position: 'absolute', top: '20px', left: '20px', zIndex: 1000, pointerEvents: 'none' }}>
            <div className="glass-panel" style={{ padding: '10px 16px', background: 'var(--bg-card-heavy)', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Layers size={16} className="text-accent" style={{ color: 'var(--accent-primary)' }} />
              <span style={{ fontSize: '0.8rem', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Spatial Selector</span>
            </div>
          </div>
        </div>

        {/* Right: Controls & Info */}
        <div style={{ width: '380px', display: 'flex', flexDirection: 'column', background: 'var(--bg-card-heavy)' }}>
          <div style={{ padding: '24px', borderBottom: '1px solid var(--border-light)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: '700', marginBottom: '4px' }}>Zone Extraction</h2>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>{dataset.dataset_name}</p>
            </div>
            <button onClick={onClose} className="btn-secondary" style={{ padding: '8px', minWidth: 'auto', borderRadius: '10px' }}>
              <X size={20} />
            </button>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
            {/* Dataset Info */}
            <div style={{ marginBottom: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <Info size={14} color="var(--accent-primary)" />
                <span style={{ fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Dataset Scope</span>
              </div>
              
              <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-light)', borderRadius: '12px', padding: '16px', marginBottom: '12px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div>
                    <label className="form-label" style={{ fontSize: '0.7rem' }}>Native X Range</label>
                    <div style={{ fontSize: '0.85rem', fontFamily: 'monospace', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {dataset.bbox?.min_x?.toFixed(1)}...{dataset.bbox?.max_x?.toFixed(1)}
                    </div>
                  </div>
                  <div>
                    <label className="form-label" style={{ fontSize: '0.7rem' }}>Native Y Range</label>
                    <div style={{ fontSize: '0.85rem', fontFamily: 'monospace', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {dataset.bbox?.min_y?.toFixed(1)}...{dataset.bbox?.max_y?.toFixed(1)}
                    </div>
                  </div>
                </div>
              </div>

              {!dataset.geographic_bbox && (
                <div style={{ padding: '16px', background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.2)', borderRadius: '12px' }}>
                  <div style={{ display: 'flex', gap: '10px', marginBottom: '8px' }}>
                    <AlertTriangle size={16} color="var(--warning)" />
                    <span style={{ fontSize: '0.8rem', fontWeight: '600', color: 'var(--warning)' }}>No Coordinate System Found</span>
                  </div>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-dim)', lineHeight: '1.4', marginBottom: '12px' }}>
                    The map cannot be displayed because the file is missing SRS metadata. 
                    If you know the EPSG code (e.g. 32631), enter it below:
                  </p>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <input 
                      type="text" 
                      placeholder="EPSG:32631" 
                      className="form-input" 
                      style={{ height: '36px', fontSize: '0.8rem' }}
                      id="epsg-input"
                    />
                    <button 
                      className="btn-secondary" 
                      style={{ height: '36px', minWidth: 'auto', padding: '0 12px' }}
                      onClick={async () => {
                        const epsg = document.getElementById('epsg-input').value;
                        if (!epsg) return;
                        setIsLoadingMetadata(true);
                        try {
                          const res = await fetch(`${import.meta.env.VITE_API_URL}/lidar/datasets/${dataset.id}/info?override_srs=${epsg}`);
                          const info = await res.json();
                          setDataset(prev => ({ ...prev, ...info }));
                        } catch (err) {
                          console.error(err);
                        } finally {
                          setIsLoadingMetadata(false);
                        }
                      }}
                    >
                      Apply
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Selection Coordinates */}
            <div style={{ marginBottom: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <Crosshair size={14} color={boundingBox ? "var(--accent-primary)" : "var(--text-dim)"} />
                <span style={{ fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Selection Bounds</span>
              </div>
              {!boundingBox ? (
                <div style={{ padding: '20px', textAlign: 'center', border: '1px dashed var(--border-light)', borderRadius: '12px', color: 'var(--text-dim)', fontSize: '0.85rem' }}>
                  Draw a rectangle on the map to begin selection
                </div>
              ) : (
                <div style={{ background: 'rgba(59, 130, 246, 0.05)', border: '1px solid rgba(59, 130, 246, 0.2)', borderRadius: '12px', padding: '16px' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                    <div>
                      <label className="form-label" style={{ fontSize: '0.7rem', color: 'var(--accent-primary)' }}>MIN LON/LAT</label>
                      <div style={{ fontSize: '0.85rem', fontWeight: '500' }}>{boundingBox.min_x.toFixed(5)}, {boundingBox.min_y.toFixed(5)}</div>
                    </div>
                    <div>
                      <label className="form-label" style={{ fontSize: '0.7rem', color: 'var(--accent-primary)' }}>MAX LON/LAT</label>
                      <div style={{ fontSize: '0.85rem', fontWeight: '500' }}>{boundingBox.max_x.toFixed(5)}, {boundingBox.max_y.toFixed(5)}</div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Elevation Controls */}
            <div style={{ marginBottom: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <Maximize2 size={14} color="var(--accent-primary)" />
                <span style={{ fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Elevation Filter (Z)</span>
              </div>
              <div style={{ display: 'flex', gap: '12px' }}>
                <div style={{ flex: 1 }}>
                  <label className="form-label" style={{ fontSize: '0.7rem' }}>MIN Z</label>
                  <input type="number" className="form-input" value={minZ} onChange={e => setMinZ(e.target.value)} />
                </div>
                <div style={{ flex: 1 }}>
                  <label className="form-label" style={{ fontSize: '0.7rem' }}>MAX Z</label>
                  <input type="number" className="form-input" value={maxZ} onChange={e => setMaxZ(e.target.value)} />
                </div>
              </div>
            </div>

            {error && (
              <div style={{ color: 'var(--error)', fontSize: '0.8rem', display: 'flex', gap: '8px', padding: '12px', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '10px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                <AlertTriangle size={16} style={{ flexShrink: 0 }} /> {error}
              </div>
            )}
          </div>

          <div style={{ padding: '24px', borderTop: '1px solid var(--border-light)', background: 'rgba(0,0,0,0.2)' }}>
            <button 
              className="btn-primary" 
              onClick={handleDownload} 
              disabled={!boundingBox || isDownloading}
              style={{ width: '100%', justifyContent: 'center' }}
            >
              {isDownloading ? (
                <>Processing...</>
              ) : (
                <><Download size={18} /> Download Selection</>
              )}
            </button>
            <div style={{ marginTop: '12px', display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-dim)', fontSize: '0.7rem', justifyContent: 'center' }}>
              <HelpCircle size={12} /> Only LAS/LAZ format supported
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ZoneSelector;
