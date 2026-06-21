import { create } from 'zustand';

export interface GraphNode {
  id: string;
  label: string;
  name: string;
  description: string;
  difficulty_level: string;
  x?: number;
  y?: number;
}

export interface GraphEdge {
  from: string;
  to: string;
  type: string;
  source?: string | GraphNode;
  target?: string | GraphNode;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface User {
  email: string;
  role: 'student' | 'researcher';
}

interface DocumentInfo {
  id: string;
  title: string;
  status: string;
  progress_pct: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface AppState {
  // Auth state
  user: User | null;
  login: (email: string, role: 'student' | 'researcher') => void;
  logout: () => void;

  // Graph state
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNode: GraphNode | null;
  setSelectedNode: (node: GraphNode | null) => void;
  graphDepth: number;
  setGraphDepth: (depth: number) => void;
  graphMode: 'basic' | 'advanced';
  setGraphMode: (mode: 'basic' | 'advanced') => void;
  setGraphData: (data: GraphData) => void;
  appendGraphData: (data: GraphData) => void;

  // Documents state
  activeDocumentId: string | null;
  setActiveDocumentId: (docId: string | null) => void;
  documents: DocumentInfo[];
  addDocument: (doc: DocumentInfo) => void;
  updateDocumentStatus: (id: string, status: string, progress_pct: number) => void;

  // Chat state
  chatMessages: ChatMessage[];
  chatLoading: boolean;
  addChatMessage: (msg: ChatMessage) => void;
  updateLastChatMessage: (content: string) => void;
  setChatLoading: (loading: boolean) => void;
  clearChat: () => void;

  // Highlights, Notes & Doc Text (Sprint 4)
  activeTab: 'map' | 'text';
  setActiveTab: (tab: 'map' | 'text') => void;
  documentText: string | null;
  setDocumentText: (text: string | null) => void;
  notes: NoteInfo[];
  setNotes: (notes: NoteInfo[]) => void;
  addNote: (note: NoteInfo) => void;
  highlights: HighlightInfo[];
  setHighlights: (highlights: HighlightInfo[]) => void;
  addHighlight: (highlight: HighlightInfo) => void;
}

export interface NoteInfo {
  id: string;
  content: string;
  created_at: string;
  concepts?: string[];
}

export interface HighlightInfo {
  id: string;
  text: string;
  page: number;
  doc_title: string;
}

export const useStore = create<AppState>((set) => ({
  // Auth state: Logged in by default with a mock student user
  user: { email: 'student@mindmesh.ai', role: 'student' },
  login: (email, role) => set({ user: { email, role } }),
  logout: () => set({ user: null }),

  // Graph state
  nodes: [],
  edges: [],
  selectedNode: null,
  setSelectedNode: (node) => set({ selectedNode: node }),
  graphDepth: 1,
  setGraphDepth: (depth) => set({ graphDepth: depth }),
  graphMode: 'basic',
  setGraphMode: (mode) => set({ graphMode: mode }),
  setGraphData: (data) => set({ nodes: data.nodes, edges: data.edges }),
  appendGraphData: (data) => set((state) => {
    // Deduplicate nodes
    const nodeMap = new Map(state.nodes.map(n => [n.id, n]));
    data.nodes.forEach(n => nodeMap.set(n.id, n));
    
    // Deduplicate edges
    const getEdgeId = (e: GraphEdge) => {
      const fromId = typeof e.source === 'object' ? e.source.id : e.source || e.from;
      const toId = typeof e.target === 'object' ? e.target.id : e.target || e.to;
      return `${fromId}-${toId}-${e.type}`;
    };
    
    const edgeKeys = new Set(state.edges.map(getEdgeId));
    const newEdges = [...state.edges];
    data.edges.forEach(e => {
      const key = getEdgeId(e);
      if (!edgeKeys.has(key)) {
        newEdges.push(e);
        edgeKeys.add(key);
      }
    });
    
    return {
      nodes: Array.from(nodeMap.values()),
      edges: newEdges
    };
  }),

  // Documents state
  activeDocumentId: null,
  setActiveDocumentId: (docId) => set({ activeDocumentId: docId }),
  documents: [],
  addDocument: (doc) => set((state) => ({ documents: [doc, ...state.documents] })),
  updateDocumentStatus: (id, status, progress_pct) => set((state) => ({
    documents: state.documents.map((doc) =>
      doc.id === id ? { ...doc, status, progress_pct } : doc
    )
  })),

  // Chat state
  chatMessages: [],
  chatLoading: false,
  addChatMessage: (msg) => set((state) => ({ chatMessages: [...state.chatMessages, msg] })),
  updateLastChatMessage: (content) => set((state) => {
    const updated = [...state.chatMessages];
    if (updated.length > 0 && updated[updated.length - 1].role === 'assistant') {
      updated[updated.length - 1] = {
        ...updated[updated.length - 1],
        content: updated[updated.length - 1].content + content
      };
    }
    return { chatMessages: updated };
  }),
  setChatLoading: (loading) => set({ chatLoading: loading }),
  clearChat: () => set({ chatMessages: [] }),

  // Highlights, Notes & Doc Text states (Sprint 4)
  activeTab: 'map',
  setActiveTab: (tab) => set({ activeTab: tab }),
  documentText: null,
  setDocumentText: (text) => set({ documentText: text }),
  notes: [],
  setNotes: (notes) => set({ notes }),
  addNote: (note) => set((state) => ({ notes: [note, ...state.notes] })),
  highlights: [],
  setHighlights: (highlights) => set({ highlights }),
  addHighlight: (highlight) => set((state) => ({ highlights: [highlight, ...state.highlights] })),
}));
