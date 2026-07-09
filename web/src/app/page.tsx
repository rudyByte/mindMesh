'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useStore } from '../store/useStore';
import { LeftSidebar, RightSidebar, BottomPanel } from '../components/Panels';
import GraphCanvas from '../components/GraphCanvas';
import LearningRoadmap from '../components/LearningRoadmap';
import UploadModal from '../components/UploadModal';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { ConnectionBanner } from '../components/ConnectionBanner';
import { API_BASE_URL } from '../lib/api';
import { FileText, Map as MapIcon, Sparkles, AlignLeft, AlignJustify, Layers, Compass } from 'lucide-react';

function renderFormattedText(text: string, fontSize: 'sm' | 'base' | 'lg', align: 'justify' | 'left') {
  if (!text) return null;

  const fontSizeClass = {
    sm: 'text-xs md:text-sm',
    base: 'text-sm md:text-base',
    lg: 'text-base md:text-lg'
  }[fontSize];

  const alignClass = align === 'justify' ? 'text-justify' : 'text-left';

  return (
    <div 
      className={`${fontSizeClass} ${alignClass} text-slate-300/90 font-sans select-text font-normal w-full max-w-full`} 
      style={{ 
        whiteSpace: 'pre-wrap', 
        wordBreak: 'break-word', 
        overflowWrap: 'anywhere', 
        lineHeight: 1.7 
      }}
    >
      {text}
    </div>
  );
}

export default function DashboardPage() {
  const user = useStore((state) => state.user);
  const router = useRouter();
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  // Sprint 4 states
  const activeDocumentId = useStore((state) => state.activeDocumentId);
  const documents = useStore((state) => state.documents);
  const activeTab = useStore((state) => state.activeTab);
  const setActiveTab = useStore((state) => state.setActiveTab);
  const isLearningMode = useStore((state) => state.isLearningMode);
  const documentText = useStore((state) => state.documentText);
  const setDocumentText = useStore((state) => state.setDocumentText);
  const addHighlight = useStore((state) => state.addHighlight);
  const initSessions = useStore((state) => state.initSessions);
  const sessionId = useStore((state) => state.sessionId);

  // Initialize sessions on page mount
  useEffect(() => {
    initSessions();
  }, [initSessions]);

  const [selectedText, setSelectedText] = useState('');
  const [popoverCoords, setPopoverCoords] = useState<{ x: number; y: number } | null>(null);
  const [documentTextError, setDocumentTextError] = useState<string | null>(null);

  // Reader display preferences & scroll progress state
  const [readerFontSize, setReaderFontSize] = useState<'sm' | 'base' | 'lg'>('base');
  const [readerAlign, setReaderAlign] = useState<'justify' | 'left'>('justify');
  const [scrollProgress, setScrollProgress] = useState(0);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const handleScroll = () => {
    const element = scrollContainerRef.current;
    if (!element) return;
    const totalHeight = element.scrollHeight - element.clientHeight;
    if (totalHeight <= 0) {
      setScrollProgress(0);
      return;
    }
    const progress = (element.scrollTop / totalHeight) * 100;
    setScrollProgress(progress);
  };

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
      setDocumentTextError(null);
      try {
        const response = await fetch(`${API_BASE_URL}/documents/${activeDocumentId}/text`);
        if (response.ok) {
          if (response.body) {
            setDocumentText('');
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let streamedText = '';
            
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;
              streamedText += decoder.decode(value, { stream: true });
              setDocumentText(streamedText);
            }
          } else {
            setDocumentText(await response.text());
          }
        } else {
          setDocumentTextError(`HTTP Error ${response.status}: ${response.statusText}`);
        }
      } catch (err: any) {
        console.error('Failed to load document text preview', err);
        setDocumentTextError(err.message || 'API connection failed');
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
    if (!selectedText || !activeDocumentId || !sessionId) return;

    try {
      const response = await fetch(`${API_BASE_URL}/highlights?document_id=${activeDocumentId}`, {
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
        const graphResponse = await fetch(`${API_BASE_URL}/documents/${activeDocumentId}/graph`);
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

  const graphDepth = useStore((state) => state.graphDepth);
  const setGraphDepth = useStore((state) => state.setGraphDepth);
  const graphMode = useStore((state) => state.graphMode);
  const setGraphMode = useStore((state) => state.setGraphMode);

  return (
    <>
      <ConnectionBanner />
      <div className="mission-dashboard h-screen w-screen flex flex-col overflow-hidden select-none">
      {/* 3-Pane workspace layout */}
      <div className="mission-workspace flex-1 flex overflow-hidden">
        {/* Left side controller navigation */}
        <ErrorBoundary name="Left Navigation Panel">
          <LeftSidebar onOpenUpload={() => setIsUploadOpen(true)} />
        </ErrorBoundary>
        
        {/* Center flexible canvas area */}
        <div className="mission-stage flex-1 h-full relative flex flex-col">
          {/* Unified Horizontal Toolbar HUD */}
          <div className="absolute top-4 left-4 right-4 z-20 flex justify-center pointer-events-none px-2">
            <div className="view-switcher flex items-center p-1 md:p-1.5 gap-1 md:gap-1.5 pointer-events-auto overflow-x-auto no-scrollbar max-w-full !bg-[#E8F9FD] !border-[#69D2E7]">
              
              {activeTab === 'map' && (
                <>
                  <button
                    onClick={() => setGraphMode('basic')}
                    data-active={graphMode === 'basic'}
                    className="px-2 py-1.5 text-[11px] font-bold rounded flex items-center justify-center gap-1 transition-all cursor-pointer whitespace-nowrap shrink-0"
                  >
                    <Compass className="w-3.5 h-3.5 hidden sm:block" />
                    Prerequisites
                  </button>
                  
                  <button
                    onClick={() => setGraphMode('advanced')}
                    data-active={graphMode === 'advanced'}
                    className="px-2 py-1.5 text-[11px] font-bold rounded flex items-center justify-center gap-1 transition-all cursor-pointer whitespace-nowrap shrink-0"
                  >
                    <Layers className="w-3.5 h-3.5 hidden sm:block" />
                    Related & Extends
                  </button>

                  <div className="flex items-center gap-1 mx-1 md:mx-2 border-l border-[#69D2E7] pl-1 md:pl-2 shrink-0">
                    <span className="text-[11px] font-bold text-gray-700 mr-1 whitespace-nowrap">Traversal</span>
                    {[1, 2, 3].map((depth) => (
                      <button
                        key={depth}
                        data-active={graphDepth === depth}
                        onClick={() => setGraphDepth(depth)}
                        className="w-6 h-6 md:w-7 md:h-7 text-[11px] font-bold rounded flex items-center justify-center transition-all cursor-pointer shrink-0 bg-white border border-[#69D2E7]"
                      >
                        {depth}
                      </button>
                    ))}
                  </div>
                </>
              )}

              <button
                onClick={() => setActiveTab('map')}
                data-active={activeTab === 'map'}
                className="px-3 py-1.5 text-xs font-bold rounded flex items-center justify-center gap-1.5 transition-all cursor-pointer whitespace-nowrap shrink-0 ml-1"
              >
                <MapIcon className="w-3.5 h-3.5" />
                Visual Map
              </button>
              
              {activeDocumentId && (
                <button
                  onClick={() => setActiveTab('text')}
                  data-active={activeTab === 'text'}
                  className="px-3 py-1.5 text-xs font-bold rounded flex items-center justify-center gap-1.5 transition-all cursor-pointer whitespace-nowrap shrink-0"
                >
                  <FileText className="w-3.5 h-3.5" />
                  Document Text
                </button>
              )}
            </div>
          </div>

          {/* Main Tab Render */}
          <div className="flex-1 min-h-0 relative">
            {activeTab === 'map' ? (
              <div className="w-full h-full relative">
                {/* Learning Roadmap Overlay */}
                <LearningRoadmap />
                
                {/* Graph Canvas (fades out during learning mode) */}
                <div className={`absolute inset-0 transition-opacity duration-500 ${isLearningMode ? 'opacity-0 pointer-events-none' : 'opacity-100'}`}>
                  <ErrorBoundary name="Knowledge Graph Canvas">
                    <GraphCanvas />
                  </ErrorBoundary>
                </div>
              </div>
            ) : (
              /* PDF Document Raw Text Viewer (Sprint 4) */
              <ErrorBoundary name="Document Text Reader">
                <div 
                  ref={scrollContainerRef}
                  onScroll={handleScroll}
                  className="w-full h-full py-12 px-6 md:px-12 overflow-y-auto bg-gradient-to-b from-[#020a09]/75 to-[#030d0b]/85 font-sans flex flex-col items-center border border-cyan-500/5 backdrop-blur-md relative"
                  onMouseUp={handleTextSelection}
                >
                  {/* Reading Progress Indicator */}
                  <div className="absolute top-0 left-0 w-full h-[3px] bg-cyan-500/10 z-30">
                    <div 
                      className="h-full bg-cyan-400 transition-all duration-75 shadow-[0_0_8px_rgba(6,182,212,0.8)]"
                      style={{ width: `${scrollProgress}%` }}
                    />
                  </div>

                  <div className="w-full max-w-2xl bg-[#041210]/40 p-8 md:p-12 rounded-2xl border border-cyan-500/10 shadow-[0_20px_50px_rgba(0,0,0,0.5)] select-text relative">
                    <div className="border-b border-cyan-500/10 pb-4 mb-6 select-none flex items-center justify-between gap-4">
                      <div>
                        <h2 className="text-sm font-bold text-cyan-400 flex items-center gap-2">
                          <FileText className="w-4 h-4 text-cyan-400" /> {activeDocTitle}
                        </h2>
                        <p className="text-[10px] text-slate-500 mt-1 font-medium font-sans">
                          Select text to save insights to the knowledge graph.
                        </p>
                      </div>

                      {/* Reading Preferences HUD */}
                      <div className="flex items-center gap-2 bg-[#020a09]/80 border border-cyan-500/10 p-1.5 rounded-xl shadow-lg">
                        <button
                          onClick={() => setReaderFontSize(prev => prev === 'sm' ? 'base' : prev === 'base' ? 'lg' : 'sm')}
                          className="px-2 py-1 hover:bg-cyan-950/40 text-cyan-400 hover:text-cyan-300 rounded border border-cyan-500/5 transition-all text-[9px] font-bold font-mono uppercase cursor-pointer"
                          title={`Font Size: ${readerFontSize.toUpperCase()}`}
                        >
                          {readerFontSize.toUpperCase()}
                        </button>
                        <span className="w-px h-3.5 bg-cyan-500/10" />
                        <button
                          onClick={() => setReaderAlign(prev => prev === 'justify' ? 'left' : 'justify')}
                          className="p-1 hover:bg-cyan-950/40 text-cyan-400 hover:text-cyan-300 rounded border border-cyan-500/5 transition-all cursor-pointer flex items-center justify-center"
                          title={`Alignment: ${readerAlign.toUpperCase()}`}
                        >
                          {readerAlign === 'justify' ? <AlignJustify className="w-3.5 h-3.5" /> : <AlignLeft className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                    </div>

                    {documentTextError ? (
                      <div className="text-rose-400 font-semibold block bg-rose-500/10 p-4 rounded-xl border border-rose-500/20 font-sans">
                        Error loading document text: {documentTextError}
                      </div>
                    ) : documentText ? (
                      <div className="space-y-4">
                        {renderFormattedText(documentText, readerFontSize, readerAlign)}
                      </div>
                    ) : (
                      <div className="text-sm text-slate-400 leading-relaxed font-sans animate-pulse">
                        Parsing document content...
                      </div>
                    )}

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
    </>
  );
}
