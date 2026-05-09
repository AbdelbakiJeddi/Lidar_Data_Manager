# Frontend Overhaul Progress Report

## What Has Been Completed 

1. **Architecture & Dependency Upgrades:**
   * Installed and configured modern state and data-fetching primitives: `@tanstack/react-query`, `zustand`, `react-router-dom`, `react-dropzone`, and `tailwindcss` (alongside `postcss` and `autoprefixer`).
   * Cleaned up the nested `frontend/frontend` folder that was accidentally generated during Tailwind initialization. Removed legacy CSS files (`App.css`).

2. **Routing & Structure (`App.jsx` & `/pages`):**
   * Migrated from a single monolithic file to a multi-route architecture via React Router.
   * `Dashboard.jsx`: The root component (`/`) split into a robust Sidebar and MapArea container.
   * `PotreeViewerPage.jsx`: Designed to be opened in a separate tab (`/viewer?bbox=...`) isolating the heavy 3D rendering from the dashboard controls. 

3. **Global State (`store/useLidarStore.js`):**
   * Implemented a Zustand store to handle:
     * `selectedDataset`: Which dataset is currently clicked in the Sidebar.
     * `boundingBox`: Captures Map drawing events.
     * `zFilters`: Captures min/max elevation limits.

4. **Component Implementation (`/components`):**
   * **`Sidebar.jsx`**: Fully built out logic. Features file drag-and-drop integrated via React Dropzone. API calls (load list, upload file, process) fully rewritten to use React Query hooks. Includes a modern UI styled with Tailwind and Lucide icons.
   * **`MapArea.jsx`**: Wired up Leaflet and React-Leaflet-Draw. Strictly restricted drawing tools to **rectangles only**. It successfully pushes bounding box coordinates into the Zustand store and automatically visualizes dataset extents.

## Where I Stopped

I completed the core React restructuring and basic logic. The user can technically view the UI, connect to the dataset list (if the backend is running), draw a rectangle map bounding box, and observe the sidebar reacts.

## What is Still Left to Be Done

1. **Verify API Connection:**
   * The `api.js` points to `http://localhost:8000`. We must verify that CORS and connectivity work appropriately between Docker containers when testing inside the browser.

2. **Potree 3D Viewer Asset Installation:**
   * The `PotreeViewerPage.jsx` component exists, but the actual Potree JavaScript library and workers are not placed inside Vite's `/public` directory.
   * **Action Item:** Download the compiled Potree distribution and configure the `new Potree.Viewer` setup inside that page.

3. **Wire Bounding Box Extraction API:**
   * In `Sidebar.jsx`, the button for "Extract Subset (LAZ)" currently has a placeholder logic comment: `/* Extract Logic handled globally or in api */`. 
   * **Action Item:** Integrate the `extractZone` API call from `api.js` to download the specific LAZ cropped selection when clicked.

4. **Testing in Docker:**
   * We need to run `docker compose up --build frontend` to test the new Tailwind build process and ensure the Vite dev server maps correctly in the containerized environment.