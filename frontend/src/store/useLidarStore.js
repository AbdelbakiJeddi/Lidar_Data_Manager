import { create } from 'zustand';

export const useLidarStore = create((set) => ({
  selectedDataset: null,
  setSelectedDataset: (dataset) => set({ selectedDataset: dataset }),
  
  boundingBox: null, // format: { north, south, east, west }
  setBoundingBox: (bbox) => set({ boundingBox: bbox }),
  clearBoundingBox: () => set({ boundingBox: null }),

  zFilters: { min: null, max: null },
  setZFilters: (filters) => set((state) => ({ zFilters: { ...state.zFilters, ...filters } })),
  clearZFilters: () => set({ zFilters: { min: null, max: null } }),
}));