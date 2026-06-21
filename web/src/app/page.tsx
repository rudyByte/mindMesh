'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useStore } from '../store/useStore';
import { LeftSidebar, RightSidebar, BottomPanel } from '../components/Panels';
import GraphCanvas from '../components/GraphCanvas';
import UploadModal from '../components/UploadModal';

export default function DashboardPage() {
  const user = useStore((state) => state.user);
  const router = useRouter();
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  useEffect(() => {
    if (!user) {
      router.push('/login');
    }
  }, [user, router]);

  if (!user) {
    return (
      <div className="min-h-screen w-full bg-[#070b13] flex items-center justify-center text-slate-500 font-semibold select-none">
        Redirecting to authorization...
      </div>
    );
  }

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-[#070b13] select-none text-slate-200">
      {/* 3-Pane workspace layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left side controller navigation */}
        <LeftSidebar onOpenUpload={() => setIsUploadOpen(true)} />
        
        {/* Interactive force layout canvas */}
        <div className="flex-1 h-full relative">
          <GraphCanvas />
        </div>
        
        {/* Right side AI reasoning HUD */}
        <RightSidebar />
      </div>

      {/* Bottom highlights and bookmarks drawer */}
      <BottomPanel />

      {/* Document ingestion Modal popover */}
      <UploadModal isOpen={isUploadOpen} onClose={() => setIsUploadOpen(false)} />
    </div>
  );
}
