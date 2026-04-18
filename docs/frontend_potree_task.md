# Frontend Integration Architecture (Potree)

This document outlines the architecture and execution plan for integrating a web-based frontend to visualize massive point cloud datasets. The industry standard tool for this is **Potree** (based on Three.js).

## Objective
To build a web-based viewer capable of streaming and rendering tera-scale LiDAR datasets stored on a MinIO object storage backend.

## Architecture

To visualize massive datasets without freezing the browser or overloading the backend, the data must be organized in a Level of Detail (LoD) format.

#### 1. Data Contract (How Potree gets the data)
The backend pipeline will format data as **COPC (Cloud Optimized Point Cloud)** or **EPT (Entwine Point Tile)**. 
- **COPC is the modern standard**: It stores the entire LoD hierarchy within a single LAZ file. MinIO only needs to serve one object, and the Potree viewer can independently fetch chunks via **HTTP Range Requests**.

#### 2. Serving the Data (MinIO CORS Setup)
- MinIO buckets must be securely configured to allow read access to the LiDAR `.laz` or `.copc.laz` files via URLs.
- **CORS Configuration**: The MinIO bucket must have CORS headers configured so that the frontend web application (running on a different port/domain) can request data directly from MinIO without needing the FastAPI backend to act as a proxy.

## Implementation Tasks

#### [NEW] Frontend Setup
- Build a lightweight `index.html` frontend serving the Potree library and its dependencies (Three.js).
- Integrate the Potree viewer code to mount the COPC data URL dynamically based on the requested `{workspace}` and `{dataset}` IDs.

**Example Implementation Snippet:**
```javascript
// Example Potree setup for COPC streaming directly from MinIO
Potree.loadPointCloud("http://localhost:9000/processed-octree/my_workspace/my_dataset.copc.laz", "Dataset Name", function(e){
    viewer.scene.addPointCloud(e.pointcloud);
    
    // Auto-adjust camera view
    viewer.fitToScreen();
});
```

#### [MODIFY] MinIO Configuration
- Configure the `processed-octree` bucket in MinIO to accept CORS requests from the frontend domain.

## Verification
- Deploy the Potree frontend.
- Provide a test `.copc.laz` file via the MinIO URLs.
- Verify that the point cloud loads correctly in the browser without freezing, thereby proving LOD and HTTP Range requests are working as intended.
