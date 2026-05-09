# LiDAR Data Manager: Comprehensive Project Summary

The **LiDAR Data Manager** is a sophisticated spatial data platform designed to manage, process, and analyze LiDAR point clouds. The system addresses the full lifecycle of LiDAR datasets—from raw data ingestion to 3D visualization and localized geographic extraction.

---

## 1. Platform Purpose & Value Proposition
The system enables researchers to efficiently manage massive point cloud datasets (LAS/LAZ formats). Rather than handling single massive files, the platform logically chunks and structures the data geographically. It is designed around **Spatial Intelligence**, offering capabilities like on-the-fly coordinate reprojection, spatial queries, auto-detection of Coordinate Reference Systems (CRS/SRS), and automated bounding-box footprint extraction.

---

## 2. Overall Workflow

The data lifecycle within the project is broadly divided into two main phases: **Ingestion/Processing** and **Query/Export**.

### Phase 1: Ingestion & Processing
1. **Upload**: Users stream raw LAZ/LAS files via the frontend. The FastApi backend uploads the raw files directly to a MinIO storage bucket (`lidar-raw`). Memory is preserved by utilizing stream uploads (`length=-1`).
2. **Metadata Extraction:** The system uses `PDAL` (Point Data Abstraction Library) to read the dataset and automatically calculate geographic footprints and CRS configurations.
3. **Tiling & Sub-division**: Background processes step in to chunk the massive point clouds into a flat 2D tile grid (or octree subdivisions). Native PDAL is used to convert chunks into **COPC** (Cloud Optimized Point Cloud) format for optimal streaming.
4. **Storage & Indexing**: The processed tiles are stored in a separate MinIO bucket (`lidar-processed`). Concurrently, the geographic bounding boxes and metadata for these tiles are recorded in MongoDB, utilizing interval-overlap indices for highly efficient spatial lookups.

### Phase 2: Querying & Visualization
1. **Boundary Selection:** On the frontend, users view the overall geographic footprint of the dataset on a 2D map and draw custom polygons/bounding boxes for their Area of Interest (AOI).
2. **Geospatial Resolution:** If the selected region's map coordinates do not match the source files, backend integration with `pyproj` handles automatic reprojection at the boundaries to retrieve an accurate geospatial match.
3. **Tile Extraction & Merge:** The backend queries MongoDB to rapidly identify all COPC tiles intersecting the user's custom bounding box. 
4. **Export & View:** The identified data is retrieved via temporary presigned MinIO URLs. It is either merged, cropped, and streamed as a custom LAZ file download back to the user, or loaded into the web viewer for interactive visualization.

---

## 3. Architecture & Tech Stack

The architecture is built on a microservices-aligned dockerized environment, promoting separation of concerns:

*   **Backend Gateway (FastAPI):** Python-based REST API managing routing, coordinate manipulation (`pyproj`), endpoints (`/lidar/*`), dependency injection, and background task orchestrations. 
*   **Geospatial Processor (PDAL / LAStools):** Acts as the heavy-lifting engine for bounding box calculations, COPC conversion, tiling, and data cropping. Uses `pdal info` for intelligent metadata extraction.
*   **Application State & Metadata (MongoDB via Motor):** Asynchronous document storage tracking datasets (file metadata) and tile spatial indices (tile grid/octree geometry).
*   **Blob Storage (MinIO S3):** Object storage segregating `lidar-raw` and `lidar-processed` files. 
*   **Frontend UI (Vite + React):** Responsible for the map-based interactions and dashboard controls.

---

## 4. Frontend Capabilities

The frontend delivers a premium, glassmorphism-styled web interface focused on seamless geographic manipulation:

*   **Interactive Zone Selector & 2D Mapping:** A split-pane Leaflet (CartoDB dark mode) map where users view dataset footprints overlaid on real-world map tiles.
*   **Free-Form Polygon Selection:** Users can click to place vertices on the map to extract custom, non-rectangular zones (connecting the final point closes the polygon). 
*   **Real-Time Data Feedback:** A sidebar instantly displays bounding box bounds, current selection coordinates, and allows the configuration of specific elevation minimum/maximum (Z-axis) filters.
*   **SRS Override & Correction:** A built-in graphical tool allows users to manually specify an EPSG projection code when a file lacks its internal metadata.
*   **Potree 3D Visualization:** Ongoing integration allows the targeted node selection to render dynamically in a web-based Potree 3D canvas right inside the application via COPC endpoints.

---

## 5. Current Project Status & Roadmap

**Status:** The Minimum Viable Product (MVP) core architecture is complete.
*   **Completed:** Multi-file streaming uploads, MongoDB/MinIO lifecycle, 2D flat tiling, automated metadata mapping, coordinate reprojection, rectangular/polygon selections.
*   **Actively Evolving:** The internal processing engine has been actively migrated towards native PDAL implementations (moving away from an older LAStools over Wine iteration) for better Linux efficiency and modern COPC support.
*   **Future Roadmap:** True chunked/streaming downloads for massive subset exports, deeper integration of the Potree visualization pipeline directly into the unified interface UI pane, and implementing authentication/rate-limiting for production readiness.