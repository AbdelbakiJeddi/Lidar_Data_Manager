import React, { useEffect, useRef, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { ArrowLeft, Loader2, AlertTriangle, Maximize } from 'lucide-react';

const POTREE_BASE = '/potree/Potree_1.8.2';



export default function PotreeViewerPage() {
  const [searchParams] = useSearchParams();
  const bbox = searchParams.get('bbox');
  const urlsParam = searchParams.get('urls');
  const copcUrls = urlsParam ? JSON.parse(decodeURIComponent(urlsParam)) : [];

  const containerRef = useRef(null);
  const viewerRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function initPotree() {
      try {
        if (!window.Potree) {
          throw new Error('Potree library is missing from the global window. Make sure it is loaded in index.html');
        }

        if (cancelled) return;

        // 3. Set script and resource paths (absolute URLs for proper URL construction)
        window.Potree.scriptPath = window.location.origin + '/potree/Potree_1.8.2/build/potree';
        window.Potree.resourcePath = window.location.origin + '/potree/Potree_1.8.2/build/potree/resources';

        // 4. Create viewer
        const viewer = new window.Potree.Viewer(containerRef.current);
        viewerRef.current = viewer;

        viewer.setEDLEnabled(true);
        viewer.setFOV(60);
        viewer.setPointBudget(2_000_000);
        viewer.setBackground('gradient');
        viewer.loadSettingsFromURL();

        console.log('[Potree] Viewer created, scene:', viewer.scene);
        console.log('[Potree] Camera:', viewer.camera);

        // Hide the default Potree sidebar/nav if generated
        const potreeSidebar = containerRef.current.querySelector('#potree_sidebar_container');
        if (potreeSidebar) potreeSidebar.style.display = 'none';

        // 5. Load point clouds from URLs
        console.log('[Potree] Loading URLs:', copcUrls);
        if (copcUrls && copcUrls.length > 0) {
          for (let i = 0; i < copcUrls.length; i++) {
            if (cancelled) break;
            const url = copcUrls[i];
            console.log('[Potree] Loading URL:', url);
            try {
              const result = await window.Potree.loadPointCloud(url, `pointcloud_${i}`);
              console.log('[Potree] Loaded result:', result);
              if (cancelled) return;

              const pointcloud = result.pointcloud;
              console.log('[Potree] Pointcloud:', pointcloud);
              viewer.scene.addPointCloud(pointcloud);

              // Material settings
              const material = pointcloud.material;
              material.size = 1;
              material.pointSizeType = window.Potree.PointSizeType.ADAPTIVE;
              material.activeAttributeName = 'elevation';
              material.elevationScale = 1;
              material.shape = window.Potree.PointShape.CIRCLE;
            } catch (loadError) {
              console.error(`[Potree] Could not load point cloud ${i}:`, loadError);
            }
          }
          viewer.fitToScreen();
        } else {
          console.log('[Potree] No URLs to load');
        }

        setLoading(false);
      } catch (err) {
        console.error('Potree initialization failed:', err);
        if (!cancelled) {
          setError(err.message);
          setLoading(false);
        }
      }
    }

    initPotree();

    return () => {
      cancelled = true;
      if (viewerRef.current) {
        try {
          viewerRef.current.renderer?.dispose();
        } catch (e) {
          /* ignore */
        }
      }
    };
  }, [copcUrls]);

  return (
    <div className="w-screen h-screen bg-black overflow-hidden flex flex-col relative">
      {/* Top Bar */}
      <div className="absolute top-0 left-0 right-0 z-50 flex items-center justify-between px-4 py-2 bg-black/70 backdrop-blur-sm border-b border-gray-800">
        <div className="flex items-center gap-3">
          <Link
            to="/"
            className="flex items-center gap-1.5 text-gray-400 hover:text-white text-sm transition-colors"
          >
            <ArrowLeft size={16} />
            <span>Dashboard</span>
          </Link>
          <div className="w-px h-5 bg-gray-700" />
          <h1 className="text-white text-sm font-semibold flex items-center gap-2">
            <Maximize size={14} className="text-blue-400" />
            3D Point Cloud Viewer
          </h1>
        </div>
        {bbox && (
          <span className="text-xs font-mono text-gray-500">
            bbox: {bbox}
          </span>
        )}
      </div>

      {/* Loading Overlay */}
      {loading && (
        <div className="absolute inset-0 z-40 flex items-center justify-center bg-black/90">
          <div className="text-center space-y-4">
            <Loader2 size={40} className="animate-spin text-blue-500 mx-auto" />
            <p className="text-gray-300 text-sm">Loading 3D viewer...</p>
            <p className="text-gray-600 text-xs">Initializing Potree engine</p>
          </div>
        </div>
      )}

      {/* Error Overlay */}
      {error && (
        <div className="absolute inset-0 z-40 flex items-center justify-center bg-black/90">
          <div className="text-center space-y-4 max-w-md p-6 bg-gray-900 border border-gray-800 rounded-xl">
            <AlertTriangle size={40} className="text-red-400 mx-auto" />
            <h2 className="text-white font-semibold">Viewer Error</h2>
            <p className="text-gray-400 text-sm">{error}</p>
            <p className="text-gray-600 text-xs">
              Make sure the Potree library files are correctly placed in the{' '}
              <code className="bg-gray-800 px-1 rounded">/public/potree/</code> directory.
            </p>
            <Link
              to="/"
              className="inline-flex items-center gap-2 text-blue-400 hover:text-blue-300 text-sm transition-colors"
            >
              <ArrowLeft size={14} /> Return to Dashboard
            </Link>
          </div>
        </div>
      )}

      {/* Potree Render Container — Potree takes over this div */}
      <div
        ref={containerRef}
        id="potree_render_area"
        className="w-full h-full"
        style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}
      />
    </div>
  );
}