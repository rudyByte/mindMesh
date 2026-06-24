'use client';

import React, { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { useStore, GraphNode, GraphEdge } from '../store/useStore';
import { API_BASE_URL } from '../lib/api';
import { Layers, Compass, Loader2 } from 'lucide-react';
import { forceCollide } from 'd3-force';

// Dynamically import force graph to prevent SSR errors in Next.js
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full relative overflow-hidden bg-[#030712] flex flex-col items-center justify-center text-slate-500 select-none">
      {/* Premium pulsing mesh background */}
      <div className="absolute inset-0 grid grid-cols-12 grid-rows-12 gap-1 opacity-[0.03]">
        {Array.from({ length: 144 }).map((_, i) => (
          <div key={i} className="border border-slate-500 rounded-sm w-full h-full" />
        ))}
      </div>
      
      {/* Floating pulsing nodes simulation */}
      <div className="absolute inset-0 flex items-center justify-center opacity-10">
        <div className="relative w-[300px] h-[300px] animate-pulse">
          <div className="absolute top-[20%] left-[30%] w-6 h-6 rounded-full bg-indigo-500" />
          <div className="absolute top-[50%] left-[60%] w-8 h-8 rounded-full bg-purple-500" />
          <div className="absolute top-[70%] left-[20%] w-5 h-5 rounded-full bg-emerald-500" />
          <div className="absolute top-[40%] left-[10%] w-7 h-7 rounded-full bg-amber-500" />
          {/* Simple connections */}
          <svg className="absolute inset-0 w-full h-full stroke-slate-500 stroke-[0.5] fill-none">
            <line x1="30%" y1="20%" x2="60%" y2="50%" />
            <line x1="60%" y1="50%" x2="20%" y2="70%" />
            <line x1="20%" y1="70%" x2="10%" y2="40%" />
            <line x1="10%" y1="40%" x2="30%" y2="20%" />
          </svg>
        </div>
      </div>

      <div className="relative z-10 flex flex-col items-center gap-3">
        <Loader2 className="w-6 h-6 animate-spin text-indigo-500" />
        <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Initializing Space Map...</span>
      </div>
    </div>
  ),
});

class GraphErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean }> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: any) {
    return { hasError: true };
  }

  componentDidCatch(error: any, errorInfo: any) {
    console.error("ForceGraph2D crashed:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="w-full h-full flex flex-col items-center justify-center text-cyan-500/60 bg-[#030c0b] p-6 text-center gap-3">
          <Layers className="w-12 h-12 text-rose-500/40 animate-pulse" />
          <h3 className="text-sm font-bold text-rose-400">Visualization Engine Error</h3>
          <p className="text-xs max-w-md text-slate-400">
            The layout simulation failed to load or encountered invalid coordinate geometry. Please refresh or ingest a new document.
          </p>
          <button 
            onClick={() => this.setState({ hasError: false })}
            className="mt-2 px-3 py-1.5 text-xs font-semibold rounded-lg bg-cyan-950/40 border border-cyan-500/30 text-cyan-400 hover:bg-cyan-950/80 transition-all cursor-pointer animate-pulse"
          >
            Reset Visualization
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default function GraphCanvas() {
  const containerRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<any>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [loading, setLoading] = useState(false);
  const [canvasError, setCanvasError] = useState<string | null>(null);

  // Store state
  const nodes = useStore((state) => state.nodes);
  const edges = useStore((state) => state.edges);
  const selectedNode = useStore((state) => state.selectedNode);
  const setSelectedNode = useStore((state) => state.setSelectedNode);
  const graphDepth = useStore((state) => state.graphDepth);
  const setGraphDepth = useStore((state) => state.setGraphDepth);
  const graphMode = useStore((state) => state.graphMode);
  const setGraphMode = useStore((state) => state.setGraphMode);
  const setGraphData = useStore((state) => state.setGraphData);
  const appendGraphData = useStore((state) => state.appendGraphData);
  const activePathNodeIds = useStore((state) => state.activePathNodeIds);
  const documents = useStore((state) => state.documents);
  const activeDocumentId = useStore((state) => state.activeDocumentId);
  const graphFilter = useStore((state) => state.graphFilter);
  const sessionId = useStore((state) => state.sessionId);

  const shouldZoomToFit = useRef(false);

  const safeNodes = Array.isArray(nodes) ? nodes : [];
  const safeEdges = Array.isArray(edges) ? edges : [];

  const filteredNodes = React.useMemo(() => {
    if (!graphFilter) return safeNodes;
    if (graphFilter === 'Concept') {
      return safeNodes.filter(n => n && (n.label === 'Concept' || n.label === 'Topic'));
    }
    if (graphFilter === 'Learning Path') {
      const pathSet = new Set(activePathNodeIds || []);
      return safeNodes.filter(n => n && pathSet.has(n.id));
    }
    return safeNodes.filter(n => n && n.label === graphFilter);
  }, [safeNodes, graphFilter, activePathNodeIds]);

  const filteredEdges = React.useMemo(() => {
    const nodeIds = new Set(filteredNodes.map(n => n.id));
    return safeEdges.filter(e => {
      if (!e) return false;
      const fromId = typeof e.source === 'object' && e.source !== null ? (e.source as any).id : e.source || e.from;
      const toId = typeof e.target === 'object' && e.target !== null ? (e.target as any).id : e.target || e.to;
      return nodeIds.has(fromId) && nodeIds.has(toId);
    });
  }, [safeEdges, filteredNodes]);

  const validatedGraphData = React.useMemo(() => {
    // 1. Validate and clean nodes
    const validNodes = filteredNodes.filter(n => {
      if (!n) return false;
      if (typeof n.id !== 'string' || !n.id.trim()) return false;
      if (typeof n.label !== 'string' || !n.label.trim()) return false;
      return true;
    }).map(n => ({
      ...n,
      name: n.name || (n as any).title || 'Unknown Node',
      description: n.description || '',
      difficulty_level: n.difficulty_level || 'Beginner',
      x: typeof (n as any).x === 'number' && !isNaN((n as any).x) ? (n as any).x : undefined,
      y: typeof (n as any).y === 'number' && !isNaN((n as any).y) ? (n as any).y : undefined,
    }));

    const validNodeIds = new Set(validNodes.map(n => n.id));

    // 2. Validate and clean edges/links
    const validLinks = filteredEdges.filter(e => {
      if (!e) return false;
      const fromId = typeof e.source === 'object' && e.source !== null ? (e.source as any).id : e.source || e.from;
      const toId = typeof e.target === 'object' && e.target !== null ? (e.target as any).id : e.target || e.to;
      
      if (typeof fromId !== 'string' || !fromId.trim()) return false;
      if (typeof toId !== 'string' || !toId.trim()) return false;
      
      // Ensure both nodes exist in our validNodes list to prevent canvas crash
      return validNodeIds.has(fromId) && validNodeIds.has(toId);
    }).map(e => {
      const fromId = typeof e.source === 'object' && e.source !== null ? (e.source as any).id : e.source || e.from;
      const toId = typeof e.target === 'object' && e.target !== null ? (e.target as any).id : e.target || e.to;
      return {
        source: fromId,
        target: toId,
        type: e.type || 'RELATED_TO'
      };
    });

    return { nodes: validNodes, links: validLinks };
  }, [filteredNodes, filteredEdges]);

  // Set zoom to fit flag when nodes are loaded or active document changes
  useEffect(() => {
    if (safeNodes.length > 0) {
      shouldZoomToFit.current = true;
    }
  }, [nodes, activeDocumentId, safeNodes.length]);

  // Focus/zoom camera when selectedNode changes
  useEffect(() => {
    if (!selectedNode || !fgRef.current) return;
    
    try {
      const fg = fgRef.current;
      if (typeof fg.graphData !== 'function') return;
      
      const graphData = fg.graphData();
      if (!graphData || !Array.isArray(graphData.nodes)) return;
      
      const node = graphData.nodes.find((n: any) => n && n.id === selectedNode.id);
      
      if (node) {
        const x = typeof node.x === 'number' && !isNaN(node.x) ? node.x : 0;
        const y = typeof node.y === 'number' && !isNaN(node.y) ? node.y : 0;
        if (typeof fg.centerAt === 'function') {
          fg.centerAt(x, y, 800);
        }
        if (typeof fg.zoom === 'function') {
          fg.zoom(2.5, 800);
        }
      }
    } catch (err) {
      console.error('Failed to focus/zoom camera to selected node:', err);
    }
  }, [selectedNode]);

  // Track dimensions
  useEffect(() => {
    if (!containerRef.current) return;
    const updateDimensions = () => {
      const w = containerRef.current?.clientWidth;
      const h = containerRef.current?.clientHeight;
      setDimensions({
        width: typeof w === 'number' && !isNaN(w) && w > 0 ? w : 800,
        height: typeof h === 'number' && !isNaN(h) && h > 0 ? h : 600,
      });
    };
    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  // Fetch session graph when sessionId changes if not already loaded
  useEffect(() => {
    const fetchSessionGraph = async () => {
      if (!sessionId) return;
      if (nodes.length > 0) return; // Skip if already loaded by store
      setLoading(true);
      setCanvasError(null);
      try {
        const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/graph`);
        if (response.ok) {
          const data = await response.json();
          setGraphData(data);
        } else {
          setCanvasError(`HTTP Error ${response.status}: ${response.statusText}`);
        }
      } catch (err: any) {
        console.error('Failed to load session graph', err);
        setCanvasError(err.message || 'API connection failed');
      } finally {
        setLoading(false);
      }
    };

    fetchSessionGraph();
  }, [sessionId, setGraphData, nodes.length]);

  const nodeDegrees = React.useMemo(() => {
    const degrees: Record<string, number> = {};
    validatedGraphData.nodes.forEach(n => {
      degrees[n.id] = 0;
    });
    validatedGraphData.links.forEach(e => {
      const fromId = typeof e.source === 'object' && e.source !== null ? (e.source as any).id : e.source;
      const toId = typeof e.target === 'object' && e.target !== null ? (e.target as any).id : e.target;
      if (fromId && degrees[fromId] !== undefined) degrees[fromId]++;
      if (toId && degrees[toId] !== undefined) degrees[toId]++;
    });
    return degrees;
  }, [validatedGraphData]);

  // Configure forces inside the force-directed simulation safely
  useEffect(() => {
    if (fgRef.current) {
      try {
        const fg = fgRef.current;
        
        // Safely set many-body charge repulsion force if it exists
        const chargeForce = fg.d3Force('charge');
        if (chargeForce && typeof chargeForce.strength === 'function') {
          chargeForce.strength(-400);
        }
        
        // Safely set link distance force if it exists
        const linkForce = fg.d3Force('link');
        if (linkForce && typeof linkForce.distance === 'function') {
          linkForce.distance(150);
        }
        
        // Add safe collision detection force
        const collideForce = forceCollide((node: any) => {
          try {
            const rawDegree = (nodeDegrees && node && node.id) ? (nodeDegrees[node.id] || 0) : 0;
            const degree = typeof rawDegree === 'number' && !isNaN(rawDegree) && rawDegree >= 0 ? rawDegree : 0;
            const radius = 3 + Math.sqrt(degree) * 1.5;
            return radius + 75;
          } catch (e) {
            return 80;
          }
        });
        
        if (collideForce && typeof collideForce.iterations === 'function') {
          fg.d3Force('collide', collideForce.iterations(3));
        }
        
        // Reheat the simulation safely
        if (typeof fg.d3ReheatSimulation === 'function') {
          fg.d3ReheatSimulation();
        }
      } catch (err) {
        console.error('Error configuring D3 forces:', err);
      }
    }
  }, [filteredNodes, nodeDegrees]);

  // Helper to detect if a link is part of the learning path
  const isPathLink = (link: any) => {
    try {
      if (!activePathNodeIds || !Array.isArray(activePathNodeIds) || activePathNodeIds.length < 2 || !link) return false;
      const sourceId = typeof link.source === 'object' && link.source !== null ? link.source.id : link.source;
      const targetId = typeof link.target === 'object' && link.target !== null ? link.target.id : link.target;
      if (!sourceId || !targetId) return false;
      const sIdx = activePathNodeIds.indexOf(sourceId);
      const tIdx = activePathNodeIds.indexOf(targetId);
      return sIdx !== -1 && tIdx !== -1 && tIdx === sIdx + 1;
    } catch (e) {
      return false;
    }
  };

  // Color mapping based on label
  const getNodeColor = (label: string) => {
    switch (label) {
      case 'Concept': return '#06b6d4'; // Neon Cyan
      case 'Paper': return '#8b5cf6';   // Soft Violet
      case 'Author': return '#d946ef';  // Vibrant Magenta/Violet
      case 'Topic': return '#f59e0b';   // Warm Amber
      case 'Keyword': return '#14b8a6'; // Vibrant Teal
      default: return '#06b6d4';
    }
  };

  const handleNodeClick = async (node: any) => {
    if (!node || !node.id) return;
    const clickedNode: GraphNode = {
      id: node.id,
      label: node.label,
      name: node.name || node.title || 'Unknown',
      description: node.description || '',
      difficulty_level: node.difficulty_level || 'Beginner',
      ...node
    };
    setSelectedNode(clickedNode);
    setLoading(true);
    // Do not clear canvas error here to keep the current graph visible

    try {
      // Fetch full details of the clicked node
      const detailsUrl = sessionId
        ? `${API_BASE_URL}/graph/node/${node.id}?session_id=${sessionId}`
        : `${API_BASE_URL}/graph/node/${node.id}?document_id=${activeDocumentId || 'doc-1'}`;
      const detailsRes = await fetch(detailsUrl);
      if (detailsRes.ok) {
        const detailsData = await detailsRes.json();
        setSelectedNode(detailsData);
      } else {
        console.error(`Failed to load node details (HTTP ${detailsRes.status})`);
      }

      // Fetch dynamic node expansion
      const url = sessionId
        ? `${API_BASE_URL}/graph/expand?node_id=${node.id}&depth=${graphDepth}&mode=${graphMode}&session_id=${sessionId}`
        : `${API_BASE_URL}/graph/expand?node_id=${node.id}&depth=${graphDepth}&mode=${graphMode}&document_id=${activeDocumentId || 'doc-1'}`;
      const response = await fetch(url);
      if (response.ok) {
        const expandedData = await response.json();
        appendGraphData(expandedData);
      } else {
        console.error(`Failed to expand node (HTTP ${response.status})`);
      }
    } catch (err: any) {
      console.error('Failed to expand/retrieve node details', err);
    } finally {
      setLoading(false);
    }
  };

  const graphWidth = typeof dimensions.width === 'number' && !isNaN(dimensions.width) && dimensions.width > 0 ? dimensions.width : 800;
  const graphHeight = typeof dimensions.height === 'number' && !isNaN(dimensions.height) && dimensions.height > 0 ? dimensions.height : 600;

  return (
    <div 
      ref={containerRef} 
      className="relative w-full h-full select-none overflow-hidden"
      style={{ background: 'radial-gradient(circle at center, #091a18 0%, #030c0b 100%)' }}
    >
      {/* Cyber Grid Overlay */}
      <div className="absolute inset-0 cyber-grid pointer-events-none opacity-30" />

      {/* Ambient Glowing Backlights behind densest clusters */}
      <div className="ambient-glow-cyan top-1/4 left-1/4 animate-pulse duration-[8000ms] opacity-50" />
      <div className="ambient-glow-violet bottom-1/3 right-1/3 animate-pulse duration-[12000ms] opacity-40" />

      {/* Controls HUD */}
      <div className="absolute top-4 left-4 z-10 flex flex-wrap gap-2.5 max-w-full">
        {/* Toggle Mode */}
        <div className="flex items-center gap-1 bg-[#031412]/80 backdrop-blur-lg border border-cyan-500/10 p-1 rounded-xl shadow-[0_0_15px_rgba(6,182,212,0.06)]">
          <button
            onClick={() => setGraphMode('basic')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-all cursor-pointer ${
              graphMode === 'basic' 
                ? 'bg-cyan-600/80 border border-cyan-400/30 text-white shadow-[0_0_10px_rgba(6,182,212,0.2)]' 
                : 'text-cyan-400/60 hover:text-cyan-200 hover:bg-cyan-950/20'
            }`}
          >
            <Compass className="w-3.5 h-3.5" />
            Prerequisites
          </button>
          <button
            onClick={() => setGraphMode('advanced')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-all cursor-pointer ${
              graphMode === 'advanced' 
                ? 'bg-cyan-600/80 border border-cyan-400/30 text-white shadow-[0_0_10px_rgba(6,182,212,0.2)]' 
                : 'text-cyan-400/60 hover:text-cyan-200 hover:bg-cyan-950/20'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            Related & Extends
          </button>
        </div>

        {/* Depth Slider */}
        <div className="flex items-center gap-3 bg-[#031412]/80 backdrop-blur-lg border border-cyan-500/10 px-4 py-1.5 rounded-xl shadow-[0_0_15px_rgba(6,182,212,0.06)]">
          <span className="text-xs font-medium text-cyan-400/70">Traversal Hops:</span>
          <input
            type="range"
            min="1"
            max="3"
            value={graphDepth}
            onChange={(e) => setGraphDepth(parseInt(e.target.value))}
            className="w-20 accent-cyan-500 cursor-pointer h-1 bg-slate-800 rounded-lg appearance-none"
          />
          <span className="text-xs font-bold text-cyan-400 font-mono bg-cyan-950/30 border border-cyan-500/20 px-2 py-0.5 rounded">
            {graphDepth}
          </span>
        </div>
      </div>

      {/* Loading Overlay */}
      {loading && (
        <div className="absolute top-4 right-4 z-10 flex items-center gap-2 bg-[#031412]/95 backdrop-blur-lg border border-cyan-500/15 px-3.5 py-2 rounded-xl shadow-[0_0_15px_rgba(6,182,212,0.06)]">
          <Loader2 className="w-4 h-4 text-cyan-400 animate-spin" />
          <span className="text-xs font-medium text-cyan-300">Expanding path...</span>
        </div>
      )}

      {canvasError ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center text-rose-500/60 gap-3.5 p-6 text-center z-30 bg-[#030c0b]/80 backdrop-blur-sm">
          <Layers className="w-12 h-12 text-rose-500/40 animate-pulse" />
          <h3 className="text-sm font-bold text-rose-400">Failed to Load Concept Map</h3>
          <p className="text-xs max-w-md text-slate-400 font-mono">
            {canvasError}
          </p>
          <button 
            onClick={async () => {
              setCanvasError(null);
              setLoading(true);
              try {
                const graphUrl = sessionId
                  ? `${API_BASE_URL}/sessions/${sessionId}/graph`
                  : `${API_BASE_URL}/documents/${activeDocumentId || 'doc-1'}/graph`;
                const response = await fetch(graphUrl);
                if (response.ok) {
                  const data = await response.json();
                  setGraphData(data);
                } else {
                  setCanvasError(`HTTP Error ${response.status}: ${response.statusText}`);
                }
              } catch (err: any) {
                setCanvasError(err.message || 'API connection failed');
              } finally {
                setLoading(false);
              }
            }}
            className="mt-2 px-4 py-2 text-xs font-semibold rounded-lg bg-rose-950/40 border border-rose-500/30 text-rose-400 hover:bg-rose-950/80 transition-all cursor-pointer shadow-[0_0_10px_rgba(244,63,94,0.15)]"
          >
            Retry Connection
          </button>
        </div>
      ) : safeNodes.length === 0 ? (
        <div className="w-full h-full flex flex-col items-center justify-center text-cyan-500/40 gap-2.5">
          <Layers className="w-12 h-12 text-cyan-500/30 animate-pulse" />
          <p className="text-sm font-medium">Upload a PDF document to visualize the concept map</p>
        </div>
      ) : validatedGraphData.nodes.length === 0 ? (
        <div className="w-full h-full flex flex-col items-center justify-center text-cyan-500/40 gap-2.5 p-6 text-center">
          <Layers className="w-12 h-12 text-cyan-500/30 animate-pulse" />
          <p className="text-sm font-medium">No {graphFilter || 'nodes'} found in this document</p>
          <p className="text-[10px] text-slate-500 mt-1 max-w-[240px] leading-relaxed">
            Try choosing a different section or ingest a document with more metadata.
          </p>
        </div>
      ) : (
        <GraphErrorBoundary>
          <ForceGraph2D
            ref={fgRef}
            width={graphWidth}
            height={graphHeight}
            graphData={{
              nodes: validatedGraphData.nodes.map(n => ({ ...n })),
              links: validatedGraphData.links.map(l => ({ ...l }))
            }}
            nodeId="id"
            nodeVal={(node: any) => {
              try {
                if (!node) return 3;
                const rawDegree = (nodeDegrees && node.id) ? (nodeDegrees[node.id] || 0) : 0;
                const degree = typeof rawDegree === 'number' && !isNaN(rawDegree) && rawDegree >= 0 ? rawDegree : 0;
                return 3 + Math.sqrt(degree) * 2;
              } catch (err) {
                return 3;
              }
            }}
            nodeColor={(node: any) => {
              try {
                return node && node.label ? getNodeColor(node.label) : '#06b6d4';
              } catch (err) {
                return '#06b6d4';
              }
            }}
            linkColor={(link: any) => {
              try {
                return isPathLink(link) ? '#10b981' : 'rgba(6, 182, 212, 0.12)';
              } catch (err) {
                return 'rgba(6, 182, 212, 0.12)';
              }
            }}
            linkWidth={(link: any) => {
              try {
                return isPathLink(link) ? 2.2 : 0.6;
              } catch (err) {
                return 0.6;
              }
            }}
            linkCurvature={0.25}
            linkDirectionalArrowLength={3.5}
            linkDirectionalArrowRelPos={1}
            linkDirectionalParticles={(link: any) => {
              try {
                return isPathLink(link) ? 3 : 1;
              } catch (err) {
                return 1;
              }
            }}
            linkDirectionalParticleWidth={(link: any) => {
              try {
                return isPathLink(link) ? 2.0 : 0.8;
              } catch (err) {
                return 0.8;
              }
            }}
            linkDirectionalParticleSpeed={(link: any) => {
              try {
                return isPathLink(link) ? 0.012 : 0.003;
              } catch (err) {
                return 0.003;
              }
            }}
            linkDirectionalParticleColor={(link: any) => {
              try {
                return isPathLink(link) ? '#10b981' : '#06b6d4';
              } catch (err) {
                return '#06b6d4';
              }
            }}
            onNodeClick={handleNodeClick}
            onEngineStop={() => {
              if (fgRef.current && shouldZoomToFit.current && typeof fgRef.current.zoomToFit === 'function') {
                try {
                  fgRef.current.zoomToFit(600, 80);
                } catch (_) {}
                shouldZoomToFit.current = false;
              }
            }}
            nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
              try {
                if (!node || !ctx) return;
                const x = typeof node.x === 'number' && !isNaN(node.x) ? node.x : 0;
                const y = typeof node.y === 'number' && !isNaN(node.y) ? node.y : 0;
                const rawLabel = node.name || node.title || 'Unknown';
                
                // Do not truncate labels aggressively to prevent truncation where possible
                const maxLabelLength = 40;
                const label = rawLabel.length > maxLabelLength ? rawLabel.slice(0, maxLabelLength) + '...' : rawLabel;
                
                // Fixed font size between 10-14px that scales properly with zoom
                const fontSize = 12;
                const rawDegree = (nodeDegrees && node.id) ? (nodeDegrees[node.id] || 0) : 0;
                const degree = typeof rawDegree === 'number' && !isNaN(rawDegree) && rawDegree >= 0 ? rawDegree : 0;
                const radius = 3 + Math.sqrt(degree) * 1.5;
                
                const isSelected = selectedNode?.id === node.id;
                const isPathNode = activePathNodeIds && activePathNodeIds.includes(node.id);
                const color = getNodeColor(node.label);

                const scale = typeof globalScale === 'number' && !isNaN(globalScale) && globalScale > 0 ? globalScale : 1;

                // Tech ring/dashboard effect for Selected or Topic nodes
                if (isSelected || node.label === 'Topic') {
                  ctx.save();
                  const ringRadius = radius + 6;
                  ctx.beginPath();
                  ctx.arc(x, y, ringRadius, 0, 2 * Math.PI, false);
                  ctx.strokeStyle = node.label === 'Topic' ? 'rgba(245, 158, 11, 0.45)' : 'rgba(6, 182, 212, 0.45)';
                  ctx.lineWidth = 1 / scale;
                  ctx.setLineDash([4, 4]);
                  
                  // Rotate ring slowly over time
                  const rotation = (Date.now() / 1500) % (Math.PI * 2);
                  ctx.translate(x, y);
                  ctx.rotate(rotation);
                  ctx.translate(-x, -y);
                  ctx.stroke();
                  ctx.restore();
                  
                  // Tech crosshairs/ticks
                  ctx.save();
                  ctx.strokeStyle = node.label === 'Topic' ? 'rgba(245, 158, 11, 0.6)' : 'rgba(6, 182, 212, 0.6)';
                  ctx.lineWidth = 0.75 / scale;
                  const tickLength = 3;
                  for (let angle = 0; angle < Math.PI * 2; angle += Math.PI / 2) {
                    const cos = Math.cos(angle);
                    const sin = Math.sin(angle);
                    ctx.beginPath();
                    ctx.moveTo(x + cos * (ringRadius + 1), y + sin * (ringRadius + 1));
                    ctx.lineTo(x + cos * (ringRadius + 1 + tickLength), y + sin * (ringRadius + 1 + tickLength));
                    ctx.stroke();
                  }
                  ctx.restore();
                  
                  // For topic, add outer energy sunburst rays
                  if (node.label === 'Topic') {
                    ctx.save();
                    const numRays = 16;
                    const innerR = radius + 3;
                    const outerR = radius + 14;
                    const pulse = 1.0 + 0.12 * Math.sin(Date.now() / 250);
                    for (let r = 0; r < numRays; r++) {
                      const angle = (r * Math.PI * 2) / numRays + (Date.now() / 2500);
                      const gradRay = ctx.createLinearGradient(
                        x + Math.cos(angle) * innerR,
                        y + Math.sin(angle) * innerR,
                        x + Math.cos(angle) * outerR * pulse,
                        y + Math.sin(angle) * outerR * pulse
                      );
                      gradRay.addColorStop(0, 'rgba(245, 158, 11, 0.7)');
                      gradRay.addColorStop(1, 'rgba(245, 158, 11, 0)');
                      ctx.strokeStyle = gradRay;
                      ctx.lineWidth = 1.5 / scale;
                      ctx.beginPath();
                      ctx.moveTo(x + Math.cos(angle) * innerR, y + Math.sin(angle) * innerR);
                      ctx.lineTo(x + Math.cos(angle) * outerR * pulse, y + Math.sin(angle) * outerR * pulse);
                      ctx.stroke();
                    }
                    ctx.restore();
                  }
                } else if (isPathNode) {
                  // Path nodes glow pulse
                  const pathIdx = activePathNodeIds.indexOf(node.id);
                  const pulseFactor = 0.5 + 0.5 * Math.sin(Date.now() / 200 - pathIdx * 0.8);
                  ctx.save();
                  ctx.beginPath();
                  ctx.arc(x, y, radius + 4 + pulseFactor * 2, 0, 2 * Math.PI, false);
                  ctx.fillStyle = `rgba(16, 185, 129, ${0.1 + pulseFactor * 0.15})`;
                  ctx.fill();
                  ctx.strokeStyle = 'rgba(16, 185, 129, 0.35)';
                  ctx.lineWidth = 1 / scale;
                  ctx.stroke();
                  ctx.restore();
                }

                // Draw glass sphere node with inner radial gradient
                ctx.save();
                ctx.shadowColor = color;
                ctx.shadowBlur = 10;
                
                const grad = ctx.createRadialGradient(
                  x - radius * 0.2,
                  y - radius * 0.2,
                  radius * 0.05,
                  x,
                  y,
                  radius
                );
                
                // Sphere highlighting
                grad.addColorStop(0, '#ffffff');
                grad.addColorStop(0.2, color);
                grad.addColorStop(0.85, color);
                grad.addColorStop(1, 'rgba(0, 0, 0, 0.5)');
                
                ctx.beginPath();
                ctx.arc(x, y, radius, 0, 2 * Math.PI, false);
                ctx.fillStyle = grad;
                ctx.fill();
                
                // Rim highlight
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.35)';
                ctx.lineWidth = 0.5 / scale;
                ctx.stroke();
                ctx.restore();

                // Label text below node
                ctx.font = `${fontSize}px Outfit, system-ui, sans-serif`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                
                // Draw background rectangle for text readability at high zoom
                const textWidth = ctx.measureText(label).width;
                ctx.fillStyle = 'rgba(3, 12, 11, 0.85)';
                ctx.fillRect(
                  x - textWidth / 2 - 3,
                  y + radius + 2,
                  textWidth + 6,
                  fontSize + 2
                );

                // Draw text
                ctx.fillStyle = isSelected || isPathNode ? '#ffffff' : '#cbd5e1';
                ctx.fillText(label, x, y + radius + 3);
              } catch (err) {
                console.error("Failed to render custom node canvas shape:", err);
                // Safe minimal fallback circle shape
                try {
                  ctx.beginPath();
                  ctx.arc(node.x || 0, node.y || 0, 4, 0, 2 * Math.PI);
                  ctx.fillStyle = '#06b6d4';
                  ctx.fill();
                } catch (_) {}
              }
            }}
          />
        </GraphErrorBoundary>
      )}
    </div>
  );
}
