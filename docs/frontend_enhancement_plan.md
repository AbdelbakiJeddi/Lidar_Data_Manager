# Frontend UI/UX and Logic Enhancement Plan

This document outlines the step-by-step plan for upgrading the frontend dashboard, logic, mapping, and 3D visualization capabilities of the LiDAR Data Manager.

## Phase 1: Clean UI/UX & Upload Enhancement
*   **Tailwind CSS Setup:** Install Tailwind to provide clean, utility-based spacing and layouts without overdoing custom CSS classes. It will keep the dashboard looking professional but simple.
*   **Layout Structure:** Build a split-screen dashboard layout:
    *   **Left Sidebar:** Dataset list with search, filtering, and simple pagination.
    *   **Main Area:** Leaflet map at the top, dataset details/actions at the bottom.
*   **Drag-and-Drop Uploads:** Integrate `react-dropzone` to allow researchers to drag LAZ files into a designated simple dotted box, showing a standard inline loading spinner (no popups) while the file streams to the backend.

## Phase 2: Complete Dashboard Logic Overhaul
*   **React Query for Data Fetching:** Install `@tanstack/react-query`. Rewrite API calls to use queries and mutations to handle loading spinners, caching, and auto-refreshing the dataset list seamlessly when a new file finishes uploading.
*   **Zustand for Global State:** Install `zustand`. Create a centralized store (`useLidarStore.js`) to track:
    *   `selectedDataset` (the one the user clicked on).
    *   `boundingBox` (the bounds of the rectangle drawn on the map).
    *   `zFilters` (Min/Max elevation integers for the query).
*   **Dataset List Enhancements:** Add a search bar to filter datasets by name/date, and standard "Prev/Next" buttons to paginate if the list gets too long.

## Phase 3: Spatial Mapping (Rectangles Only)
*   **Restrict Draw Tools:** Configure `react-leaflet-draw` to exclusively allow the `Draw Rectangle` tool. Hide polygons, lines, and markers.
*   **Event Capture:** When the user draws a rectangle, extract the exact North/South/East/West coordinates and save them to the Zustand store.
*   **Dataset Previews:** When a dataset is clicked from the sidebar, draw its overarching geographical bounding box as a simple, non-editable colored rectangle on the map.

## Phase 4: 3D Visualization Integration (Potree setup)
*   **Separate Page for 3D Viewer:** Implement `react-router-dom` to handle routing.
    *   The main dashboard will live at the root path (`/`).
    *   Clicking "View in 3D" opens a new route (e.g., `/viewer/:datasetId` or `/viewer/subset`) in a new browser tab.
    *   This dedicated viewer page will take up 100% of the viewport and strictly load the Potree UI without dashboard clutter.
*   **Cropped Zone Viewing Pipeline:** Loading whole massive datasets would crash the browser. When a user selects a sub-region:
    1.  **Selection:** User draws a rectangle on the 2D Leaflet map.
    2.  **Processing:** User clicks "Extract & View 3D". The frontend sends rectangle coordinates to the FastAPI backend.
    3.  **Backend Cropping:** The backend queries MongoDB for intersecting tiles, crops them using PDAL, and saves a smaller merged temporary COPC file in MinIO.
    4.  **Viewing:** The backend returns the URL of this *new, smaller subset*. The Potree tab opens and loads **only** this cropped zone.
*   **Static Assets Setup:** Place the required Potree libraries/workers inside Vite's `public/` folder so they are accessible.
*   **Lazy Loading:** Use React's `lazy` and `Suspense` so the Potree engine is only downloaded when the user opens the 3D viewer.
