import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { MapContainer, TileLayer, useMap, Rectangle, Polygon, Polyline, CircleMarker, useMapEvents, Tooltip } from 'react-leaflet';
import L from 'leaflet';
import { getDatasets, downloadZone, uploadDataset, processDataset, downloadMultiZone } from './api';
import { Box, Upload, RefreshCw, Layers, Database, X, Download, AlertTriangle, Maximize2, Crosshair, HelpCircle, Info, MousePointer, CheckCircle2, RotateCcw, Loader2 } from 'lucide-react';
import 'leaflet/dist/leaflet.css';

// Colors for dataset contours
const CONTOUR_COLORS = ['#8b5cf6', '#ec4899', '#14b8a6', '#f59e0b', '#3b82f6'];

const makeCornerIcon = (color, size = 14) => L.divIcon({
  className: 'corner-marker',
  html: `<div style="
    width: ${size}px; height: ${size}px; border-radius: 50%;
    background: ${color}; border: 2px solid #fff;
    box-shadow: 0 0 8px ${color}88, 0 2px 4px rgba(0,0,0,0.4);
    cursor: grab;
  "></div>`,
  iconSize: [size, size],
  iconAnchor: [size/2, size/2],
});

// Component to handle map centering when a dataset is selected
const MapEffects = ({ dataset }) => {
  const map = useMap();
  useEffect(() => {
    if (dataset?.geographic_bbox) {
      const bounds = L.latLngBounds(
        [dataset.geographic_bbox.min_y, dataset.geographic_bbox.min_x],
        [dataset.geographic_bbox.max_y, dataset.geographic_bbox.max_x]
      );
      map.flyToBounds(bounds, { padding: [50, 50], duration: 1.5 });
    }
  }, [map, dataset]);
  return null;
};

// Click handler for placing polygon points
const ClickHandler = ({ onMapClick, activeDataset }) => {
  useMapEvents({ 
    click: (e) => {
      if (activeDataset) onMapClick(e);
    }
  });
  return null;
};

const CLOSE_THRESHOLD_PX = 15;

function App() {
  const [datasets, setDatasets] = useState([]);
  const [activeDataset, setActiveDataset] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [mapRef, setMapRef] = useState(null);

  // Background Upload State
  const fileInputRef = useRef(null);
  const [uploadingFiles, setUploadingFiles] = useState([]); // { id, name, progress }

  // Polygon State
  const [points, setPoints] = useState([]);
  const [isClosed, setIsClosed] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState('');

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
    const interval = setInterval(fetchDatasets, 10000);
    return () => clearInterval(interval);
  }, []);

  // Reset drawing when explicitly closing the dataset bar
  useEffect(() => {
    if (!activeDataset) {
      setPoints([]);
      setIsClosed(false);
      setError('');
    }
  }, [activeDataset]);

  const handleMapClick = useCallback((e) => {
    if (isClosed || !activeDataset) return;

    if (points.length >= 3 && mapRef) {
      const startPx = mapRef.latLngToContainerPoint(points[0]);
      const clickPx = mapRef.latLngToContainerPoint(e.latlng);
      if (startPx.distanceTo(clickPx) < CLOSE_THRESHOLD_PX) {
        setIsClosed(true);
        return;
      }
    }
    setPoints(prev => [...prev, e.latlng]);
  }, [isClosed, points, mapRef, activeDataset]);

  const handleResetDrawing = () => {
    setPoints([]);
    setIsClosed(false);
    setError('');
  };

  const handleUndoLast = () => {
    if (isClosed) setIsClosed(false);
    else setPoints(prev => prev.slice(0, -1));
    setError('');
  };

  const handleDownload = async () => {
    if (!isClosed || points.length < 3) return;
    setIsDownloading(true);
    setError('');
    try {
      // Convert polygon points to bounding box
      const lngs = points.map(p => p.lng);
      const lats = points.map(p => p.lat);
      const minX = Math.min(...lngs);
      const maxX = Math.max(...lngs);
      const minY = Math.min(...lats);
      const maxY = Math.max(...lats);
      
      // Multi-dataset extraction with rectangular bbox
      await downloadMultiZone(minX, minY, maxX, maxY);
    } catch (err) {
      console.error('Download failed', err);
      setError('Extraction failed. Ensure your selection overlaps with available datasets.');
    } finally {
      setIsDownloading(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Reset input so the same file can be selected again if needed
    e.target.value = null;

    const uploadId = Math.random().toString(36).substring(7);
    const datasetName = file.name.replace(/\.[^/.]+$/, ""); // Remove extension

    setUploadingFiles(prev => [...prev, { id: uploadId, name: datasetName, progress: 0 }]);

    try {
      const response = await uploadDataset(datasetName, file, (progressEvent) => {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        setUploadingFiles(prev => prev.map(u => u.id === uploadId ? { ...u, progress: percentCompleted } : u));
      });
      
      const datasetId = response.data.dataset_id;
      
      // Auto-process right after upload completes
      await processDataset(datasetId);

      // Remove from uploading list and refresh main datasets
      setUploadingFiles(prev => prev.filter(u => u.id !== uploadId));
      fetchDatasets();

    } catch (err) {
      console.error("Background upload failed:", err);
      // Change progress to error state
      setUploadingFiles(prev => prev.map(u => u.id === uploadId ? { ...u, progress: -1 } : u));
      // Auto remove error state after 5 seconds
      setTimeout(() => {
        setUploadingFiles(prev => prev.filter(u => u.id !== uploadId));
      }, 5000);
    }
  };

  const linePositions = useMemo(() => points.map(p => [p.lat, p.lng]), [points]);
  const polygonPositions = useMemo(() => isClosed ? points.map(p => [p.lat, p.lng]) : null, [points, isClosed]);
  const step = points.length === 0 ? 'start' : !isClosed ? 'drawing' : 'complete';

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden', background: '#0a0a0a' }}>
      
      {/* Hidden File Input */}
      <input 
        type="file" 
        ref={fileInputRef} 
        style={{ display: 'none' }} 
        accept=".las,.laz" 
        onChange={handleFileUpload} 
      />

      {/* Left Sidebar - Dataset Management */}
      <div style={{ 
        width: '320px', 
        background: 'var(--bg-card)', 
        borderRight: '1px solid var(--border-light)',
        display: 'flex', 
        flexDirection: 'column',
        zIndex: 1000
      }}>
        <div style={{ padding: '24px', borderBottom: '1px solid var(--border-light)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
            <div style={{ background: 'var(--accent-gradient)', padding: '10px', borderRadius: '12px' }}>
              <Box color="white" size={24} strokeWidth={2.5} />
            </div>
            <div>
              <h1 style={{ fontSize: '1.5rem', fontWeight: '800', lineHeight: 1 }}>LiDAR Studio</h1>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', fontWeight: '500', marginTop: '4px' }}>Map Explorer</p>
            </div>
          </div>
          <button className="btn-primary" style={{ width: '100%', justifyContent: 'center' }} onClick={() => fileInputRef.current.click()}>
            <Upload size={16} /> Upload Dataset
          </button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', padding: '0 8px' }}>
            <h3 style={{ fontSize: '0.85rem', fontWeight: '700', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Workspaces</h3>
            <button onClick={fetchDatasets} className="btn-secondary" style={{ padding: '4px', minWidth: 'auto', border: 'none', background: 'transparent' }}>
              <RefreshCw size={14} className={isRefreshing ? "spin-animation" : ""} color="var(--text-dim)" />
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            
            {/* Background Uploads */}
            {uploadingFiles.map((upload) => (
              <div key={upload.id} style={{ padding: '16px', borderRadius: '12px', background: 'rgba(59, 130, 246, 0.05)', border: '1px dashed var(--accent-primary)', position: 'relative', overflow: 'hidden' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                  {upload.progress === -1 ? <AlertTriangle size={16} color="var(--error)" /> : <Loader2 size={16} className="spin-animation" color="var(--accent-primary)" />}
                  <span style={{ fontWeight: '600', fontSize: '0.9rem', color: 'var(--text-main)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {upload.name}
                  </span>
                </div>
                {upload.progress === -1 ? (
                  <div style={{ fontSize: '0.75rem', color: 'var(--error)', fontWeight: '500' }}>Upload Failed</div>
                ) : (
                  <>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: 'var(--text-dim)', marginBottom: '4px' }}>
                      <span>Uploading...</span>
                      <span>{upload.progress}%</span>
                    </div>
                    <div style={{ width: '100%', height: '4px', background: 'rgba(255,255,255,0.1)', borderRadius: '2px', overflow: 'hidden' }}>
                      <div style={{ width: `${upload.progress}%`, height: '100%', background: 'var(--accent-primary)', transition: 'width 0.2s ease' }}></div>
                    </div>
                  </>
                )}
              </div>
            ))}

            {datasets.map((ds, idx) => {
              const isActive = activeDataset?.id === ds.id;
              const color = CONTOUR_COLORS[idx % CONTOUR_COLORS.length];
              return (
                <div 
                  key={ds.id}
                  onClick={() => setActiveDataset(ds)}
                  style={{
                    padding: '16px',
                    borderRadius: '12px',
                    background: isActive ? `rgba(${parseInt(color.slice(1,3),16)},${parseInt(color.slice(3,5),16)},${parseInt(color.slice(5,7),16)},0.1)` : 'rgba(255,255,255,0.02)',
                    border: `1px solid ${isActive ? color : 'var(--border-light)'}`,
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    position: 'relative',
                    overflow: 'hidden'
                  }}
                >
                  {isActive && <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: '4px', background: color }}></div>}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                    <Database size={16} color={isActive ? color : "var(--text-dim)"} />
                    <span style={{ fontWeight: '600', fontSize: '0.9rem', color: isActive ? '#fff' : 'var(--text-main)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {ds.dataset_name}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ 
                      fontSize: '0.7rem', 
                      padding: '2px 8px', 
                      borderRadius: '10px',
                      background: ds.status === 'processed' || ds.status === 'completed' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)',
                      color: ds.status === 'processed' || ds.status === 'completed' ? '#10b981' : '#f59e0b',
                      fontWeight: '600'
                    }}>
                      {ds.status.toUpperCase()}
                    </span>
                    {!ds.geographic_bbox && (ds.status === 'processed' || ds.status === 'completed') && (
                      <span style={{ fontSize: '0.7rem', color: 'var(--error)' }}>Missing Bounds</span>
                    )}
                  </div>
                </div>
              );
            })}
            {datasets.length === 0 && uploadingFiles.length === 0 && (
              <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-dim)', fontSize: '0.85rem' }}>
                No datasets available.<br/>Upload one to begin.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Map Area */}
      <div style={{ flex: 1, position: 'relative' }}>
        <MapContainer
          center={[0, 0]}
          zoom={2}
          style={{ height: '100%', width: '100%', cursor: (!activeDataset || isClosed) ? 'grab' : 'crosshair' }}
          zoomControl={true}
          ref={setMapRef}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.carto.com/">CARTO</a>'
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          />

          {/* Render all dataset contours */}
          {datasets.filter(d => d.geographic_bbox).map((ds, idx) => {
            const color = CONTOUR_COLORS[idx % CONTOUR_COLORS.length];
            const isActive = activeDataset?.id === ds.id;
            const pathOptions = {
              color: color, 
              weight: isActive ? 3 : 1, 
              dashArray: isActive ? '' : '6, 4', 
              fillOpacity: isActive ? 0.05 : 0.01 
            };
            
            if (ds.geographic_boundary && ds.geographic_boundary.coordinates) {
              // Recursively convert GeoJSON [lon, lat] arrays to Leaflet [lat, lon] arrays
              const flipCoords = (coords) => {
                if (typeof coords[0] === 'number') {
                  return [coords[1], coords[0]];
                }
                return coords.map(flipCoords);
              };
              const positions = flipCoords(ds.geographic_boundary.coordinates);
              
              return (
                <Polygon
                  key={ds.id}
                  positions={positions}
                  pathOptions={pathOptions}
                  interactive={points.length === 0 || isClosed}
                  eventHandlers={{ click: () => setActiveDataset(ds) }}
                >
                  <Tooltip sticky direction="top">{ds.dataset_name}</Tooltip>
                </Polygon>
              );
            } else {
              const bounds = [
                [ds.geographic_bbox.min_y, ds.geographic_bbox.min_x],
                [ds.geographic_bbox.max_y, ds.geographic_bbox.max_x]
              ];
              return (
                <Rectangle
                  key={ds.id}
                  bounds={bounds}
                  pathOptions={pathOptions}
                  interactive={points.length === 0 || isClosed}
                  eventHandlers={{ click: () => setActiveDataset(ds) }}
                >
                  <Tooltip sticky direction="top">{ds.dataset_name}</Tooltip>
                </Rectangle>
              );
            }
          })}

          {/* User drawn polygon */}
          {activeDataset && (
            <>
              {polygonPositions && (
                <Polygon positions={polygonPositions} pathOptions={{ color: '#3b82f6', weight: 2, fillOpacity: 0.15, fillColor: '#3b82f6' }} />
              )}
              {!isClosed && linePositions.length >= 2 && (
                <Polyline positions={linePositions} pathOptions={{ color: '#3b82f6', weight: 2, dashArray: '6, 4' }} />
              )}
              {points.map((pt, i) => (
                <CircleMarker
                  key={i} center={pt} radius={i === 0 ? 8 : 5}
                  pathOptions={{ color: i === 0 ? '#10b981' : '#3b82f6', fillColor: i === 0 ? '#10b981' : '#3b82f6', fillOpacity: 1, weight: 2 }}
                >
                  {i === 0 && !isClosed && points.length >= 3 && (
                    <Tooltip permanent direction="top" offset={[0, -10]} className="point-tooltip">Click to close</Tooltip>
                  )}
                </CircleMarker>
              ))}
            </>
          )}

          <MapEffects dataset={activeDataset} />
          <ClickHandler onMapClick={handleMapClick} activeDataset={activeDataset} />
        </MapContainer>

        {/* Top bar indicator */}
        <div style={{ position: 'absolute', top: '20px', left: '20px', zIndex: 1000, pointerEvents: 'none' }}>
          <div className="glass-panel" style={{ padding: '10px 16px', background: 'var(--bg-card-heavy)', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Layers size={16} style={{ color: 'var(--accent-primary)' }} />
            <span style={{ fontSize: '0.8rem', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {activeDataset ? `Active: ${activeDataset.dataset_name}` : 'Select a dataset to begin extraction'}
            </span>
          </div>
        </div>

        {/* Bottom Floating Action Bar (Only shows when dataset is active) */}
        {activeDataset && (
          <div style={{
            position: 'absolute', bottom: '30px', left: '50%', transform: 'translateX(-50%)',
            background: 'var(--bg-card-heavy)', padding: '12px 24px', borderRadius: '50px',
            display: 'flex', alignItems: 'center', gap: '16px', boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
            zIndex: 1000, border: '1px solid var(--border-light)'
          }}>
            
            {/* Dataset Name & Close */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', paddingRight: '16px', borderRight: '1px solid var(--border-light)' }}>
              <Database size={16} color="var(--accent-primary)" />
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontWeight: '600', fontSize: '0.85rem', color: '#fff' }}>Extraction Active</span>
                <span style={{ fontSize: '0.65rem', color: 'var(--text-dim)' }}>Capturing all overlapping data</span>
              </div>
              <button onClick={() => setActiveDataset(null)} style={{ background: 'transparent', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', display: 'flex', marginLeft: '4px' }}>
                <X size={16} />
              </button>
            </div>

            {/* Drawing Controls */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              {!isClosed ? (
                <span style={{ fontSize: '0.85rem', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <MousePointer size={14} /> {points.length === 0 ? "Click to draw rectangle" : `${points.length} corners placed`}
                </span>
              ) : (
                <span style={{ fontSize: '0.85rem', color: '#10b981', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <CheckCircle2 size={14} /> Rectangle ready
                </span>
              )}

              {points.length > 0 && (
                <>
                  <button onClick={handleUndoLast} className="btn-secondary" style={{ padding: '6px 12px', borderRadius: '20px', fontSize: '0.8rem' }}>Undo</button>
                  <button onClick={handleResetDrawing} className="btn-secondary" style={{ padding: '6px 12px', borderRadius: '20px', fontSize: '0.8rem' }}>Clear</button>
                </>
              )}

              <button 
                className="btn-primary" 
                onClick={handleDownload} 
                disabled={!isClosed || isDownloading || activeDataset.status === 'processing'}
                style={{ padding: '8px 20px', borderRadius: '20px', marginLeft: '8px' }}
                title={activeDataset.status === 'processing' ? 'Wait for dataset processing to complete' : ''}
              >
                {isDownloading ? 'Processing...' : activeDataset.status === 'processing' ? 'Dataset Processing...' : <><Download size={16} /> Download Zone</>}
              </button>
            </div>
          </div>
        )}
      </div>

      <style>{`
        body { margin: 0; padding: 0; }
        .spin-animation { animation: spin 1s linear infinite; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
        .point-tooltip {
          background: rgba(0,0,0,0.8) !important;
          border: 1px solid rgba(255,255,255,0.1) !important;
          color: #fff !important;
          font-size: 0.7rem !important;
          font-weight: 600 !important;
          padding: 2px 8px !important;
          border-radius: 6px !important;
        }
        .leaflet-container {
          background: #111;
        }
      `}</style>
    </div>
  );
}

export default App;
