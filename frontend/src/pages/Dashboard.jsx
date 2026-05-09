import React from 'react';
import Sidebar from '../components/Sidebar';
import MapArea from '../components/MapArea';

export default function Dashboard() {
  return (
    <div className="flex h-screen w-screen bg-[#242424] text-gray-100 overflow-hidden">
      {/* Sidebar - Fix width and add subtle right border */}
      <div className="w-96 flex-shrink-0 border-r border-gray-700/50 bg-[#1e1e1e] flex flex-col h-full z-10 shadow-xl">
        <Sidebar />
      </div>
      
      {/* Main Map Area */}
      <div className="flex-1 h-full relative">
        <MapArea />
      </div>
    </div>
  );
}