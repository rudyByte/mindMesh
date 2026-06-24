'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Upload, X, FileText, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { useStore } from '../store/useStore';
import { API_BASE_URL } from '../config';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function UploadModal({ isOpen, onClose }: UploadModalProps) {
  const [dragActive, setDragActive] = useState(false);
  const [uploadState, setUploadState] = useState<'idle' | 'uploading' | 'extracting' | 'building' | 'done' | 'error'>('idle');
  const [progress, setProgress] = useState(0);
  const [errorMsg, setErrorMsg] = useState('');
  const [fileName, setFileName] = useState('');
  
  const addDocument = useStore((state) => state.addDocument);
  const updateDocumentStatus = useStore((state) => state.updateDocumentStatus);
  const setGraphData = useStore((state) => state.setGraphData);
  const setActiveDocumentId = useStore((state) => state.setActiveDocumentId);
  const setSelectedNode = useStore((state) => state.setSelectedNode);
  const sessionId = useStore((state) => state.sessionId);
  const activeDocumentId = useStore((state) => state.activeDocumentId);
  const documents = useStore((state) => state.documents);
  const removeDocument = useStore((state) => state.removeDocument);

  const [shouldReplace, setShouldReplace] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // Reset state on open if previously completed or failed
  useEffect(() => {
    if (isOpen) {
      setShouldReplace(false);
      if (uploadState === 'done' || uploadState === 'error') {
        setUploadState('idle');
        setProgress(0);
        setErrorMsg('');
        setFileName('');
      }
    }
  }, [isOpen]);

  // Clean up polling interval on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  if (!isOpen) return null;

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  const onButtonClick = () => {
    fileInputRef.current?.click();
  };

  const processFile = async (file: File) => {
    if (!file.name.endsWith('.pdf')) {
      setUploadState('error');
      setErrorMsg('Only PDF files are supported.');
      return;
    }

    setFileName(file.name);
    setUploadState('uploading');
    setProgress(10);

    const formData = new FormData();
    formData.append('file', file);

    try {
      let uploadUrl = `${API_BASE_URL}/documents/upload?session_id=${sessionId}`;
      if (shouldReplace && activeDocumentId) {
        uploadUrl += `&replace_doc_id=${activeDocumentId}`;
        removeDocument(activeDocumentId);
        setGraphData({ nodes: [], edges: [] });
        setSelectedNode(null);
      }

      const response = await fetch(uploadUrl, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed: HTTP ${response.status} ${response.statusText}`);
      }

      const uploadData = await response.json();
      const docId = uploadData.id;
      
      // Add to store
      addDocument({
        id: docId,
        title: file.name,
        status: 'processing',
        progress_pct: 10
      });

      // Start polling
      pollStatus(docId);

    } catch (err: any) {
      setUploadState('error');
      setErrorMsg(err.message || 'Server connection failed.');
    }
  };

  const pollStatus = (docId: string) => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }

    intervalRef.current = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/documents/${docId}/status?session_id=${sessionId}`);
        if (!response.ok) {
          throw new Error(`Failed to get status (HTTP ${response.status})`);
        }
        
        const data = await response.json();
        const { status, progress_pct, error } = data;
        
        setProgress(progress_pct);
        updateDocumentStatus(docId, status, progress_pct);

        if (progress_pct < 40) {
          setUploadState('uploading');
        } else if (progress_pct < 80) {
          setUploadState('extracting');
        } else if (progress_pct < 100) {
          setUploadState('building');
        }

        if (status === 'done') {
          setUploadState('done');
          setProgress(100);
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
          
          // Set active document ID now that it's successfully done!
          setActiveDocumentId(docId);
          
          // Clear frontend graph state before rendering the new graph
          setGraphData({ nodes: [], edges: [] });
          
          // Fetch and load graph
          const graphUrl = sessionId
            ? `${API_BASE_URL}/sessions/${sessionId}/graph`
            : `${API_BASE_URL}/documents/${docId}/graph`;
          const graphResponse = await fetch(graphUrl);
          if (graphResponse.ok) {
            const graphData = await graphResponse.json();
            
            let validatedNodes = graphData.nodes || [];
            let validatedEdges = graphData.edges || [];

            if (!sessionId) {
              // Validate that no nodes from previous documents exist in graphData
              validatedNodes = (graphData.nodes || []).filter((node: any) => {
                return !node.doc_id || node.doc_id === docId;
              });
              const validatedNodeIds = new Set(validatedNodes.map((n: any) => n.id));
              validatedEdges = (graphData.edges || []).filter((edge: any) => {
                const fromId = typeof edge.source === 'object' ? edge.source.id : edge.source || edge.from;
                const toId = typeof edge.target === 'object' ? edge.target.id : edge.target || edge.to;
                return validatedNodeIds.has(fromId) && validatedNodeIds.has(toId);
              });
            }

            setGraphData({
              nodes: validatedNodes,
              edges: validatedEdges
            });

            // Automatically select the central Topic node of the newly uploaded document
            const topicNode = validatedNodes.find((n: any) => n.label === 'Topic');
            if (topicNode) {
              setSelectedNode(topicNode);
            }
          }
        } else if (status === 'error') {
          setUploadState('error');
          setErrorMsg(error || 'Graph extraction failed.');
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
        }
      } catch (err: any) {
        setUploadState('error');
        setErrorMsg(err.message ? `Polling status failed: ${err.message}` : 'Polling status failed.');
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      }
    }, 2000);
  };

  const getStatusText = () => {
    switch (uploadState) {
      case 'uploading': return 'Uploading PDF...';
      case 'extracting': return 'AI Extracting Entities & Relations...';
      case 'building': return 'Deduplicating & Constructing Neo4j Graph...';
      case 'done': return 'Success! Graph Generated!';
      case 'error': return 'Error!';
      default: return 'Drag & Drop your PDF here';
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="relative w-full max-w-lg p-6 glass-panel rounded-2xl shadow-2xl border border-cyan-500/20">
        <button 
          onClick={onClose} 
          className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="mb-4">
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Upload className="w-5 h-5 text-cyan-400" />
            Ingest Document
          </h2>
          <p className="text-sm text-slate-400 mt-1 font-sans">
            Upload text-based PDF textbook chapters or papers to expand your knowledge graph.
          </p>
        </div>

        {uploadState === 'idle' && (
          <>
            <form 
              onDragEnter={handleDrag} 
              onDragOver={handleDrag} 
              onDragLeave={handleDrag} 
              onDrop={handleDrop}
              className={`flex flex-col items-center justify-center border-2 border-dashed rounded-xl p-10 transition-all cursor-pointer ${
                dragActive ? 'border-cyan-500 bg-cyan-500/10' : 'border-cyan-500/20 bg-cyan-950/5 hover:border-cyan-500/40'
              }`}
              onClick={onButtonClick}
            >
              <input 
                ref={fileInputRef}
                type="file" 
                className="hidden" 
                accept=".pdf"
                onChange={handleChange}
              />
              <Upload className="w-10 h-10 text-cyan-500/40 mb-3" />
              <p className="text-sm font-medium text-slate-300 font-sans">
                Drag and drop your PDF file here, or <span className="text-cyan-400 hover:text-cyan-300 underline font-semibold">browse</span>
              </p>
              <p className="text-xs text-slate-500 mt-1.5 font-sans">Max size 25MB · Text-based PDF only</p>
            </form>

            {activeDocumentId && (
              <div className="mt-4 p-3 bg-cyan-950/20 rounded-lg border border-cyan-500/10 flex items-center gap-3 animate-fadeIn">
                <input 
                  type="checkbox"
                  id="replace-doc-checkbox"
                  checked={shouldReplace}
                  onChange={(e) => setShouldReplace(e.target.checked)}
                  className="w-4 h-4 rounded border-cyan-500/30 bg-[#030c0b] text-cyan-500 focus:ring-cyan-500/50 cursor-pointer"
                />
                <label 
                  htmlFor="replace-doc-checkbox"
                  className="text-xs font-semibold text-slate-300 font-sans cursor-pointer select-none"
                >
                  Replace active document: <span className="text-cyan-400 font-bold">{(documents.find(d => d.id === activeDocumentId))?.title || 'current document'}</span>
                </label>
              </div>
            )}
          </>
        )}

        {uploadState !== 'idle' && (
          <div className="p-6 border border-cyan-500/10 bg-[#030c0b]/40 rounded-xl">
            <div className="flex items-center gap-3.5 mb-4">
              <div className="p-3 bg-cyan-500/10 rounded-lg text-cyan-400">
                <FileText className="w-6 h-6" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-200 truncate font-sans">{fileName}</p>
                <p className="text-xs text-slate-400 mt-0.5 font-sans">{getStatusText()}</p>
              </div>
              {uploadState === 'done' && <CheckCircle2 className="w-6 h-6 text-emerald-500 flex-shrink-0" />}
              {uploadState === 'error' && <AlertCircle className="w-6 h-6 text-rose-500 flex-shrink-0" />}
              {(uploadState !== 'done' && uploadState !== 'error') && (
                <Loader2 className="w-5 h-5 text-cyan-400 animate-spin flex-shrink-0" />
              )}
            </div>

            {uploadState !== 'error' && (
              <div className="space-y-1.5">
                <div className="w-full bg-[#030c0b] border border-cyan-500/10 rounded-full h-1.5 overflow-hidden">
                  <div 
                    className="bg-cyan-500 h-1.5 rounded-full transition-all duration-300 shadow-[0_0_8px_rgba(6,182,212,0.6)]"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-slate-500 font-mono font-bold">
                  <span>{uploadState.toUpperCase()}</span>
                  <span>{progress}%</span>
                </div>
              </div>
            )}

            {uploadState === 'error' && (
              <div className="mt-2 text-xs text-rose-400 font-semibold bg-rose-500/10 p-2.5 rounded-lg border border-rose-500/20 font-sans">
                {errorMsg}
              </div>
            )}

            <div className="mt-6 flex justify-end gap-3">
              {uploadState === 'error' && (
                <button 
                  onClick={() => setUploadState('idle')}
                  className="px-4 py-2 text-sm font-semibold rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-all cursor-pointer font-sans"
                >
                  Try Again
                </button>
              )}
              <button 
                onClick={onClose}
                className="px-4 py-2 text-sm font-semibold rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white transition-all shadow-md cursor-pointer font-sans"
              >
                Close
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
