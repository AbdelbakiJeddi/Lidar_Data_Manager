import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { MapContainer, TileLayer, useMap, Rectangle, Polygon, Marker, Polyline, CircleMarker, useMapEvents, Tooltip } from 'react-leaflet';
import L from 'leaflet';
import { downloadZone } from '../api';
import { X, Download, AlertTriangle, Layers, Maximize2, Crosshair, HelpCircle, Info, RefreshCw, RotateCcw, MousePointer, CheckCircle2 } from 'lucide-react';

import 'leaflet/dist/leaflet.css';

// Custom marker icons
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

const startIcon = makeCornerIcon('#10b981', 18);
const pointIcon = makeCornerIcon('#3b82f6', 14);

// Component to handle map centering
const MapEffects = ({ dataset }) => {
  const map = useMap();
  useEffect(() => {
    const geoBbox = dataset.geographic_bbox;
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

// Click handler for placing polygon points
const ClickHandler = ({ onMapClick }) => {
  useMapEvents({ click: onMapClick });
  return null;
};

// Distance check for closing the polygon
const CLOSE_THRESHOLD_PX = 15;

const ZoneSelector = ({ dataset: initialDataset, onClose }) => {
  const [dataset, setDataset] = useState(initialDataset);
  const [points, setPoints] = useState([]); // [{lat, lng}, ...]
  const [isClosed, setIsClosed] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isLoadingMetadata, setIsLoadingMetadata] = useState(false);
  const [error, setError] = useState('');
  const [mapRef, setMapRef] = useState(null);

  const [minZ, setMinZ] = useState(dataset.bbox?.min_z?.toFixed(2) || -100);
  const [maxZ, setMaxZ] = useState(dataset.bbox?.max_z?.toFixed(2) || 100);

  // Fetch missing metadata
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

  const handleMapClick = useCallback((e) => {
    if (isClosed) return;

    // Check if clicking near the start point to close the polygon
    if (points.length >= 3 && mapRef) {
      const startPx = mapRef.latLngToContainerPoint(points[0]);
      const clickPx = mapRef.latLngToContainerPoint(e.latlng);
      const dist = startPx.distanceTo(clickPx);

      if (dist < CLOSE_THRESHOLD_PX) {
        setIsClosed(true);
        return;
      }
    }

    setPoints(prev => [...prev, e.latlng]);
  }, [isClosed, points, mapRef]);

  const handleReset = useCallback(() => {
    setPoints([]);
    setIsClosed(false);
    setError('');
  }, []);

  const handleUndoLast = useCallback(() => {
    if (isClosed) {
      setIsClosed(false);
    } else {
      setPoints(prev => prev.slice(0, -1));
    }
    setError('');
  }, [isClosed]);

  const handleDownload = async () => {
    if (!isClosed || points.length < 3) return;
    setIsDownloading(true);
    setError('');

    try {
      // Convert points to [[lon, lat], ...] format
      const coordinates = points.map(p => [p.lng, p.lat]);
      await downloadZone(dataset.id, coordinates, parseFloat(minZ), parseFloat(maxZ));
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

  // Polyline positions (for the in-progress line)
  const linePositions = useMemo(() => {
    return points.map(p => [p.lat, p.lng]);
  }, [points]);

  // Polygon positions (for completed shape)
  const polygonPositions = useMemo(() => {
    if (!isClosed) return null;
    return points.map(p => [p.lat, p.lng]);
  }, [points, isClosed]);

  const step = points.length === 0 ? 'start' : !isClosed ? 'drawing' : 'complete';

  return (
    <div className="modal-overlay">
      <div className="modal-content glass-panel" style={{ padding: 0, display: 'flex', flexDirection: 'row', height: '80vh' }}>

        {/* Left: Interactive Map */}
        <div style={{ flex: 1, position: 'relative', borderRight: '1px solid var(--border-light)' }}>
          <MapContainer
            center={[48.8566, 2.3522]}
            zoom={13}
            style={{ height: '100%', width: '100%', cursor: isClosed ? 'grab' : 'crosshair' }}
            zoomControl={false}
            ref={setMapRef}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.carto.com/">CARTO</a>'
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            />

            {/* Dataset extent */}
            {datasetBounds && (
              <Rectangle
                bounds={datasetBounds}
                pathOptions={{ color: '#8b5cf6', weight: 1.5, dashArray: '6, 4', fillOpacity: 0.04 }}
              />
            )}

            {/* Completed polygon fill */}
            {polygonPositions && (
              <Polygon
                positions={polygonPositions}
                pathOptions={{ color: '#3b82f6', weight: 2, fillOpacity: 0.15, fillColor: '#3b82f6' }}
              />
            )}

            {/* In-progress polyline */}
            {!isClosed && linePositions.length >= 2 && (
              <Polyline
                positions={linePositions}
                pathOptions={{ color: '#3b82f6', weight: 2, dashArray: '6, 4' }}
              />
            )}

            {/* Vertex markers */}
            {points.map((pt, i) => (
              <CircleMarker
                key={i}
                center={pt}
                radius={i === 0 ? 8 : 5}
                pathOptions={{
                  color: i === 0 ? '#10b981' : '#3b82f6',
                  fillColor: i === 0 ? '#10b981' : '#3b82f6',
                  fillOpacity: 1,
                  weight: 2,
                }}
              >
                {i === 0 && !isClosed && points.length >= 3 && (
                  <Tooltip permanent direction="top" offset={[0, -10]} className="point-tooltip">
                    Click to close
                  </Tooltip>
                )}
              </CircleMarker>
            ))}

            <MapEffects dataset={dataset} />
            <ClickHandler onMapClick={handleMapClick} />
          </MapContainer>

          {isLoadingMetadata && (
            <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 2000, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(4px)' }}>
              <RefreshCw className="spin-animation" size={32} color="var(--accent-primary)" />
              <p style={{ marginTop: '16px', fontWeight: '600', color: 'var(--text-main)' }}>Extracting Spatial Metadata...</p>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: '4px' }}>Analyzing dataset coordinate system</p>
            </div>
          )}

          {/* Step indicator */}
          <div style={{ position: 'absolute', bottom: '20px', left: '50%', transform: 'translateX(-50%)', zIndex: 1000 }}>
            <div className="glass-panel" style={{ padding: '10px 20px', background: 'var(--bg-card-heavy)', display: 'flex', alignItems: 'center', gap: '12px' }}>
              {step === 'start' && (
                <>
                  <MousePointer size={16} color="#10b981" />
                  <span style={{ fontSize: '0.8rem', fontWeight: '600' }}>Click to start drawing a polygon</span>
                </>
              )}
              {step === 'drawing' && (
                <>
                  <MousePointer size={16} color="#3b82f6" />
                  <span style={{ fontSize: '0.8rem', fontWeight: '600' }}>
                    {points.length} {points.length === 1 ? 'point' : 'points'} placed
                    {points.length >= 3 && <span style={{ color: '#10b981' }}> — click start point to close</span>}
                  </span>
                </>
              )}
              {step === 'complete' && (
                <>
                  <CheckCircle2 size={16} color="#10b981" />
                  <span style={{ fontSize: '0.8rem', fontWeight: '600', color: '#10b981' }}>Polygon complete ({points.length} vertices)</span>
                </>
              )}
            </div>
          </div>

          <div style={{ position: 'absolute', top: '20px', left: '20px', zIndex: 1000, pointerEvents: 'none' }}>
            <div className="glass-panel" style={{ padding: '10px 16px', background: 'var(--bg-card-heavy)', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Layers size={16} style={{ color: 'var(--accent-primary)' }} />
              <span style={{ fontSize: '0.8rem', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Polygon Selector</span>
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
              <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-light)', borderRadius: '12px', padding: '16px' }}>
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
            </div>

            {/* Polygon Vertices */}
            <div style={{ marginBottom: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Crosshair size={14} color={isClosed ? "#10b981" : "var(--text-dim)"} />
                  <span style={{ fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)' }}>
                    Vertices ({points.length})
                  </span>
                </div>
                <div style={{ display: 'flex', gap: '6px' }}>
                  {points.length > 0 && (
                    <button onClick={handleUndoLast} className="btn-secondary" style={{ padding: '4px 10px', minWidth: 'auto', fontSize: '0.7rem', borderRadius: '8px', gap: '4px' }}>
                      Undo
                    </button>
                  )}
                  {points.length > 0 && (
                    <button onClick={handleReset} className="btn-secondary" style={{ padding: '4px 10px', minWidth: 'auto', fontSize: '0.7rem', borderRadius: '8px', gap: '4px' }}>
                      <RotateCcw size={12} /> Clear
                    </button>
                  )}
                </div>
              </div>

              {points.length === 0 ? (
                <div style={{ padding: '20px', textAlign: 'center', border: '1px dashed var(--border-light)', borderRadius: '12px', color: 'var(--text-dim)', fontSize: '0.85rem' }}>
                  Click on the map to start drawing
                </div>
              ) : (
                <div style={{ maxHeight: '180px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {points.map((pt, i) => (
                    <div key={i} style={{
                      padding: '8px 12px',
                      borderRadius: '8px',
                      background: i === 0 ? 'rgba(16, 185, 129, 0.08)' : 'rgba(59, 130, 246, 0.05)',
                      border: `1px solid ${i === 0 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(59, 130, 246, 0.1)'}`,
                      display: 'flex', alignItems: 'center', gap: '10px',
                    }}>
                      <div style={{
                        width: '20px', height: '20px', borderRadius: '50%', flexShrink: 0,
                        background: i === 0 ? '#10b981' : '#3b82f6',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: '0.6rem', fontWeight: '700', color: '#fff',
                      }}>{i + 1}</div>
                      <div style={{ fontSize: '0.75rem', fontFamily: 'monospace', color: 'var(--text-main)' }}>
                        {pt.lat.toFixed(6)}, {pt.lng.toFixed(6)}
                      </div>
                    </div>
                  ))}
                  {isClosed && (
                    <div style={{ padding: '6px 12px', textAlign: 'center', fontSize: '0.7rem', color: '#10b981', fontWeight: '600' }}>
                      ✓ Polygon closed
                    </div>
                  )}
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
              disabled={!isClosed || isDownloading}
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

      <style>{`
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
          box-shadow: none !important;
        }
        .point-tooltip::before { display: none !important; }
      `}</style>
    </div>
  );
};

export default ZoneSelector;
