import React, { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, FeatureGroup, useMap, Rectangle, GeoJSON } from 'react-leaflet';
import { EditControl } from 'react-leaflet-draw';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet-draw/dist/leaflet.draw.css';
import { useLidarStore } from '../store/useLidarStore';

// Auto-center map when a dataset is clicked
const MapPanner = ({ dataset }) => {
  const map = useMap();
  useEffect(() => {
    if (dataset?.geographic_bbox) {
      const { min_x, min_y, max_x, max_y } = dataset.geographic_bbox;
      // Note: L.latLngBounds takes [lat, lng], which maps to [Y, X]
      const bounds = L.latLngBounds(
        [min_y, min_x],
        [max_y, max_x]
      );
      map.flyToBounds(bounds, { padding: [50, 50], duration: 1 });
    }
  }, [map, dataset]);
  return null;
};

export default function MapArea() {
  const setBoundingBox = useLidarStore(state => state.setBoundingBox);
  const selectedDataset = useLidarStore(state => state.selectedDataset);
  
  const featureGroupRef = useRef();

  const handleCreated = (e) => {
    const { layerType, layer } = e;
    if (layerType === 'rectangle') {
      const bounds = layer.getBounds();
      // bounds: getSouthWest(), getNorthEast()
      setBoundingBox({
        south: bounds.getSouthWest().lat,
        west: bounds.getSouthWest().lng,
        north: bounds.getNorthEast().lat,
        east: bounds.getNorthEast().lng,
        // The actual leaflet polygon bounds
        rect: bounds
      });
      // Optional: enforce only one rectangle at a time by clearing previous layers
      const featureGroup = featureGroupRef.current;
      featureGroup.eachLayer((existingLayer) => {
        if (existingLayer !== layer) {
          featureGroup.removeLayer(existingLayer);
        }
      });
    }
  };

  const handleDeleted = () => {
    setBoundingBox(null);
  };

  return (
    <div className="w-full h-full relative z-0">
      <MapContainer 
        center={[0, 0]} 
        zoom={2} 
        className="w-full h-full"
        zoomControl={false}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        />
        
        {/* Draw Control Layer */}
        <FeatureGroup ref={featureGroupRef}>
          <EditControl
            position="topright"
            onCreated={handleCreated}
            onDeleted={handleDeleted}
            draw={{
              rectangle: { showArea: false },
              polyline: false,
              polygon: false,
              circle: false,
              marker: false,
              circlemarker: false,
            }}
          />
        </FeatureGroup>

        {/* Dataset Preview Rectangle or Polygon */}
        {selectedDataset?.geographic_boundary ? (
          <GeoJSON 
            key={`${selectedDataset.id}-boundary`}
            data={selectedDataset.geographic_boundary}
            style={{ color: '#3b82f6', weight: 2, fillOpacity: 0.1, dashArray: '5, 5' }}
          />
        ) : selectedDataset?.geographic_bbox ? (
          <Rectangle 
            bounds={[
              [selectedDataset.geographic_bbox.min_y, selectedDataset.geographic_bbox.min_x],
              [selectedDataset.geographic_bbox.max_y, selectedDataset.geographic_bbox.max_x]
            ]}
            pathOptions={{ color: '#3b82f6', weight: 2, fillOpacity: 0.1, dashArray: '5, 5' }}
          />
        ) : null}
        
        <MapPanner dataset={selectedDataset} />
      </MapContainer>
    </div>
  );
}