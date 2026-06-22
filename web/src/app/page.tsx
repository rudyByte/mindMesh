'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useStore } from '../store/useStore';
import { LeftSidebar, RightSidebar, BottomPanel } from '../components/Panels';
import GraphCanvas from '../components/GraphCanvas';
import UploadModal from '../components/UploadModal';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { FileText, Map as MapIcon, Sparkles } from 'lucide-react';

export default function DashboardPage() {
  const user = useStore((state) => state.user);
  const router = useRouter();
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  // Sprint 4 states
  const activeDocumentId = useStore((state) => state.activeDocumentId);
  const documents = useStore((state) => state.documents);
  const activeTab = useStore((state) => state.activeTab);
  const setActiveTab = useStore((state) => state.setActiveTab);
  const documentText = useStore((state) => state.documentText);
  const setDocumentText = useStore((state) => state.setDocumentText);
  const addHighlight = useStore((state) => state.addHighlight);

  const [selectedText, setSelectedText] = useState('');
  const [popoverCoords, setPopoverCoords] = useState<{ x: number; y: number } | null>(null);

  useEffect(() => {
    if (!user) {
      router.push('/login');
    }
  }, [user, router]);

  // Load document text when active document changes
  useEffect(() => {
    if (!activeDocumentId) {
      setDocumentText(null);
      return;
    }

    const fetchDocumentText = async () => {
      try {
        const response = await fetch(`http://localhost:8000/documents/${activeDocumentId}/text`);
        if (response.ok) {
          const data = await response.json();
          setDocumentText(data.text);
        }
      } catch (err) {
        console.error('Failed to load document text preview', err);
      }
    };

    fetchDocumentText();
  }, [activeDocumentId, setDocumentText]);

  // Handle text selection in Document Text viewer
  const handleTextSelection = (e: React.MouseEvent) => {
    const selection = window.getSelection();
    if (!selection) return;
    const text = selection.toString().trim();

    if (text.length > 5) {
      setSelectedText(text);
      // Place the popover near the selection cursor
      setPopoverCoords({
        x: e.clientX,
        y: e.clientY - 45,
      });
    } else {
      setSelectedText('');
      setPopoverCoords(null);
    }
  };

  const handleSaveHighlight = async () => {
    if (!selectedText || !activeDocumentId) return;

    try {
      const response = await fetch('http://localhost:8000/highlights', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          text: selectedText,
          page: 1,
          source_document_id: activeDocumentId,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        
        // Add to Zustand store
        const docTitle = documents.find(d => d.id === activeDocumentId)?.title || 'Document.pdf';
        addHighlight({
          id: data.id,
          text: data.text,
          page: data.page,
          doc_title: docTitle
        });

        // Clear highlight popover and selection
        window.getSelection()?.removeAllRanges();
        setSelectedText('');
        setPopoverCoords(null);

        // Fetch and load updated document graph elements to canvas
        const graphResponse = await fetch(`http://localhost:8000/documents/${activeDocumentId}/graph`);
        if (graphResponse.ok) {
          const graphData = await graphResponse.json();
          useStore.getState().appendGraphData(graphData);
        }
      }
    } catch (err) {
      console.error('Failed to save highlight insight', err);
    }
  };

  if (!user) {
    return (
      <div className="min-h-screen w-full bg-[#070b13] flex items-center justify-center text-slate-500 font-semibold select-none">
        Redirecting to authorization...
      </div>
    );
  }

  const activeDocTitle = documents.find(d => d.id === activeDocumentId)?.title || 'Document';

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-[#030c0b]/20 backdrop-blur-sm select-none text-slate-200">
      {/* 3-Pane workspace layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left side controller navigation */}
        <ErrorBoundary name="Left Navigation Panel">
          <LeftSidebar onOpenUpload={() => setIsUploadOpen(true)} />
        </ErrorBoundary>
        
        {/* Center flexible canvas area */}
        <div className="flex-1 h-full relative flex flex-col">
          {/* Header Tab ToggleHUD */}
          {activeDocumentId && (
            <div className="absolute top-4 right-4 z-20 flex items-center gap-1 bg-[#031412]/80 backdrop-blur-lg border border-cyan-500/10 p-1 rounded-xl shadow-[0_0_15px_rgba(6,182,212,0.06)]">
              <button
                onClick={() => setActiveTab('map')}
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-all cursor-pointer ${
                  activeTab === 'map' 
                    ? 'bg-cyan-600/80 border border-cyan-400/30 text-white shadow-[0_0_10px_rgba(6,182,212,0.2)]' 
                    : 'text-cyan-400/60 hover:text-cyan-200 hover:bg-cyan-950/20'
                }`}
              >
                <MapIcon className="w-3.5 h-3.5" />
                Visual Map
              </button>
              <button
                onClick={() => setActiveTab('text')}
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-all cursor-pointer ${
                  activeTab === 'text' 
                    ? 'bg-cyan-600/80 border border-cyan-400/30 text-white shadow-[0_0_10px_rgba(6,182,212,0.2)]' 
                    : 'text-cyan-400/60 hover:text-cyan-200 hover:bg-cyan-950/20'
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                Document Text
              </button>
            </div>
          )}

          {/* Main Tab Render */}
          <div className="flex-1 min-h-0 relative">
            {activeTab === 'map' ? (
              <ErrorBoundary name="Knowledge Graph Canvas">
                <GraphCanvas />
              </ErrorBoundary>
            ) : (
              /* PDF Document Raw Text Viewer (Sprint 4) */
              <ErrorBoundary name="Document Text Reader">
                <div 
                  className="w-full h-full p-8 overflow-y-auto bg-[#030c0b]/55 font-sans flex flex-col items-center border border-cyan-500/5 backdrop-blur-md"
                  onMouseUp={handleTextSelection}
                >
                  <div className="w-full max-w-2xl space-y-6 select-text text-justify relative">
                    <div className="border-b border-cyan-500/10 pb-4 mb-4 select-none">
                      <h2 className="text-sm font-bold text-cyan-400 flex items-center gap-2">
                        <FileText className="w-4 h-4 text-cyan-400" /> {activeDocTitle}
                      </h2>
                      <p className="text-[10px] text-slate-500 mt-1 font-medium font-sans">
                        Select any text block to save key insights as graph highlights.
                      </p>
                    </div>

                    <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap font-medium font-sans">
                      {documentText || "Parsing document content..."}
                    </p>

                    {/* Selection Highlight Popover Insight Button */}
                    {popoverCoords && (
                      <button
                        onClick={handleSaveHighlight}
                        style={{
                          position: 'fixed',
                          left: `${popoverCoords.x}px`,
                          top: `${popoverCoords.y}px`,
                          transform: 'translateX(-50%)',
                        }}
                        className="z-30 px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 active:bg-cyan-700 text-white text-[10px] font-bold rounded-lg shadow-xl hover:scale-105 transition-all duration-150 flex items-center gap-1 border border-cyan-400/20 select-none animate-bounce cursor-pointer"
                      >
                        <Sparkles className="w-3.5 h-3.5" /> Save as Insight
                      </button>
                    )}
                  </div>
                </div>
              </ErrorBoundary>
            )}
          </div>
        </div>
        
        {/* Right side AI reasoning HUD */}
        <ErrorBoundary name="AI Assistant Panel">
          <RightSidebar />
        </ErrorBoundary>
      </div>

      {/* Bottom highlights and bookmarks drawer */}
      <ErrorBoundary name="Insights Feed Drawer">
        <BottomPanel />
      </ErrorBoundary>

      {/* Document ingestion Modal popover */}
      <UploadModal isOpen={isUploadOpen} onClose={() => setIsUploadOpen(false)} />
    </div>
  );
}
