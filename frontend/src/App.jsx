import React, { useState, useEffect, useCallback, useRef } from 'react';
import { MapContainer, TileLayer, useMap, Rectangle, Polygon, useMapEvents, Tooltip } from 'react-leaflet';
import L from 'leaflet';
import { getDatasets, extractZone, uploadDataset, processDataset, getToken, setToken, decodeTokenPayload } from './api';
import { Box, Upload, RefreshCw, Layers, Database, X, Download, AlertTriangle, Maximize2, Loader2 } from 'lucide-react';
import 'leaflet/dist/leaflet.css';
import Login from './components/Login';

// Colors for dataset contours
const CONTOUR_COLORS = ['#8b5cf6', '#ec4899', '#14b8a6', '#f59e0b', '#3b82f6'];

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

// Rectangle selector — drag to draw a rectangle on the map
const RectangleSelector = ({ enabled, onSelectionComplete }) => {
  const map = useMap();
  const startRef = useRef(null);
  const rectRef = useRef(null);
  const draggingRef = useRef(false);

  useEffect(() => {
    if (!enabled) {
      // Clean up any existing rectangle overlay
      if (rectRef.current) {
        map.removeLayer(rectRef.current);
        rectRef.current = null;
      }
      return;
    }

    const onMouseDown = (e) => {
      // Only trigger on left mouse button, and not on controls
      if (e.originalEvent.button !== 0) return;
      // Prevent map drag while drawing
      map.dragging.disable();
      startRef.current = e.latlng;
      draggingRef.current = false;

      if (rectRef.current) {
        map.removeLayer(rectRef.current);
        rectRef.current = null;
      }
    };

    const onMouseMove = (e) => {
      if (!startRef.current) return;
      draggingRef.current = true;

      const bounds = L.latLngBounds(startRef.current, e.latlng);

      if (rectRef.current) {
        rectRef.current.setBounds(bounds);
      } else {
        rectRef.current = L.rectangle(bounds, {
          color: '#3b82f6',
          weight: 2,
          fillOpacity: 0.15,
          fillColor: '#3b82f6',
          dashArray: '6, 4',
        }).addTo(map);
      }
    };

    const onMouseUp = (e) => {
      map.dragging.enable();
      if (!startRef.current) return;

      if (draggingRef.current) {
        const bounds = L.latLngBounds(startRef.current, e.latlng);

        // Remove the temporary drawing rectangle
        if (rectRef.current) {
          map.removeLayer(rectRef.current);
          rectRef.current = null;
        }

        // Only accept if the rectangle has meaningful size
        const sw = bounds.getSouthWest();
        const ne = bounds.getNorthEast();
        if (Math.abs(ne.lng - sw.lng) > 0.0001 && Math.abs(ne.lat - sw.lat) > 0.0001) {
          onSelectionComplete({
            minLon: sw.lng,
            minLat: sw.lat,
            maxLon: ne.lng,
            maxLat: ne.lat,
          });
        }
      }

      startRef.current = null;
      draggingRef.current = false;
    };

    map.on('mousedown', onMouseDown);
    map.on('mousemove', onMouseMove);
    map.on('mouseup', onMouseUp);

    return () => {
      map.off('mousedown', onMouseDown);
      map.off('mousemove', onMouseMove);
      map.off('mouseup', onMouseUp);
      map.dragging.enable();
      if (rectRef.current) {
        map.removeLayer(rectRef.current);
        rectRef.current = null;
      }
    };
  }, [enabled, map, onSelectionComplete]);

  return null;
};


function App() {
  const [authToken, setAuthTokenState] = useState(getToken());
  const [userRole, setUserRole] = useState(() => decodeTokenPayload(getToken())?.role || null);
  const [datasets, setDatasets] = useState([]);
  const [activeDataset, setActiveDataset] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Background Upload State
  const fileInputRef = useRef(null);
  const [uploadingFiles, setUploadingFiles] = useState([]);

  // Rectangle Selection State
  const [selectionBounds, setSelectionBounds] = useState(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState('');

  const handleLogout = useCallback(() => {
    setToken(null);
    setAuthTokenState(null);
    setUserRole(null);
    setDatasets([]);
    setActiveDataset(null);
  }, []);

  const handleLoginSuccess = useCallback((token) => {
    setToken(token);
    setAuthTokenState(token);
    setUserRole(decodeTokenPayload(token)?.role || null);
  }, []);

  const fetchDatasets = async () => {
    setIsRefreshing(true);
    try {
      const response = await getDatasets();
      setDatasets(response.data.datasets || []);
    } catch (err) {
      if (err.response?.status === 401) {
        handleLogout();
      } else {
        console.error('Failed to fetch datasets', err);
      }
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    if (!authToken) return;
    fetchDatasets();
    const interval = setInterval(fetchDatasets, 10000);
    return () => clearInterval(interval);
  }, [authToken]);

  // Reset selection when dataset is deselected
  useEffect(() => {
    if (!activeDataset) {
      setSelectionBounds(null);
      setError('');
    }
  }, [activeDataset]);

  const handleSelectionComplete = useCallback((bounds) => {
    setSelectionBounds(bounds);
    setError('');
  }, []);

  const handleClearSelection = () => {
    setSelectionBounds(null);
    setError('');
  };

  const handleDownload = async () => {
    if (!selectionBounds) return;
    setIsDownloading(true);
    setError('');
    try {
      await extractZone(
        selectionBounds.minLon,
        selectionBounds.minLat,
        selectionBounds.maxLon,
        selectionBounds.maxLat,
      );
    } catch (err) {
      console.error('Download failed', err);
      const message = err.response?.status === 404
        ? 'No data found in the selected area.'
        : 'Extraction failed. Please try again.';
      setError(message);
    } finally {
      setIsDownloading(false);
    }
  };

  const handleFileUpload = async (e) => {
    if (userRole !== 'admin') return;
    const file = e.target.files[0];
    if (!file) return;

    e.target.value = null;

    const uploadId = Math.random().toString(36).substring(7);
    const datasetName = file.name.replace(/\.[^/.]+$/, "");

    setUploadingFiles(prev => [...prev, { id: uploadId, name: datasetName, progress: 0 }]);

    try {
      const response = await uploadDataset(datasetName, file, (progressEvent) => {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        setUploadingFiles(prev => prev.map(u => u.id === uploadId ? { ...u, progress: percentCompleted } : u));
      });
      
      const datasetId = response.data.dataset_id;
      await processDataset(datasetId);

      setUploadingFiles(prev => prev.filter(u => u.id !== uploadId));
      fetchDatasets();

    } catch (err) {
      console.error("Background upload failed:", err);
      setUploadingFiles(prev => prev.map(u => u.id === uploadId ? { ...u, progress: -1 } : u));
      setTimeout(() => {
        setUploadingFiles(prev => prev.filter(u => u.id !== uploadId));
      }, 5000);
    }
  };

  const drawingEnabled = !!activeDataset && !isDownloading;

  if (!authToken) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

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
          {userRole === 'admin' ? (
            <button className="btn-primary" style={{ width: '100%', justifyContent: 'center' }} onClick={() => fileInputRef.current.click()}>
              <Upload size={16} /> Upload Dataset
            </button>
          ) : (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Read-only access: download only
            </div>
          )}
          <div style={{ marginTop: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
              Role: {userRole || 'unknown'}
            </span>
            <button className="btn-secondary" onClick={handleLogout} style={{ padding: '6px 10px' }}>
              Logout
            </button>
          </div>
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
          style={{ height: '100%', width: '100%', cursor: drawingEnabled ? 'crosshair' : 'grab' }}
          zoomControl={true}
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
                  eventHandlers={{ click: () => setActiveDataset(ds) }}
                >
                  <Tooltip sticky direction="top">{ds.dataset_name}</Tooltip>
                </Rectangle>
              );
            }
          })}

          {/* User selection rectangle */}
          {selectionBounds && (
            <Rectangle
              bounds={[
                [selectionBounds.minLat, selectionBounds.minLon],
                [selectionBounds.maxLat, selectionBounds.maxLon],
              ]}
              pathOptions={{
                color: '#3b82f6',
                weight: 2,
                fillOpacity: 0.15,
                fillColor: '#3b82f6',
              }}
            />
          )}

          <MapEffects dataset={activeDataset} />
          <RectangleSelector
            enabled={drawingEnabled}
            onSelectionComplete={handleSelectionComplete}
          />
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

        {/* Bottom Floating Action Bar */}
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
                <span style={{ fontWeight: '600', fontSize: '0.85rem', color: '#fff' }}>Zone Extraction</span>
                <span style={{ fontSize: '0.65rem', color: 'var(--text-dim)' }}>Drag a rectangle on the map</span>
              </div>
              <button onClick={() => setActiveDataset(null)} style={{ background: 'transparent', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', display: 'flex', marginLeft: '4px' }}>
                <X size={16} />
              </button>
            </div>

            {/* Selection Controls */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              {!selectionBounds ? (
                <span style={{ fontSize: '0.85rem', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Maximize2 size={14} /> Drag to select area
                </span>
              ) : (
                <span style={{ fontSize: '0.75rem', color: '#10b981', display: 'flex', alignItems: 'center', gap: '6px', fontFamily: 'monospace' }}>
                  {selectionBounds.minLat.toFixed(4)}°, {selectionBounds.minLon.toFixed(4)}° → {selectionBounds.maxLat.toFixed(4)}°, {selectionBounds.maxLon.toFixed(4)}°
                </span>
              )}

              {selectionBounds && (
                <button onClick={handleClearSelection} className="btn-secondary" style={{ padding: '6px 12px', borderRadius: '20px', fontSize: '0.8rem' }}>Clear</button>
              )}

              {error && (
                <span style={{ fontSize: '0.75rem', color: '#ef4444', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{error}</span>
              )}

              <button 
                className="btn-primary" 
                onClick={handleDownload} 
                disabled={!selectionBounds || isDownloading || activeDataset.status === 'processing'}
                style={{ padding: '8px 20px', borderRadius: '20px', marginLeft: '8px' }}
                title={activeDataset.status === 'processing' ? 'Wait for dataset processing to complete' : ''}
              >
                {isDownloading ? (
                  <><Loader2 size={16} className="spin-animation" /> Extracting...</>
                ) : activeDataset.status === 'processing' ? (
                  'Dataset Processing...'
                ) : (
                  <><Download size={16} /> Download</>
                )}
              </button>
            </div>
          </div>
        )}
      </div>

      <style>{`
        body { margin: 0; padding: 0; }
        .spin-animation { animation: spin 1s linear infinite; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
        .leaflet-container {
          background: #111;
        }
      `}</style>
    </div>
  );
}

export default App;
