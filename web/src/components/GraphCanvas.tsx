'use client';

import React, { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { useStore, GraphNode, GraphEdge } from '../store/useStore';
import { API_BASE_URL } from '../lib/api';
import { Layers, Loader2, Search, MapPin, Filter } from 'lucide-react';
import { forceCollide, forceX, forceY } from 'd3-force';
import LearningRoadmapOverlay from './LearningRoadmapOverlay';

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
  const [isOverlayOpen, setIsOverlayOpen] = useState(false);
  const [roadmapData, setRoadmapData] = useState<any[]>([]);
  const [roadmapLoading, setRoadmapLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [edgeTypeFilter, setEdgeTypeFilter] = useState<string | null>(null);
  const [showMiniMap, setShowMiniMap] = useState(true);

  // Simulation tick state & stable refs to prevent reset during react renders
  const [tick, setTick] = useState(0);
  const d3NodesRef = useRef<any[]>([]);
  const d3LinksRef = useRef<any[]>([]);
  const prevFilteredNodesRef = useRef<any[]>([]);
  const prevFilteredEdgesRef = useRef<any[]>([]);

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
  const activePathNodeIds = useStore((state) => state.activePathNodeIds);
  const documents = useStore((state) => state.documents);
  const activeDocumentId = useStore((state) => state.activeDocumentId);
  const graphFilter = useStore((state) => state.graphFilter);
  const sessionId = useStore((state) => state.sessionId);

  const shouldZoomToFit = useRef(false);
  const selectedNodeId = selectedNode?.id;

  const safeNodes = Array.isArray(nodes) ? nodes : [];
  const safeEdges = Array.isArray(edges) ? edges : [];

  const filteredNodes = React.useMemo(() => {
    if (!graphFilter) return safeNodes;
    if (graphFilter === 'Concept') {
      return safeNodes.filter(n => n && ['Concept', 'Topic', 'Method', 'Dataset', 'Keyword'].includes(n.label));
    }
    if (graphFilter === 'Paper') {
      return safeNodes.filter(n => n && ['Paper', 'Author'].includes(n.label));
    }
    if (graphFilter === 'Learning Path') {
      if (activePathNodeIds && activePathNodeIds.length > 0) {
        const pathSet = new Set(activePathNodeIds);
        return safeNodes.filter(n => n && pathSet.has(n.id));
      }
      return safeNodes.filter(n => n && ['Concept', 'Topic', 'Application'].includes(n.label));
    }
    return safeNodes.filter(n => n && n.label === graphFilter);
  }, [safeNodes, graphFilter, activePathNodeIds]);

  const filteredEdges = React.useMemo(() => {
    const nodeIds = new Set(filteredNodes.map(n => n.id));
    return safeEdges.filter(e => {
      if (!e) return false;
      if (edgeTypeFilter && (e.type || 'RELATED_TO') !== edgeTypeFilter) return false;
      const fromId = typeof e.source === 'object' && e.source !== null ? (e.source as any).id : e.source || e.from;
      const toId = typeof e.target === 'object' && e.target !== null ? (e.target as any).id : e.target || e.to;
      return nodeIds.has(fromId) && nodeIds.has(toId);
    });
  }, [safeEdges, filteredNodes, edgeTypeFilter]);

  const edgeTypes = React.useMemo(() => {
    return Array.from(new Set(safeEdges.map(e => e?.type || 'RELATED_TO').filter(Boolean))).sort();
  }, [safeEdges]);

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
      fx: typeof (n as any).fx === 'number' && !isNaN((n as any).fx) ? (n as any).fx : undefined,
      fy: typeof (n as any).fy === 'number' && !isNaN((n as any).fy) ? (n as any).fy : undefined,
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

  // ── Preserve Simulated Positions & Calculate DAG Levels ──────────────────
  // We use an iterative DAG levelling algorithm to assign topological depths.
  // Topics sit at level 0, concept nodes with no prereqs at level 1, concepts
  // with prerequisites are pushed to levels 2, 3, etc. based on longest path.
  if (filteredNodes !== prevFilteredNodesRef.current || filteredEdges !== prevFilteredEdgesRef.current) {
    prevFilteredNodesRef.current = filteredNodes;
    prevFilteredEdgesRef.current = filteredEdges;

    const levels: Record<string, number> = {};
    filteredNodes.forEach(n => {
      if (n.label === 'Topic') levels[n.id] = 0;
      else if (n.label === 'Concept') levels[n.id] = 1;
      else if (n.label === 'Paper' || n.label === 'Method' || n.label === 'Dataset') levels[n.id] = 2;
      else levels[n.id] = 3;
    });

    // Relax levels iteratively based on directed relationship directions
    for (let iter = 0; iter < 12; iter++) {
      let changed = false;
      filteredEdges.forEach(l => {
        const fromId = typeof l.source === 'object' && l.source !== null ? (l.source as any).id : l.source || l.from;
        const toId = typeof l.target === 'object' && l.target !== null ? (l.target as any).id : l.target || l.to;
        if (!fromId || !toId || levels[fromId] === undefined || levels[toId] === undefined) return;

        // Prerequisite rules: prerequisite (from) is above target (to)
        if (l.type === 'PREREQUISITE_OF' || l.type === 'PREREQUISITE') {
          if (levels[toId] < levels[fromId] + 1) {
            levels[toId] = levels[fromId] + 1;
            changed = true;
          }
        }
        // Extends rules: general concept (to) is above specific concept (from)
        if (l.type === 'EXTENDS') {
          if (levels[fromId] < levels[toId] + 1) {
            levels[fromId] = levels[toId] + 1;
            changed = true;
          }
        }
        // Used_for rules: fundamental method (from) is above application (to)
        if (l.type === 'USED_FOR') {
          if (levels[toId] < levels[fromId] + 1) {
            levels[toId] = levels[fromId] + 1;
            changed = true;
          }
        }
      });
      if (!changed) break;
    }

    const maxLevel = Math.max(1, ...Object.values(levels));
    const W = dimensions.width || 800;
    const H = dimensions.height || 600;
    const ySpan = H * 0.72;
    const yStart = -ySpan / 2;
    const yStep = ySpan / maxLevel;

    // Group nodes by level to compute horizontal spacing
    const levelGroups: Record<number, any[]> = {};
    for (let l = 0; l <= maxLevel; l++) levelGroups[l] = [];
    filteredNodes.forEach(n => {
      const lvl = levels[n.id] ?? 1;
      levelGroups[lvl].push(n);
    });

    // Populate stable ref nodes preserving existing simulated positions
    d3NodesRef.current = filteredNodes.map(n => {
      const lvl = levels[n.id] ?? 1;
      const peers = levelGroups[lvl];
      const idx = peers.indexOf(n);
      const count = Math.max(1, peers.length);
      const xRange = Math.min(W * 0.85, count * 150);
      const x = count === 1 ? 0 : -xRange / 2 + (idx / (count - 1)) * xRange;
      const y = yStart + lvl * yStep;

      const existing = d3NodesRef.current.find(prev => prev.id === n.id);
      return {
        ...n,
        x: existing?.x ?? x,
        y: existing?.y ?? y,
        vx: existing?.vx ?? 0,
        vy: existing?.vy ?? 0,
        level: lvl
      };
    });

    // Populate stable ref links
    d3LinksRef.current = filteredEdges.map(e => {
      const fromId = typeof e.source === 'object' && e.source !== null ? (e.source as any).id : e.source || e.from;
      const toId = typeof e.target === 'object' && e.target !== null ? (e.target as any).id : e.target || e.to;
      return {
        source: fromId,
        target: toId,
        type: e.type || 'RELATED_TO'
      };
    });
  }

  // Set zoom to fit flag when nodes are loaded or active document changes
  useEffect(() => {
    if (safeNodes.length > 0) {
      shouldZoomToFit.current = true;
    }
  }, [nodes, activeDocumentId, safeNodes.length]);

  // Keep traversal controls live. Replace the neighborhood so reducing depth
  // contracts the graph instead of leaving previously appended nodes behind.
  useEffect(() => {
    if (!selectedNodeId || !activeDocumentId) return;
    if (selectedNodeId.startsWith('llm-req-')) return;

    const controller = new AbortController();
    const expandSelectedNode = async () => {
      setLoading(true);
      setCanvasError(null);
      try {
        const scope = sessionId
          ? `session_id=${encodeURIComponent(sessionId)}`
          : `document_id=${encodeURIComponent(activeDocumentId || '')}`;
        const url = graphMode === 'path'
          ? `${API_BASE_URL}/graph/hierarchy?focus=${encodeURIComponent(selectedNodeId)}&up=${graphDepth}&down=${Math.max(1, graphDepth)}&${scope}`
          : `${API_BASE_URL}/graph/expand?node_id=${encodeURIComponent(selectedNodeId)}&depth=${graphDepth}&mode=${graphMode}&${scope}`;
        const response = await fetch(url, { signal: controller.signal });
        if (!response.ok) throw new Error(`Traversal failed (HTTP ${response.status})`);
        const data = await response.json();
        if (graphMode === 'path') {
          const prereqs = Array.isArray(data.prerequisites) ? data.prerequisites : [];
          const extensions = Array.isArray(data.extensions) ? data.extensions : [];
          const applications = Array.isArray(data.applications) ? data.applications : [];
          const related = Array.isArray(data.related) ? data.related : [];
          const target = data.target;

          const positionTier = (items: any[], y: number, xOffset = 0) => items.map((item, idx) => {
            const count = Math.max(1, items.length);
            const x = xOffset + (idx - (count - 1) / 2) * 180;
            return { ...item, x, y, fx: x, fy: y };
          });

          const prereqNodes = positionTier(prereqs, -220, 0);
          const extensionNodes = positionTier(extensions, 210, -120);
          const appNodes = positionTier(applications, 340, 120);
          const relatedNodes = positionTier(related, 20, 360);
          const targetNode = target ? { ...target, x: 0, y: 0, fx: 0, fy: 0 } : null;
          const pathNodes = [...prereqNodes, ...(targetNode ? [targetNode] : []), ...extensionNodes, ...appNodes, ...relatedNodes];
          const pathEdges = [
            ...prereqNodes.map((n: any) => ({ from: n.id, to: selectedNodeId, type: 'PREREQUISITE_OF' })),
            ...extensionNodes.map((n: any) => ({ from: selectedNodeId, to: n.id, type: 'EXTENDS' })),
            ...appNodes.map((n: any) => ({ from: selectedNodeId, to: n.id, type: 'USED_FOR' })),
            ...relatedNodes.map((n: any) => ({ from: selectedNodeId, to: n.id, type: 'RELATED_TO' })),
          ];
          setGraphData({ nodes: pathNodes, edges: pathEdges });
        } else {
          setGraphData({
            nodes: Array.isArray(data.nodes) ? data.nodes : [],
            edges: Array.isArray(data.edges) ? data.edges : [],
          });
        }
        shouldZoomToFit.current = true;
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') return;
        setCanvasError(error instanceof Error ? error.message : 'Traversal request failed');
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };

    expandSelectedNode();
    return () => controller.abort();
  }, [selectedNodeId, graphDepth, graphMode, activeDocumentId, sessionId, setGraphData]);

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
      if (containerRef.current) {
        const w = containerRef.current.clientWidth;
        const h = containerRef.current.clientHeight;
        setDimensions(prev => {
          if (prev.width !== w || prev.height !== h) {
            // Trigger a re-center if dimensions change (e.g. sidebar toggle)
            if (fgRef.current && typeof fgRef.current.zoomToFit === 'function') {
              setTimeout(() => {
                try { fgRef.current.zoomToFit(400, 140); } catch (e) {}
              }, 50);
            }
            return {
              width: typeof w === 'number' && !isNaN(w) && w > 0 ? w : 800,
              height: typeof h === 'number' && !isNaN(h) && h > 0 ? h : 600,
            };
          }
          return prev;
        });
      }
    };
    
    updateDimensions();
    
    const resizeObserver = new ResizeObserver(() => {
      updateDimensions();
    });
    
    resizeObserver.observe(containerRef.current);
    
    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  // Fetch document graph when activeDocumentId changes if not already loaded
  useEffect(() => {
    const fetchGraph = async () => {
      if (!activeDocumentId) return;
      if (nodes.length > 0) return; // Skip if already loaded by store
      setLoading(true);
      setCanvasError(null);
      try {
        const response = await fetch(`${API_BASE_URL}/documents/${activeDocumentId}/graph`);
        if (response.ok) {
          const data = await response.json();
          setGraphData(data);
        } else {
          setCanvasError(`HTTP Error ${response.status}: ${response.statusText}`);
        }
      } catch (err: any) {
        console.error('Failed to load document graph', err);
        setCanvasError(err.message || 'API connection failed');
      } finally {
        setLoading(false);
      }
    };

    fetchGraph();
  }, [activeDocumentId, setGraphData, nodes.length]);

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

  const jumpToNode = (node: GraphNode) => {
    setSelectedNode(node);
    try {
      const fg = fgRef.current;
      const graphData = fg?.graphData?.();
      const renderedNode = graphData?.nodes?.find((n: any) => n.id === node.id) || node;
      const x = typeof renderedNode.x === 'number' ? renderedNode.x : (node.x || node.fx || 0);
      const y = typeof renderedNode.y === 'number' ? renderedNode.y : (node.y || node.fy || 0);
      fg?.centerAt?.(x, y, 700);
      fg?.zoom?.(2.8, 700);
    } catch (err) {
      console.error('Failed to jump to node:', err);
    }
  };

  const handleSearchSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    const term = searchTerm.trim().toLowerCase();
    if (!term) return;
    const match = validatedGraphData.nodes.find(n =>
      (n.name || '').toLowerCase().includes(term) ||
      (n.label || '').toLowerCase().includes(term)
    );
    if (match) jumpToNode(match as GraphNode);
  };

  const minimapNodes = React.useMemo(() => {
    const positioned = d3NodesRef.current.map((node: any) => ({
      node,
      x: typeof node.x === 'number' ? node.x : 0,
      y: typeof node.y === 'number' ? node.y : 0,
    }));
    if (!positioned.length) return [];
    const minX = Math.min(...positioned.map(p => p.x));
    const maxX = Math.max(...positioned.map(p => p.x));
    const minY = Math.min(...positioned.map(p => p.y));
    const maxY = Math.max(...positioned.map(p => p.y));
    const width = Math.max(1, maxX - minX);
    const height = Math.max(1, maxY - minY);
    return positioned.map(p => ({
      node: p.node,
      x: 10 + ((p.x - minX) / width) * 140,
      y: 10 + ((p.y - minY) / height) * 90,
    }));
  }, [tick]);

  // ── Hierarchical layout via D3 forces ────────────────────────────────────
  useEffect(() => {
    if (!fgRef.current || !d3NodesRef.current.length) return;
    try {
      const fg = fgRef.current;
      const canvasHeight = dimensions.height || 600;
      const canvasWidth  = dimensions.width  || 800;

      const maxLevel = Math.max(1, ...d3NodesRef.current.map(n => n.level ?? 1));
      const ySpan  = canvasHeight * 0.76;
      const yStart = -ySpan / 2;
      const yStep  = ySpan / maxLevel;
      const levelY  = (level: number) => yStart + level * yStep;

      // Group node IDs by level for X distribution
      const levelGroups: Record<number, string[]> = {};
      for (let l = 0; l <= maxLevel; l++) levelGroups[l] = [];
      d3NodesRef.current.forEach((n: any) => {
        const lvl = n.level ?? 1;
        levelGroups[lvl].push(n.id);
      });

      // ❶ Kill center force
      fg.d3Force('center', null);

      // ❷ Moderate charge repulsion
      const chargeForce = fg.d3Force('charge');
      if (chargeForce && typeof chargeForce.strength === 'function') {
        chargeForce.strength(-380);
      }

      // ❸ Link distance
      const linkForce = fg.d3Force('link');
      if (linkForce && typeof linkForce.distance === 'function') {
        linkForce.distance((link: any) => {
          try {
            const srcId = typeof link.source === 'object' ? link.source?.id : link.source;
            const tgtId = typeof link.target === 'object' ? link.target?.id : link.target;
            const srcNode = d3NodesRef.current.find((n: any) => n.id === srcId);
            const tgtNode = d3NodesRef.current.find((n: any) => n.id === tgtId);
            return (srcNode?.level === tgtNode?.level) ? 140 : 200;
          } catch { return 170; }
        });
      }

      // ❹ Strong forceY — locks each node to its computed DAG level Y
      fg.d3Force('y', forceY((node: any) => {
        return levelY(node.level ?? 1);
      }).strength(0.9));

      // ❺ forceX — distributes nodes evenly across canvas width per level
      fg.d3Force('x', forceX((node: any) => {
        const lvl = node.level ?? 1;
        const siblings = levelGroups[lvl];
        const idx   = siblings.indexOf(node.id);
        const count = Math.max(1, siblings.length);
        const xRange = Math.min(canvasWidth * 0.88, count * 160);
        if (count === 1) return 0;
        return -xRange / 2 + (idx / (count - 1)) * xRange;
      }).strength(0.55));

      // ❻ Collision
      const collideForce = forceCollide((node: any) => {
        try {
          const rawDegree = (nodeDegrees && node && node.id) ? (nodeDegrees[node.id] || 0) : 0;
          const degree = typeof rawDegree === 'number' && !isNaN(rawDegree) && rawDegree >= 0 ? rawDegree : 0;
          return 4 + Math.sqrt(degree) * 1.8 + 48;
        } catch { return 52; }
      });
      if (collideForce && typeof collideForce.iterations === 'function') {
        fg.d3Force('collide', collideForce.iterations(4));
      }

      if (typeof fg.d3ReheatSimulation === 'function') {
        fg.d3ReheatSimulation();
      }
    } catch (err) {
      console.error('Error configuring hierarchical D3 forces:', err);
    }
  }, [filteredNodes, nodeDegrees, dimensions]);

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
      case 'Method': return '#22c55e';  // Neon Green
      case 'Dataset': return '#f97316'; // Bright Orange
      case 'Paper': return '#8b5cf6';   // Soft Violet
      case 'Author': return '#d946ef';  // Vibrant Magenta/Violet
      case 'Topic': return '#f59e0b';   // Warm Amber
      case 'Keyword': return '#14b8a6'; // Vibrant Teal
      default: return '#06b6d4';
    }
  };

  const getLinkColor = (type: string, isActivePath = false) => {
    if (isActivePath) return '#10b981';
    switch (type) {
      case 'PREREQUISITE_OF':
      case 'PREREQUISITE':
        return 'rgba(34, 211, 238, 0.95)';
      case 'EXTENDS':
      case 'USED_FOR':
        return 'rgba(16, 185, 129, 0.9)';
      case 'CITES':
      case 'MENTIONS':
        return 'rgba(168, 85, 247, 0.86)';
      case 'HAS_KEYWORD':
        return 'rgba(20, 184, 166, 0.76)';
      default:
        return 'rgba(203, 213, 225, 0.72)';
    }
  };

  const handleNodeClick = async (node: any) => {
    if (!node || !node.id) return;
    const clickedNode: GraphNode = {
      ...node,
      id: node.id,
      label: node.label,
      name: node.name || node.title || 'Unknown',
      description: node.description || '',
      difficulty_level: node.difficulty_level || 'Beginner',
    };
    setSelectedNode(clickedNode);
    setIsOverlayOpen(true);
    setRoadmapLoading(true);
    setRoadmapData([]);

    try {
      // Fetch Learning Roadmap data
      const roadmapUrl = `${API_BASE_URL}/learning-roadmap/${node.id}`;
      const roadmapRes = await fetch(roadmapUrl);
      if (roadmapRes.ok) {
        const roadmapJson = await roadmapRes.json();
        setRoadmapData(roadmapJson.roadmap || []);
      }
    } catch (err) {
      console.error('Failed to retrieve learning roadmap', err);
    } finally {
      setRoadmapLoading(false);
    }

    try {
      if (node.id.startsWith('llm-req-')) return;
      
      // Fetch full details of the clicked node
      const detailsScope = sessionId
        ? `session_id=${encodeURIComponent(sessionId)}`
        : `document_id=${encodeURIComponent(activeDocumentId || 'doc-1')}`;
      const detailsUrl = `${API_BASE_URL}/graph/node/${node.id}?${detailsScope}`;
      const detailsRes = await fetch(detailsUrl);
      if (detailsRes.ok) {
        const detailsData = await detailsRes.json();
        setSelectedNode(detailsData);
      } else {
        console.error(`Failed to load node details (HTTP ${detailsRes.status})`);
      }

    } catch (err: any) {
      console.error('Failed to retrieve node details', err);
    }
  };

  const graphWidth = typeof dimensions.width === 'number' && !isNaN(dimensions.width) && dimensions.width > 0 ? dimensions.width : 800;
  const graphHeight = typeof dimensions.height === 'number' && !isNaN(dimensions.height) && dimensions.height > 0 ? dimensions.height : 600;

  return (
    <div 
      ref={containerRef} 
      className="mission-canvas relative w-full h-full select-none overflow-hidden"
    >
      {/* Cyber Grid Overlay */}
      <div className="absolute inset-0 cyber-grid pointer-events-none opacity-30" />

      {/* Ambient Glowing Backlights behind densest clusters */}
      <div className="ambient-glow-cyan top-1/4 left-1/4 animate-pulse duration-[8000ms] opacity-50" />
      <div className="ambient-glow-violet bottom-1/3 right-1/3 animate-pulse duration-[12000ms] opacity-40" />

      {/* Search / filters */}
      {safeNodes.length > 0 && (
        <div className="absolute top-4 left-4 z-30 flex flex-col gap-2 w-[min(360px,calc(100%-2rem))] pointer-events-auto">
          <form
            onSubmit={handleSearchSubmit}
            className="flex items-center gap-2 bg-[#031412]/95 backdrop-blur-lg border border-cyan-500/25 px-2.5 py-2 rounded-xl shadow-[0_0_18px_rgba(6,182,212,0.10)]"
          >
            <Search className="w-4 h-4 text-cyan-300 shrink-0" />
            <input
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              list="mindmesh-node-search"
              placeholder="Search node, concept, paper..."
              className="min-w-0 flex-1 bg-transparent outline-none text-xs text-cyan-50 placeholder:text-slate-500 font-medium"
            />
            <datalist id="mindmesh-node-search">
              {validatedGraphData.nodes.slice(0, 160).map((node) => (
                <option key={node.id} value={node.name} />
              ))}
            </datalist>
            <button
              type="submit"
              className="px-2.5 py-1 rounded-lg bg-cyan-500/15 border border-cyan-400/30 text-[10px] font-bold uppercase tracking-wider text-cyan-100 hover:bg-cyan-500/25"
            >
              Jump
            </button>
          </form>

          <div className="flex flex-wrap items-center gap-1.5 bg-[#031412]/90 backdrop-blur-lg border border-cyan-500/15 px-2 py-2 rounded-xl">
            <span className="flex items-center gap-1 px-1 text-[9px] font-mono font-bold uppercase tracking-widest text-cyan-400/70">
              <Filter className="w-3.5 h-3.5" /> Edges
            </span>
            <button
              onClick={() => setEdgeTypeFilter(null)}
              data-active={!edgeTypeFilter}
              className="px-2 py-1 rounded-md border border-slate-600/30 text-[9px] font-bold uppercase tracking-wider text-slate-300 data-[active=true]:border-cyan-400/60 data-[active=true]:text-cyan-100 data-[active=true]:bg-cyan-500/15"
            >
              All
            </button>
            {edgeTypes.slice(0, 7).map((type) => (
              <button
                key={type}
                onClick={() => setEdgeTypeFilter(edgeTypeFilter === type ? null : type)}
                data-active={edgeTypeFilter === type}
                className="px-2 py-1 rounded-md border border-slate-600/30 text-[9px] font-bold uppercase tracking-wider text-slate-300 data-[active=true]:border-cyan-400/60 data-[active=true]:text-cyan-100 data-[active=true]:bg-cyan-500/15"
              >
                {type.replaceAll('_', ' ')}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Map / Path View switch */}
      {selectedNodeId && (
        <div className="absolute top-4 right-4 z-20 flex items-center gap-2 bg-[#031412]/95 backdrop-blur-lg border border-cyan-500/20 px-2 py-2 rounded-xl shadow-[0_0_18px_rgba(6,182,212,0.08)]">
          <button
            onClick={() => setGraphMode('advanced')}
            data-active={graphMode !== 'path'}
            className="px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider border border-cyan-500/20 text-cyan-200 data-[active=true]:bg-cyan-500/15 data-[active=true]:border-cyan-400/60"
          >
            Map View
          </button>
          <button
            onClick={() => setGraphMode('path')}
            data-active={graphMode === 'path'}
            className="px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider border border-emerald-500/20 text-emerald-200 data-[active=true]:bg-emerald-500/15 data-[active=true]:border-emerald-400/60"
          >
            Path View
          </button>
          {graphMode === 'path' && (
            <button
              onClick={() => setGraphDepth(Math.min(6, graphDepth + 1))}
              className="px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider border border-amber-500/25 text-amber-200 hover:bg-amber-500/10"
            >
              I don&apos;t know this ↑
            </button>
          )}
        </div>
      )}

      {/* Loading Overlay */}
      {loading && (
        <div className="absolute top-20 right-4 z-10 flex items-center gap-2 bg-[#031412]/95 backdrop-blur-lg border border-cyan-500/15 px-3.5 py-2 rounded-xl shadow-[0_0_15px_rgba(6,182,212,0.06)]">
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
                const graphUrl = `${API_BASE_URL}/documents/${activeDocumentId || 'doc-1'}/graph`;
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
              nodes: d3NodesRef.current,
              links: d3LinksRef.current
            }}
            nodeId="id"
            onEngineTick={() => setTick(t => t + 1)}
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
                return getLinkColor(link?.type || 'RELATED_TO', isPathLink(link));
              } catch (err) {
                return 'rgba(148, 163, 184, 0.48)';
              }
            }}
            linkWidth={(link: any) => {
              try {
                if (isPathLink(link)) return 5.2;
                const type = link?.type || 'RELATED_TO';
                return type === 'PREREQUISITE_OF' || type === 'PREREQUISITE' ? 4.2 : 3.0;
              } catch (err) {
                return 3.0;
              }
            }}
            linkCurvature={0.15}
            linkDirectionalArrowLength={8}
            cooldownTicks={graphMode === 'path' ? 0 : 400}
            d3AlphaDecay={0.015}
            d3VelocityDecay={0.35}
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
                return isPathLink(link) ? 2.8 : 1.4;
              } catch (err) {
                return 1.4;
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
                  fgRef.current.zoomToFit(600, 140);
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
                
                // Font size bounded 9-14px — prevents overwhelming text at zoom-out
                const scale = typeof globalScale === 'number' && !isNaN(globalScale) && globalScale > 0 ? globalScale : 1;
                const fontSize = Math.min(14, Math.max(9, 12 / Math.sqrt(scale)));
                const rawDegree = (nodeDegrees && node.id) ? (nodeDegrees[node.id] || 0) : 0;
                const degree = typeof rawDegree === 'number' && !isNaN(rawDegree) && rawDegree >= 0 ? rawDegree : 0;
                const radius = 4 + Math.sqrt(degree) * 1.8;

                const isSelected = selectedNode?.id === node.id;
                const isPathNode = !!(activePathNodeIds && activePathNodeIds.includes(node.id));
                const shouldShowLabel = scale >= 0.55 || isSelected || isPathNode;
                const color = getNodeColor(node.label);

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

                // Label text below node — only show when zoomed in, or for selected/path nodes
                if (shouldShowLabel) {
                  ctx.font = `${fontSize}px Outfit, system-ui, sans-serif`;
                  ctx.textAlign = 'center';
                  ctx.textBaseline = 'top';
                  const textWidth = ctx.measureText(label).width;
                  ctx.fillStyle = 'rgba(3, 12, 11, 0.92)';
                  ctx.fillRect(x - textWidth / 2 - 3, y + radius + 2, textWidth + 6, fontSize + 2);
                  ctx.fillStyle = isSelected || isPathNode ? '#ffffff' : '#cbd5e1';
                  ctx.fillText(label, x, y + radius + 3);
                }
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

      {safeNodes.length > 0 && (
        <div className="absolute bottom-4 right-4 z-20 w-[180px] rounded-xl bg-[#031412]/92 backdrop-blur-lg border border-cyan-500/20 shadow-[0_0_18px_rgba(6,182,212,0.08)] overflow-hidden">
          <div className="flex items-center justify-between px-3 py-2 border-b border-cyan-500/10">
            <span className="flex items-center gap-1.5 text-[9px] font-mono font-bold uppercase tracking-widest text-cyan-300/80">
              <MapPin className="w-3.5 h-3.5" /> Minimap
            </span>
            <button
              onClick={() => setShowMiniMap(!showMiniMap)}
              className="text-[9px] font-bold uppercase tracking-wider text-slate-400 hover:text-cyan-300"
            >
              {showMiniMap ? 'Hide' : 'Show'}
            </button>
          </div>
          {showMiniMap && (
            <>
              <svg viewBox="0 0 160 110" className="w-full h-[120px] bg-[#010807]/70">
                {validatedGraphData.links.slice(0, 240).map((link: any, idx: number) => {
                  const fromId = typeof link.source === 'object' ? link.source?.id : link.source;
                  const toId = typeof link.target === 'object' ? link.target?.id : link.target;
                  const a = minimapNodes.find(p => p.node.id === fromId);
                  const b = minimapNodes.find(p => p.node.id === toId);
                  if (!a || !b) return null;
                  return (
                    <line
                      key={`${fromId}-${toId}-${idx}`}
                      x1={a.x}
                      y1={a.y}
                      x2={b.x}
                      y2={b.y}
                      stroke={getLinkColor(link.type)}
                      strokeWidth="0.8"
                      opacity="0.55"
                    />
                  );
                })}
                {minimapNodes.slice(0, 180).map(({ node, x, y }) => (
                  <circle
                    key={node.id}
                    cx={x}
                    cy={y}
                    r={selectedNode?.id === node.id ? 3.4 : 2.2}
                    fill={getNodeColor(node.label)}
                    stroke={selectedNode?.id === node.id ? '#ffffff' : 'transparent'}
                    strokeWidth="1"
                    className="cursor-pointer"
                    onClick={() => jumpToNode(node as GraphNode)}
                  />
                ))}
              </svg>
              <div className="grid grid-cols-2 gap-1 px-3 pb-2 text-[8px] font-mono uppercase tracking-wider text-slate-400">
                <span><i className="inline-block w-2 h-2 rounded-full bg-cyan-400 mr-1" />Concept</span>
                <span><i className="inline-block w-2 h-2 rounded-full bg-amber-500 mr-1" />Topic</span>
                <span><i className="inline-block w-2 h-2 rounded-full bg-violet-500 mr-1" />Paper</span>
                <span><i className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1" />Method</span>
              </div>
            </>
          )}
        </div>
      )}

      {/* HUD Info */}
      <div className="absolute bottom-4 left-4 z-10 pointer-events-none">
        <div className="text-[9px] font-mono font-bold text-cyan-500/40 uppercase tracking-widest">
          Nodes: {validatedGraphData.nodes.length} | Edges: {validatedGraphData.links.length}
        </div>
      </div>

      <LearningRoadmapOverlay
        isOpen={isOverlayOpen}
        selectedNode={selectedNode}
        roadmap={roadmapData}
        onClose={() => setIsOverlayOpen(false)}
        onLearnThis={async (node, e) => {
          setIsOverlayOpen(false);
          
          const conceptName = node.name;
          const fallbackId = node.id || `roadmap-${conceptName}`;

          // Immediately update state with basic info so it doesn't crash the panel
          const basicNode = {
            ...node,
            id: fallbackId,
            label: node.label || 'Concept',
            name: conceptName,
            description: node.description || '',
            difficulty_level: node.difficulty_level || 'Beginner',
          } as GraphNode;
          
          setSelectedNode(basicNode);

          try {
            // Trigger API fetch to concept explainer endpoint
            const detailsUrl = `${API_BASE_URL}/graph/node/${fallbackId}?document_id=${activeDocumentId || 'doc-1'}`;
            const detailsRes = await fetch(detailsUrl);
            
            if (detailsRes.ok) {
              const detailsData = await detailsRes.json();
              // Feed that data directly into the active 'AI Detail Panel' state
              setSelectedNode(detailsData);
              
              // Find in graph and center if it exists
              const foundNode = nodes.find((n: any) => n.id === detailsData.id || n.name === conceptName);
              if (foundNode && fgRef.current) {
                fgRef.current.centerAt(foundNode.x, foundNode.y, 800);
                fgRef.current.zoom(2.5, 800);
              }
            } else {
              console.error(`Failed to load concept explainer details (HTTP ${detailsRes.status})`);
            }
          } catch (err) {
            console.error('Failed to retrieve concept explainer details', err);
          }
        }}
      />

      {roadmapLoading && isOverlayOpen && (
        <div className="absolute inset-0 z-[60] flex flex-col items-center justify-center bg-[#010605]/80 backdrop-blur-sm rounded-2xl">
          <Loader2 className="w-10 h-10 animate-spin text-cyan-400 mb-4" />
          <p className="text-cyan-400 font-mono tracking-widest text-sm animate-pulse uppercase">Fetching Roadmap...</p>
        </div>
      )}
    </div>
  );
}
