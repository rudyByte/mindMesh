'use client';

import React, { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { useStore, GraphNode, GraphEdge } from '../store/useStore';
import { Layers, Compass, Loader2 } from 'lucide-react';

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

export default function GraphCanvas() {
  const containerRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<any>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [loading, setLoading] = useState(false);

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

  // Track dimensions
  useEffect(() => {
    if (!containerRef.current) return;
    const updateDimensions = () => {
      setDimensions({
        width: containerRef.current?.clientWidth || 800,
        height: containerRef.current?.clientHeight || 600,
      });
    };
    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  // Fetch initial graph if empty
  useEffect(() => {
    const fetchInitialGraph = async () => {
      setLoading(true);
      try {
        // Query list of all nodes to display a default set if no document is uploaded
        const response = await fetch('http://localhost:8000/documents/doc-1/graph');
        if (response.ok) {
          const data = await response.json();
          setGraphData(data);
        }
      } catch (err) {
        console.error('Failed to load initial graph', err);
      } finally {
        setLoading(false);
      }
    };
    if (nodes.length === 0) {
      fetchInitialGraph();
    }
  }, [nodes.length, setGraphData]);

  // Compute degree for each node (number of connections)
  const nodeDegrees = React.useMemo(() => {
    const degrees: Record<string, number> = {};
    nodes.forEach(n => degrees[n.id] = 0);
    edges.forEach(e => {
      const fromId = typeof e.source === 'object' ? e.source.id : e.source || e.from;
      const toId = typeof e.target === 'object' ? e.target.id : e.target || e.to;
      if (degrees[fromId] !== undefined) degrees[fromId]++;
      if (degrees[toId] !== undefined) degrees[toId]++;
    });
    return degrees;
  }, [nodes, edges]);

  // Helper to detect if a link is part of the learning path
  const isPathLink = (link: any) => {
    if (!activePathNodeIds || activePathNodeIds.length < 2) return false;
    const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
    const targetId = typeof link.target === 'object' ? link.target.id : link.target;
    const sIdx = activePathNodeIds.indexOf(sourceId);
    const tIdx = activePathNodeIds.indexOf(targetId);
    return sIdx !== -1 && tIdx !== -1 && tIdx === sIdx + 1;
  };

  // Color mapping based on label
  const getNodeColor = (label: string) => {
    switch (label) {
      case 'Concept': return '#3b82f6'; // Blue
      case 'Paper': return '#a855f7';   // Purple
      case 'Author': return '#10b981';  // Green
      case 'Topic': return '#f59e0b';   // Amber
      default: return '#64748b';        // Slate
    }
  };

  const handleNodeClick = async (node: any) => {
    const clickedNode: GraphNode = {
      id: node.id,
      label: node.label,
      name: node.name || node.title,
      description: node.description,
      difficulty_level: node.difficulty_level
    };
    setSelectedNode(clickedNode);
    setLoading(true);

    try {
      // Fetch dynamic node expansion
      const url = `http://localhost:8000/graph/expand?node_id=${node.id}&depth=${graphDepth}&mode=${graphMode}`;
      const response = await fetch(url);
      if (response.ok) {
        const expandedData = await response.json();
        appendGraphData(expandedData);
      }
    } catch (err) {
      console.error('Failed to expand node', err);
    } finally {
      setLoading(false);
    }
  };

  // Center on graph when loaded
  useEffect(() => {
    if (fgRef.current && nodes.length > 0) {
      fgRef.current.zoomToFit(400, 50);
    }
  }, [nodes.length]);

  return (
    <div ref={containerRef} className="relative w-full h-full bg-[#030712] select-none">
      {/* Controls HUD */}
      <div className="absolute top-4 left-4 z-10 flex flex-wrap gap-2.5 max-w-full">
        {/* Toggle Mode */}
        <div className="flex items-center gap-1 bg-slate-900/80 backdrop-blur border border-slate-800 p-1 rounded-xl shadow-lg">
          <button
            onClick={() => setGraphMode('basic')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-all ${
              graphMode === 'basic' 
                ? 'bg-indigo-600 text-white shadow-md' 
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Compass className="w-3.5 h-3.5" />
            Prerequisites
          </button>
          <button
            onClick={() => setGraphMode('advanced')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-all ${
              graphMode === 'advanced' 
                ? 'bg-indigo-600 text-white shadow-md' 
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            Related & Extends
          </button>
        </div>

        {/* Depth Slider */}
        <div className="flex items-center gap-3 bg-slate-900/80 backdrop-blur border border-slate-800 px-4 py-1.5 rounded-xl shadow-lg">
          <span className="text-xs font-medium text-slate-400">Traversal Hops:</span>
          <input
            type="range"
            min="1"
            max="3"
            value={graphDepth}
            onChange={(e) => setGraphDepth(parseInt(e.target.value))}
            className="w-20 accent-indigo-500 cursor-pointer h-1 bg-slate-800 rounded-lg appearance-none"
          />
          <span className="text-xs font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded">
            {graphDepth}
          </span>
        </div>
      </div>

      {/* Loading Overlay */}
      {loading && (
        <div className="absolute top-4 right-4 z-10 flex items-center gap-2 bg-slate-900/90 backdrop-blur border border-slate-800 px-3.5 py-2 rounded-xl shadow-lg">
          <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
          <span className="text-xs font-medium text-slate-300">Expanding path...</span>
        </div>
      )}

      {nodes.length === 0 ? (
        <div className="w-full h-full flex flex-col items-center justify-center text-slate-500 gap-2.5">
          <Layers className="w-12 h-12 text-slate-600 animate-pulse" />
          <p className="text-sm font-medium">Upload a PDF document to visualize the concept map</p>
        </div>
      ) : (
        <ForceGraph2D
          ref={fgRef}
          width={dimensions.width}
          height={dimensions.height}
          graphData={{
            nodes: nodes.map(n => ({ ...n })),
            links: edges.map(e => ({
              source: typeof e.source === 'object' ? e.source.id : e.source || e.from,
              target: typeof e.target === 'object' ? e.target.id : e.target || e.to,
              type: e.type
            }))
          }}
          nodeId="id"
          nodeVal={(node: any) => {
            const deg = nodeDegrees[node.id] || 0;
            return 3 + Math.sqrt(deg) * 2;
          }}
          nodeColor={(node: any) => getNodeColor(node.label)}
          linkColor={(link: any) => isPathLink(link) ? '#10b981' : 'rgba(255, 255, 255, 0.08)'}
          linkWidth={(link: any) => isPathLink(link) ? 2.5 : 1}
          linkDirectionalArrowLength={3.5}
          linkDirectionalArrowRelPos={1}
          linkDirectionalParticles={(link: any) => isPathLink(link) ? 4 : 1}
          linkDirectionalParticleSpeed={(link: any) => isPathLink(link) ? 0.015 : 0.005}
          onNodeClick={handleNodeClick}
          nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
            const label = node.name || node.title || 'Unknown';
            const fontSize = Math.max(2.5, 9 / globalScale);
            const degree = nodeDegrees[node.id] || 0;
            const radius = 3 + Math.sqrt(degree) * 1.5;
            
            // Draw outer glow if part of active learning path
            const isPathNode = activePathNodeIds && activePathNodeIds.includes(node.id);
            if (isPathNode) {
              const pathIdx = activePathNodeIds.indexOf(node.id);
              const time = Date.now() / 1000;
              const pulseFactor = 0.5 + 0.5 * Math.sin(time * 5 - pathIdx * 0.8);
              
              ctx.beginPath();
              ctx.arc(node.x, node.y, radius + 3 + pulseFactor * 2.5, 0, 2 * Math.PI, false);
              ctx.fillStyle = `rgba(16, 185, 129, ${0.15 + pulseFactor * 0.25})`;
              ctx.fill();
              ctx.strokeStyle = '#10b981';
              ctx.lineWidth = (1.5 + pulseFactor * 1.5) / globalScale;
              ctx.stroke();
            } else {
              // Draw regular outer glow if selected
              const isSelected = selectedNode?.id === node.id;
              if (isSelected) {
                ctx.beginPath();
                ctx.arc(node.x, node.y, radius + 2, 0, 2 * Math.PI, false);
                ctx.fillStyle = 'rgba(99, 102, 241, 0.25)';
                ctx.fill();
                ctx.strokeStyle = '#818cf8';
                ctx.lineWidth = 1 / globalScale;
                ctx.stroke();
              }
            }

            // Draw node circle
            ctx.beginPath();
            ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
            ctx.fillStyle = getNodeColor(node.label);
            ctx.fill();
            
            // Thin white border for contrast
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.9)';
            ctx.lineWidth = 0.5 / globalScale;
            ctx.stroke();

            // Label text below node
            ctx.font = `${fontSize}px Outfit, sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'top';
            
            // Draw background rectangle for text readability at high zoom
            const textWidth = ctx.measureText(label).width;
            ctx.fillStyle = 'rgba(3, 7, 18, 0.75)';
            ctx.fillRect(
              node.x - textWidth / 2 - 1.5,
              node.y + radius + 1.5,
              textWidth + 3,
              fontSize + 1
            );

            // Draw text
            const isSelected = selectedNode?.id === node.id;
            ctx.fillStyle = isSelected || isPathNode ? '#ffffff' : '#cbd5e1';
            ctx.fillText(label, node.x, node.y + radius + 2);
          }}
        />
      )}
    </div>
  );
}
