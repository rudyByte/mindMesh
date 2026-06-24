import { create } from 'zustand';
import { API_BASE_URL } from '../lib/api';

export interface GraphNode {
  id: string;
  label: string;
  name: string;
  description: string;
  difficulty_level: string;
  x?: number;
  y?: number;
  doc_id?: string;
  session_id?: string;
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

  // Session state
  sessionId: string | null;
  sessionsList: Array<{ id: string, name: string; created_at?: number }>;
  initSessions: () => void;
  createSession: (name?: string) => void;
  switchSession: (id: string) => void;
  deleteSession: (id: string) => void;
  reloadSessionData: (id: string) => Promise<void>;

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
  graphFilter: string | null;
  setGraphFilter: (filter: string | null) => void;

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

  // Citations & Learning Paths (Sprint 5)
  citations: CitationInfo[];
  setCitations: (citations: CitationInfo[]) => void;
  addCitation: (citation: CitationInfo) => void;
  activePathNodeIds: string[];
  setActivePathNodeIds: (ids: string[]) => void;
  learningPathNarration: string | null;
  setLearningPathNarration: (narration: string | null) => void;
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

export interface CitationInfo {
  id: string;
  formatted_text: string;
  style: string;
  paper_title: string;
}

const saveSessionLocal = (id: string | null, data: any) => {
  if (!id || typeof window === 'undefined') return;
  try {
    const key = `mindmesh_session_data_${id}`;
    const stored = localStorage.getItem(key);
    const parsed = stored ? JSON.parse(stored) : {};
    const updated = { ...parsed, ...data };
    localStorage.setItem(key, JSON.stringify(updated));
  } catch (err) {
    console.error('Failed to save session data to local storage:', err);
  }
};

export const useStore = create<AppState>((set) => ({
  // Auth state: Logged in by default with a mock student user
  user: { email: 'student@mindmesh.ai', role: 'student' },
  login: (email, role) => set({ user: { email, role } }),
  logout: () => set({ user: null }),

  // Session state
  sessionId: null,
  sessionsList: [],

  initSessions: () => {
    if (typeof window === 'undefined') return;
    try {
      const storedList = localStorage.getItem('mindmesh_sessions_list');
      let list = storedList ? JSON.parse(storedList) : [];
      
      // If list is empty, initialize with default pre-seeded session
      if (list.length === 0) {
        list = [{ id: 'session-1', name: 'Session 1', created_at: Date.now() }];
        localStorage.setItem('mindmesh_sessions_list', JSON.stringify(list));
      }
      
      // Deduplicate sessions list by ID
      const seenIds = new Set<string>();
      list = list.filter((s: any) => {
        if (!s || !s.id) return false;
        if (seenIds.has(s.id)) return false;
        seenIds.add(s.id);
        return true;
      });

      // Ensure every session has a created_at timestamp
      list = list.map((s: any, idx: number) => {
        if (s.created_at === undefined) {
          s.created_at = s.id === 'session-1' ? 0 : Date.now() - (list.length - idx) * 1000;
        }
        return s;
      });

      // Overwrite/update each session's display name using its first uploaded document title
      list = list.map((s: any) => {
        const storedData = localStorage.getItem(`mindmesh_session_data_${s.id}`);
        if (storedData) {
          try {
            const sessionData = JSON.parse(storedData);
            if (sessionData.documents && sessionData.documents.length > 0) {
              s.name = sessionData.documents[0].title;
            } else {
              if (!s.name || s.name === 'MachineLearningTextbook.pdf') {
                s.name = s.id === 'session-1' ? 'Session 1' : 'Untitled Session';
              }
            }
          } catch (e) {
            console.error('Failed to parse session data for naming', e);
          }
        } else {
          if (!s.name || s.name === 'MachineLearningTextbook.pdf') {
            s.name = s.id === 'session-1' ? 'Session 1' : 'Untitled Session';
          }
        }
        return s;
      });

      // Sort by newest first (created_at descending)
      list.sort((a: any, b: any) => (b.created_at || 0) - (a.created_at || 0));
      localStorage.setItem('mindmesh_sessions_list', JSON.stringify(list));
      
      const storedActiveId = localStorage.getItem('mindmesh_active_session_id');
      const activeId = storedActiveId && list.some((s: any) => s.id === storedActiveId) ? storedActiveId : list[0].id;
      
      localStorage.setItem('mindmesh_active_session_id', activeId);
      
      // Load session specific data
      let storedData = localStorage.getItem(`mindmesh_session_data_${activeId}`);
      if (activeId === 'session-1' && !storedData) {
        const defaultSessionData = {
          documents: [],
          chatMessages: [],
          notes: [],
          highlights: [],
          citations: [],
          activeDocumentId: null
        };
        localStorage.setItem('mindmesh_session_data_session-1', JSON.stringify(defaultSessionData));
        storedData = JSON.stringify(defaultSessionData);
      }

      const sessionData = storedData ? JSON.parse(storedData) : null;
      
      set({
        sessionId: activeId,
        sessionsList: list,
        documents: sessionData?.documents || [],
        chatMessages: sessionData?.chatMessages || [],
        notes: sessionData?.notes || [],
        highlights: sessionData?.highlights || [],
        citations: sessionData?.citations || [],
        activeDocumentId: sessionData?.activeDocumentId || null,
        selectedNode: null,
        activePathNodeIds: [],
        learningPathNarration: null,
        nodes: [],
        edges: []
      });

      // Trigger load of correct data from backend
      useStore.getState().reloadSessionData(activeId);
    } catch (err) {
      console.error('Failed to initialize sessions:', err);
    }
  },

  createSession: (name) => {
    if (typeof window === 'undefined') return;
    try {
      const storedList = localStorage.getItem('mindmesh_sessions_list');
      let list = storedList ? JSON.parse(storedList) : [];
      
      const newId = crypto.randomUUID();
      const newName = name || 'Untitled Session';
      const updatedList = [...list, { id: newId, name: newName, created_at: Date.now() }];
      
      // Deduplicate
      const seenIds = new Set<string>();
      let dedupedList = updatedList.filter((s: any) => {
        if (!s || !s.id) return false;
        if (seenIds.has(s.id)) return false;
        seenIds.add(s.id);
        return true;
      });

      // Sort
      dedupedList.sort((a: any, b: any) => (b.created_at || 0) - (a.created_at || 0));

      localStorage.setItem('mindmesh_sessions_list', JSON.stringify(dedupedList));
      localStorage.setItem('mindmesh_active_session_id', newId);
      
      // Save blank data for the new session
      const newSessionData = {
        documents: [],
        chatMessages: [],
        notes: [],
        highlights: [],
        citations: [],
        activeDocumentId: null
      };
      localStorage.setItem(`mindmesh_session_data_${newId}`, JSON.stringify(newSessionData));
      
      set({
        sessionId: newId,
        sessionsList: dedupedList,
        documents: [],
        chatMessages: [],
        notes: [],
        highlights: [],
        citations: [],
        activeDocumentId: null,
        selectedNode: null,
        activePathNodeIds: [],
        learningPathNarration: null,
        nodes: [],
        edges: []
      });
    } catch (err) {
      console.error('Failed to create session:', err);
    }
  },

  switchSession: (id) => {
    if (typeof window === 'undefined') return;
    try {
      const storedList = localStorage.getItem('mindmesh_sessions_list');
      const list = storedList ? JSON.parse(storedList) : [];
      if (!list.some((s: any) => s.id === id)) return;
      
      localStorage.setItem('mindmesh_active_session_id', id);
      
      // Load session specific data
      const storedData = localStorage.getItem(`mindmesh_session_data_${id}`);
      const sessionData = storedData ? JSON.parse(storedData) : null;
      
      set({
        sessionId: id,
        sessionsList: list,
        documents: sessionData?.documents || [],
        chatMessages: sessionData?.chatMessages || [],
        notes: sessionData?.notes || [],
        highlights: sessionData?.highlights || [],
        citations: sessionData?.citations || [],
        activeDocumentId: sessionData?.activeDocumentId || null,
        selectedNode: null,
        activePathNodeIds: [],
        learningPathNarration: null,
        nodes: [],
        edges: []
      });

      // Trigger load of correct data from backend
      useStore.getState().reloadSessionData(id);
    } catch (err) {
      console.error('Failed to switch session:', err);
    }
  },

  deleteSession: async (id) => {
    if (typeof window === 'undefined') return;
    try {
      const storedList = localStorage.getItem('mindmesh_sessions_list');
      const list = storedList ? JSON.parse(storedList) : [];
      
      // Prevent deleting the last session
      if (list.length <= 1) return;

      // Call backend DELETE API
      try {
        await fetch(`${API_BASE_URL}/sessions/${id}`, { method: 'DELETE' });
      } catch (backendErr) {
        console.error('Failed to delete session on backend:', backendErr);
      }
      
      const updatedList = list.filter((s: any) => s.id !== id);
      localStorage.setItem('mindmesh_sessions_list', JSON.stringify(updatedList));
      localStorage.removeItem(`mindmesh_session_data_${id}`);
      
      const storedActiveId = localStorage.getItem('mindmesh_active_session_id');
      if (storedActiveId === id) {
        const nextActiveId = updatedList[0].id;
        localStorage.setItem('mindmesh_active_session_id', nextActiveId);
        
        const storedData = localStorage.getItem(`mindmesh_session_data_${nextActiveId}`);
        const sessionData = storedData ? JSON.parse(storedData) : null;
        
        set({
          sessionId: nextActiveId,
          sessionsList: updatedList,
          documents: sessionData?.documents || [],
          chatMessages: sessionData?.chatMessages || [],
          notes: sessionData?.notes || [],
          highlights: sessionData?.highlights || [],
          citations: sessionData?.citations || [],
          activeDocumentId: sessionData?.activeDocumentId || null,
          selectedNode: null,
          activePathNodeIds: [],
          learningPathNarration: null,
          nodes: [],
          edges: []
        });

        // Trigger load of correct data from backend
        useStore.getState().reloadSessionData(nextActiveId);
      } else {
        set({ sessionsList: updatedList });
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  },

  reloadSessionData: async (id) => {
    if (!id) return;
    try {
      // 1. Fetch graph
      const graphRes = await fetch(`${API_BASE_URL}/sessions/${id}/graph`);
      if (graphRes.ok) {
        const data = await graphRes.json();
        set({ nodes: data.nodes || [], edges: data.edges || [] });
      }

      // 2. Fetch notes
      const notesRes = await fetch(`${API_BASE_URL}/notes?session_id=${id}`);
      if (notesRes.ok) {
        const data = await notesRes.json();
        set({ notes: data || [] });
      }

      // 3. Fetch highlights
      const highlightsRes = await fetch(`${API_BASE_URL}/highlights?session_id=${id}`);
      if (highlightsRes.ok) {
        const data = await highlightsRes.json();
        set({ highlights: data || [] });
      }

      // 4. Fetch citations
      const citationsRes = await fetch(`${API_BASE_URL}/citations?session_id=${id}`);
      if (citationsRes.ok) {
        const data = await citationsRes.json();
        set({ citations: data || [] });
      }
    } catch (err) {
      console.error('Failed to reload session data:', err);
    }
  },


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
  graphFilter: null,
  setGraphFilter: (filter) => set({ graphFilter: filter }),
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
  setActiveDocumentId: (docId) => set((state) => {
    saveSessionLocal(state.sessionId, { activeDocumentId: docId });
    return { activeDocumentId: docId };
  }),
  documents: [],
  addDocument: (doc) => set((state) => {
    const docs = [doc, ...state.documents];
    saveSessionLocal(state.sessionId, { documents: docs });

    // Update the session name in sessionsList
    const updatedList = state.sessionsList.map(s => {
      if (s.id === state.sessionId) {
        return { ...s, name: doc.title };
      }
      return s;
    });
    localStorage.setItem('mindmesh_sessions_list', JSON.stringify(updatedList));

    return { documents: docs, sessionsList: updatedList };
  }),
  updateDocumentStatus: (id, status, progress_pct) => set((state) => {
    const docs = state.documents.map((doc) =>
      doc.id === id ? { ...doc, status, progress_pct } : doc
    );
    saveSessionLocal(state.sessionId, { documents: docs });
    return { documents: docs };
  }),

  // Chat state
  chatMessages: [],
  chatLoading: false,
  addChatMessage: (msg) => set((state) => {
    const msgs = [...state.chatMessages, msg];
    saveSessionLocal(state.sessionId, { chatMessages: msgs });
    return { chatMessages: msgs };
  }),
  updateLastChatMessage: (content) => set((state) => {
    const updated = [...state.chatMessages];
    if (updated.length > 0 && updated[updated.length - 1].role === 'assistant') {
      updated[updated.length - 1] = {
        ...updated[updated.length - 1],
        content: updated[updated.length - 1].content + content
      };
    }
    saveSessionLocal(state.sessionId, { chatMessages: updated });
    return { chatMessages: updated };
  }),
  setChatLoading: (loading) => set({ chatLoading: loading }),
  clearChat: () => set((state) => {
    saveSessionLocal(state.sessionId, { chatMessages: [] });
    return { chatMessages: [] };
  }),

  // Highlights, Notes & Doc Text states (Sprint 4)
  activeTab: 'map',
  setActiveTab: (tab) => set({ activeTab: tab }),
  documentText: null,
  setDocumentText: (text) => set({ documentText: text }),
  notes: [],
  setNotes: (notes) => set((state) => {
    saveSessionLocal(state.sessionId, { notes: notes });
    return { notes: notes };
  }),
  addNote: (note) => set((state) => {
    const notes = [note, ...state.notes];
    saveSessionLocal(state.sessionId, { notes: notes });
    return { notes: notes };
  }),
  highlights: [],
  setHighlights: (highlights) => set((state) => {
    saveSessionLocal(state.sessionId, { highlights: highlights });
    return { highlights: highlights };
  }),
  addHighlight: (highlight) => set((state) => {
    const highlights = [highlight, ...state.highlights];
    saveSessionLocal(state.sessionId, { highlights: highlights });
    return { highlights: highlights };
  }),

  // Citations & Learning Paths states (Sprint 5)
  citations: [],
  setCitations: (citations) => set((state) => {
    saveSessionLocal(state.sessionId, { citations: citations });
    return { citations: citations };
  }),
  addCitation: (citation) => set((state) => {
    const citations = [citation, ...state.citations];
    saveSessionLocal(state.sessionId, { citations: citations });
    return { citations: citations };
  }),
  activePathNodeIds: [],
  setActivePathNodeIds: (ids) => set({ activePathNodeIds: ids }),
  learningPathNarration: null,
  setLearningPathNarration: (narration) => set({ learningPathNarration: narration }),
}));
