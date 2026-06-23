'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useStore, GraphNode } from '../store/useStore';
import { API_BASE_URL } from '../lib/api';
import { 
  FileText, Plus, Database, Cpu, HelpCircle, 
  Map, Sparkles, BookOpen, GraduationCap, 
  ArrowRight, Landmark, Tag, ChevronDown, ChevronUp, UserCheck,
  Copy, Check, Bookmark, X, ChevronRight, Send, Trash, Loader2
} from 'lucide-react';

// ==================== LEFT SIDEBAR ====================
// ==================== LEFT SIDEBAR ====================
interface LeftSidebarProps {
  onOpenUpload: () => void;
}

export function LeftSidebar({ onOpenUpload }: LeftSidebarProps) {
  const documents = useStore((state) => state.documents);
  const activeDocumentId = useStore((state) => state.activeDocumentId);
  const setActiveDocumentId = useStore((state) => state.setActiveDocumentId);
  const setGraphData = useStore((state) => state.setGraphData);
  const user = useStore((state) => state.user);

  // Notes state (Sprint 4)
  const notes = useStore((state) => state.notes);
  const setNotes = useStore((state) => state.setNotes);
  const addNote = useStore((state) => state.addNote);
  
  // Citations state (Sprint 5)
  const citations = useStore((state) => state.citations);
  const setCitations = useStore((state) => state.setCitations);
  const [copiedCitationId, setCopiedCitationId] = useState<string | null>(null);
  const [citationsLoading, setCitationsLoading] = useState(false);

  const [activeNavTab, setActiveNavTab] = useState<'navigation' | 'notes' | 'citations'>('navigation');
  const [noteSearch, setNoteSearch] = useState('');
  const [noteInput, setNoteInput] = useState('');
  const [noteSubmitLoading, setNoteSubmitLoading] = useState(false);

  // Health check state (Sprint 6)
  const [healthStatus, setHealthStatus] = useState<{
    neo4j: { status: string; mode: string };
    supabase: { status: string; mode: string };
    anthropic: { status: string; mode: string };
  } | null>(null);

  // Fetch health status
  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/health/deep`);
        if (response.ok) {
          const data = await response.json();
          setHealthStatus(data.services);
        }
      } catch (err) {
        console.error('Failed to fetch system health status', err);
      }
    };
    
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000); // Check every 15s
    return () => clearInterval(interval);
  }, []);

  // Fetch notes on load
  useEffect(() => {
    const fetchNotes = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/notes`);
        if (response.ok) {
          const data = await response.json();
          setNotes(data);
        }
      } catch (err) {
        console.error('Failed to load notes', err);
      }
    };
    fetchNotes();
  }, [setNotes]);

  // Fetch citations on load
  useEffect(() => {
    const fetchCitations = async () => {
      setCitationsLoading(true);
      try {
        const response = await fetch(`${API_BASE_URL}/citations`);
        if (response.ok) {
          const data = await response.json();
          setCitations(data);
        }
      } catch (err) {
        console.error('Failed to load citations', err);
      } finally {
        setCitationsLoading(false);
      }
    };
    fetchCitations();
  }, [setCitations]);

  const handleDocumentSelect = async (docId: string) => {
    setActiveDocumentId(docId);
    try {
      const response = await fetch(`${API_BASE_URL}/documents/${docId}/graph`);
      if (response.ok) {
        const data = await response.json();
        setGraphData(data);
      }
    } catch (err) {
      console.error('Failed to load document graph', err);
    }
  };

  const handleNoteSearchChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const q = e.target.value;
    setNoteSearch(q);
    try {
      const url = q.trim()
        ? `${API_BASE_URL}/notes/search?q=${encodeURIComponent(q)}`
        : `${API_BASE_URL}/notes`;
      const response = await fetch(url);
      if (response.ok) {
        const data = await response.json();
        setNotes(data);
      }
    } catch (err) {
      console.error('Failed to search notes', err);
    }
  };

  const handleAddNote = async () => {
    if (!noteInput.trim()) return;
    setNoteSubmitLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/notes`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content: noteInput }),
      });
      if (response.ok) {
        const data = await response.json();
        addNote(data);
        setNoteInput('');
        
        // Refresh graph to show newly added Note node & links
        if (activeDocumentId) {
          handleDocumentSelect(activeDocumentId);
        }
      }
    } catch (err) {
      console.error('Failed to save note', err);
    } finally {
      setNoteSubmitLoading(false);
    }
  };

  return (
    <aside className="w-60 h-full flex flex-col glass-panel border-r border-slate-800 bg-[#0d1323]/80 select-none">
      {/* Brand Logo */}
      <div className="p-4 border-b border-slate-800 flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-md glow-active">
          <Database className="w-4.5 h-4.5" />
        </div>
        <div>
          <h1 className="font-extrabold text-sm text-white tracking-wider">MINDMESH</h1>
          <p className="text-[10px] text-indigo-400 font-bold tracking-widest">KNOWLEDGE GRAPH</p>
        </div>
      </div>

      {/* User Session Badge */}
      <div className="px-4 py-3 border-b border-slate-800/60 flex items-center justify-between bg-slate-900/20">
        <div className="flex items-center gap-2">
          <UserCheck className="w-4 h-4 text-emerald-400" />
          <div className="min-w-0">
            <p className="text-xs font-semibold text-slate-300 truncate">{user?.email || 'Guest User'}</p>
            <p className="text-[9px] text-slate-500 font-medium capitalize">{user?.role || 'student'}</p>
          </div>
        </div>
      </div>

      {/* Nav Selector Tabs */}
      <div className="px-3 pt-3 flex gap-1 border-b border-slate-800/40 pb-2">
        <button
          onClick={() => setActiveNavTab('navigation')}
          className={`flex-1 py-1.5 text-[10px] font-extrabold rounded-lg uppercase tracking-wider transition-colors ${
            activeNavTab === 'navigation'
              ? 'bg-slate-800 text-slate-100 border border-slate-700/60'
              : 'text-slate-500 hover:text-slate-300'
          }`}
        >
          Index
        </button>
        <button
          onClick={() => setActiveNavTab('notes')}
          className={`flex-1 py-1.5 text-[10px] font-extrabold rounded-lg uppercase tracking-wider transition-colors ${
            activeNavTab === 'notes'
              ? 'bg-slate-800 text-slate-100 border border-slate-700/60'
              : 'text-slate-500 hover:text-slate-300'
          }`}
        >
          Notes ({notes.length})
        </button>
        <button
          onClick={() => setActiveNavTab('citations')}
          className={`flex-1 py-1.5 text-[10px] font-extrabold rounded-lg uppercase tracking-wider transition-colors ${
            activeNavTab === 'citations'
              ? 'bg-slate-800 text-slate-100 border border-slate-700/60'
              : 'text-slate-500 hover:text-slate-300'
          }`}
        >
          Citations ({citations.length})
        </button>
      </div>

      {/* Main navigation area */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {activeNavTab === 'navigation' && (
          <div className="p-2.5 space-y-4">
            {/* Ingest Actions */}
            <div>
              <button
                onClick={onOpenUpload}
                className="w-full py-2 px-3.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white rounded-xl font-bold text-xs flex items-center justify-center gap-2 shadow-lg hover:shadow-indigo-500/25 transition-all duration-200"
              >
                <Plus className="w-4 h-4" />
                Ingest Document
              </button>
            </div>

            {/* Navigation options */}
            <nav className="space-y-1">
              <div className="text-[10px] text-slate-500 font-bold px-2 py-1 tracking-wider">SECTIONS</div>
              <a href="#" className="flex items-center gap-2.5 px-3 py-2 text-xs font-bold text-slate-300 bg-white/5 rounded-lg border border-white/5"><GraduationCap className="w-4 h-4 text-indigo-400" /> Concepts</a>
              <a href="#" className="flex items-center gap-2.5 px-3 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 hover:bg-white/5 rounded-lg transition-colors"><BookOpen className="w-4 h-4" /> Papers</a>
              <a href="#" className="flex items-center gap-2.5 px-3 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 hover:bg-white/5 rounded-lg transition-colors"><Landmark className="w-4 h-4" /> Authors</a>
              <a href="#" className="flex items-center gap-2.5 px-3 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 hover:bg-white/5 rounded-lg transition-colors"><Tag className="w-4 h-4" /> Keywords</a>
              <a href="#" className="flex items-center gap-2.5 px-3 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 hover:bg-white/5 rounded-lg transition-colors"><Map className="w-4 h-4" /> Learning Paths</a>
            </nav>

            {/* Documents Queue */}
            <div className="space-y-1">
              <div className="text-[10px] text-slate-500 font-bold px-2 py-1 tracking-wider">DOCUMENTS QUEUE</div>
              {documents.length === 0 ? (
                <div className="px-3 py-4 text-center rounded-lg border border-dashed border-slate-800 text-[10px] text-slate-500 font-medium">
                  No documents ingested yet.
                </div>
              ) : (
                documents.map((doc) => (
                  <button
                    key={doc.id}
                    onClick={() => handleDocumentSelect(doc.id)}
                    className={`w-full text-left px-3 py-2 rounded-lg flex flex-col gap-1 border transition-all ${
                      activeDocumentId === doc.id
                        ? 'bg-indigo-500/10 border-indigo-500/30 text-slate-100'
                        : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/5'
                    }`}
                  >
                    <div className="flex items-center gap-2 w-full">
                      <FileText className="w-3.5 h-3.5 text-indigo-400 flex-shrink-0" />
                      <span className="text-[11px] font-semibold truncate flex-1">{doc.title}</span>
                    </div>
                    {doc.status !== 'done' && (
                      <div className="w-full bg-slate-800 h-1 rounded-full overflow-hidden mt-1">
                        <div 
                          className={`h-full rounded-full ${doc.status === 'error' ? 'bg-rose-500' : 'bg-indigo-500'}`}
                          style={{ width: `${doc.progress_pct}%` }}
                        />
                      </div>
                    )}
                  </button>
                ))
              )}
            </div>
          </div>
        )}

        {activeNavTab === 'notes' && (
          /* Notes Composer & List (Sprint 4) */
          <div className="p-3 space-y-4">
            {/* Notes Search */}
            <input
              type="text"
              value={noteSearch}
              onChange={handleNoteSearchChange}
              placeholder="Search notes & links..."
              className="w-full px-3 py-1.5 rounded-lg bg-slate-950/60 border border-slate-800 text-[11px] text-slate-200 focus:outline-none focus:border-indigo-500/50"
            />

            {/* Note Composer */}
            <div className="space-y-2">
              <textarea
                value={noteInput}
                onChange={(e) => setNoteInput(e.target.value)}
                placeholder="Write a personal note..."
                className="w-full h-20 p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-[11px] text-slate-300 focus:outline-none focus:border-indigo-500/50 resize-none font-medium leading-relaxed"
              />
              <button
                disabled={noteSubmitLoading || !noteInput.trim()}
                onClick={handleAddNote}
                className="w-full py-1.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:bg-slate-800 text-white rounded-lg font-bold text-[10px] uppercase tracking-wider flex items-center justify-center gap-1.5 shadow-md"
              >
                {noteSubmitLoading ? 'Saving...' : 'Add Note'}
              </button>
            </div>

            {/* Scrollable list of Notes */}
            <div className="space-y-2.5 pt-2">
              <div className="text-[10px] text-slate-500 font-bold tracking-wider">SAVED NOTES</div>
              {notes.length === 0 ? (
                <div className="text-center py-6 text-[10px] text-slate-500 border border-dashed border-slate-800/60 rounded-lg font-medium">
                  No notes saved yet. Write a personal note above to capture insights.
                </div>
              ) : (
                notes.map((note) => (
                  <div key={note.id} className="p-2.5 rounded-lg bg-slate-900/55 border border-slate-800/70 space-y-2">
                    <p className="text-[11px] text-slate-300 font-medium leading-relaxed whitespace-pre-wrap">{note.content}</p>
                    {note.concepts && note.concepts.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {note.concepts.map((c: string, idx: number) => (
                          <span key={idx} className="bg-indigo-500/10 text-indigo-300 border border-indigo-500/10 px-1.5 py-0.5 rounded text-[8px] font-bold">
                            {c}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {activeNavTab === 'citations' && (
          /* Citations Library (Sprint 5) */
          <div className="p-3 space-y-4">
            <div className="space-y-2.5">
              <div className="text-[10px] text-slate-500 font-bold tracking-wider uppercase">Saved Citations</div>
              {citationsLoading ? (
                <div className="space-y-2.5">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="p-3 rounded-lg bg-slate-900/30 border border-slate-800/50 space-y-2.5 animate-pulse">
                      <div className="w-12 h-3 bg-slate-800 rounded" />
                      <div className="w-24 h-2 bg-slate-800 rounded" />
                      <div className="w-full h-8 bg-slate-950/40 rounded border border-slate-900" />
                    </div>
                  ))}
                </div>
              ) : citations.length === 0 ? (
                <div className="text-center py-6 text-[10px] text-slate-500 border border-dashed border-slate-800 rounded-lg font-medium">
                  No citations saved yet. Select a Paper node to format and save a citation.
                </div>
              ) : (
                <div className="space-y-2.5">
                  {citations.map((cit) => (
                    <div key={cit.id} className="p-3 rounded-lg bg-slate-900/55 border border-slate-800/70 space-y-2 relative group hover:border-slate-700/60 transition-colors">
                      <div className="flex items-center justify-between">
                        <span className="bg-indigo-500/10 text-indigo-300 border border-indigo-500/10 px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-wider">
                          {cit.style}
                        </span>
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(cit.formatted_text);
                            setCopiedCitationId(cit.id);
                            setTimeout(() => setCopiedCitationId(null), 2000);
                          }}
                          className="text-[9px] font-bold text-slate-500 hover:text-slate-300 transition-colors flex items-center gap-1"
                        >
                          {copiedCitationId === cit.id ? (
                            <>
                              <Check className="w-3 h-3 text-emerald-400" />
                              <span className="text-emerald-400">Copied</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3 h-3" />
                              <span>Copy</span>
                            </>
                          )}
                        </button>
                      </div>
                      <p className="text-[9px] font-bold text-slate-400 uppercase tracking-wide truncate max-w-[200px]">
                        {cit.paper_title || 'Research Paper'}
                      </p>
                      <p className="text-[11px] text-slate-300 font-medium leading-relaxed bg-slate-950/30 p-2 rounded border border-slate-950/50">
                        {cit.formatted_text}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Footer Support Info */}
      <div className="p-4 border-t border-slate-800 flex items-center justify-between text-[10px] text-slate-500 font-medium">
        <span className="flex items-center gap-1.5"><HelpCircle className="w-3.5 h-3.5" /> Docs</span>
        <div className="flex items-center gap-2">
          {healthStatus ? (
            <div className="flex items-center gap-1.5" title={`Neo4j: ${healthStatus.neo4j.status} (${healthStatus.neo4j.mode})\nSupabase: ${healthStatus.supabase.status} (${healthStatus.supabase.mode})\nAI: ${healthStatus.anthropic.status} (${healthStatus.anthropic.mode})`}>
              <span className="text-[9px] font-bold text-slate-600 mr-0.5">STATUS:</span>
              <span className={`w-2 h-2 rounded-full cursor-help ${healthStatus.neo4j.status === 'ok' ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]' : 'bg-rose-500 animate-ping'}`} title={`Neo4j (${healthStatus.neo4j.mode})`} />
              <span className={`w-2 h-2 rounded-full cursor-help ${healthStatus.supabase.status === 'ok' ? 'bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,0.6)]' : 'bg-rose-500 animate-ping'}`} title={`Supabase (${healthStatus.supabase.mode})`} />
              <span className={`w-2 h-2 rounded-full cursor-help ${healthStatus.anthropic.status === 'ok' ? 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)]' : 'bg-rose-500 animate-ping'}`} title={`AI Copilot (${healthStatus.anthropic.mode})`} />
            </div>
          ) : (
            <span className="animate-pulse text-[9px] text-slate-600">Verifying status...</span>
          )}
        </div>
      </div>
    </aside>
  );
}

// ==================== RIGHT SIDEBAR ====================
export function RightSidebar() {
  const selectedNode = useStore((state) => state.selectedNode);
  const setSelectedNode = useStore((state) => state.setSelectedNode);
  const user = useStore((state) => state.user);
  
  // Chat state
  const chatMessages = useStore((state) => state.chatMessages);
  const chatLoading = useStore((state) => state.chatLoading);
  const addChatMessage = useStore((state) => state.addChatMessage);
  const updateLastChatMessage = useStore((state) => state.updateLastChatMessage);
  const setChatLoading = useStore((state) => state.setChatLoading);
  const clearChat = useStore((state) => state.clearChat);

  // Citations & Paths state (Sprint 5)
  const addCitation = useStore((state) => state.addCitation);
  const activePathNodeIds = useStore((state) => state.activePathNodeIds);
  const setActivePathNodeIds = useStore((state) => state.setActivePathNodeIds);
  const learningPathNarration = useStore((state) => state.learningPathNarration);
  const setLearningPathNarration = useStore((state) => state.setLearningPathNarration);
  const appendGraphData = useStore((state) => state.appendGraphData);
  const globalNodes = useStore((state) => state.nodes);

  // Local state
  const [contextCard, setContextCard] = useState<any>(null);
  const [contextLoading, setContextLoading] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [selectedStyle, setSelectedStyle] = useState('APA');
  const [citationSaving, setCitationSaving] = useState(false);
  const [pathGenerating, setPathGenerating] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Calculate learning path steps mapping
  const pathSteps = activePathNodeIds.map(id => globalNodes.find(n => n.id === id)).filter(Boolean);

  const handleSaveCitation = async () => {
    if (!selectedNode || selectedNode.label !== 'Paper') return;
    setCitationSaving(true);
    try {
      const response = await fetch(`${API_BASE_URL}/citations`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          paper_id: selectedNode.id,
          style: selectedStyle,
        }),
      });
      if (response.ok) {
        const data = await response.json();
        addCitation(data);
      }
    } catch (err) {
      console.error('Failed to save citation', err);
    } finally {
      setCitationSaving(false);
    }
  };

  const handleGenerateLearningPath = async () => {
    if (!selectedNode || selectedNode.label !== 'Concept') return;
    setPathGenerating(true);
    try {
      const response = await fetch(`${API_BASE_URL}/learning-path?target=${selectedNode.id}`);
      if (response.ok) {
        const data = await response.json();
        appendGraphData({ nodes: data.nodes, edges: data.edges });
        setActivePathNodeIds(data.nodes.map((n: any) => n.id));
        setLearningPathNarration(data.narration);
      }
    } catch (err) {
      console.error('Failed to generate learning path', err);
    } finally {
      setPathGenerating(false);
    }
  };

  const handleClearPath = () => {
    setActivePathNodeIds([]);
    setLearningPathNarration(null);
  };

  const handleStepClick = (stepNode: any) => {
    const clickedNode: GraphNode = {
      id: stepNode.id,
      label: stepNode.label || 'Concept',
      name: stepNode.name || stepNode.title || 'Unknown',
      description: stepNode.description || '',
      difficulty_level: stepNode.difficulty_level || 'Beginner'
    };
    setSelectedNode(clickedNode);
  };

  // Auto-scroll chat to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  // Fetch context details on selected node changes
  useEffect(() => {
    if (!selectedNode) {
      setContextCard(null);
      return;
    }

    const fetchContext = async () => {
      setContextLoading(true);
      try {
        const response = await fetch(`${API_BASE_URL}/copilot/context`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ node_id: selectedNode.id }),
        });
        if (response.ok) {
          const data = await response.json();
          setContextCard(data);
        }
      } catch (err) {
        console.error('Failed to load focus context', err);
      } finally {
        setContextLoading(false);
      }
    };

    fetchContext();
  }, [selectedNode]);

  const handleSendMessage = async (text: string) => {
    if (!text.trim()) return;

    // Append user message
    const userMsg = { role: 'user' as const, content: text };
    addChatMessage(userMsg);
    setInputValue('');
    setChatLoading(true);

    // Append empty assistant message for streaming capture
    addChatMessage({ role: 'assistant' as const, content: '' });

    try {
      const response = await fetch(`${API_BASE_URL}/copilot/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: text,
          node_id: selectedNode?.id || null,
          conversation_history: chatMessages.slice(-10).map(m => ({ role: m.role, content: m.content })),
          user_role: user?.role || 'student'
        }),
      });

      if (!response.ok || !response.body) {
        throw new Error('Streaming failed');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        updateLastChatMessage(chunk);
      }
    } catch (err) {
      console.error('Streaming connection error', err);
      updateLastChatMessage('\n\n*(Error connecting to AI Copilot. Check server connection.)*');
    } finally {
      setChatLoading(false);
    }
  };

  const triggerQuickAction = (action: string) => {
    if (!selectedNode) return;
    let prompt = '';
    switch (action) {
      case 'explain':
        prompt = `Explain the concept of '${selectedNode.name}' to me.`;
        break;
      case 'compare':
        prompt = `Compare '${selectedNode.name}' with its prerequisites.`;
        break;
      case 'next':
        prompt = `What are the next concepts I should study after '${selectedNode.name}'?`;
        break;
    }
    handleSendMessage(prompt);
  };

  // Label colors for node detail badges
  const getNodeColor = (label: string) => {
    switch (label) {
      case 'Concept': return 'text-blue-400 bg-blue-500/10 border-blue-500/20';
      case 'Paper': return 'text-purple-400 bg-purple-500/10 border-purple-500/20';
      case 'Author': return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
      case 'Topic': return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
      default: return 'text-slate-400 bg-slate-500/10 border-slate-500/20';
    }
  };

  return (
    <aside className="w-80 h-full flex flex-col glass-panel border-l border-slate-800 bg-[#0d1323]/80 select-none">
      {/* Tab Header */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <h2 className="text-xs font-bold text-slate-300 flex items-center gap-1.5 uppercase tracking-wider">
          <Sparkles className="w-4 h-4 text-indigo-400 animate-pulse" />
          AI Detail Panel
        </h2>
        <span className="text-[9px] text-slate-500 font-semibold bg-slate-800 px-2 py-0.5 rounded-full capitalize">
          {user?.role || 'student'} Mode
        </span>
      </div>

      {/* Details & Copilot Container */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5 scrollbar-thin">
        {selectedNode ? (
          <div className="space-y-4">
            {/* Header Identity */}
            <div className="space-y-2">
              <span className={`px-2 py-0.5 text-[9px] font-bold tracking-widest uppercase border rounded ${getNodeColor(selectedNode.label)}`}>
                {selectedNode.label}
              </span>
              <h3 className="text-base font-extrabold text-slate-100">{selectedNode.name}</h3>
            </div>

            {/* Description Card */}
            <div className="p-3.5 glass-card rounded-xl border border-slate-800/50 space-y-2.5">
              <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">Description</h4>
              <p className="text-xs text-slate-300 leading-relaxed font-medium">
                {selectedNode.description || 'No description extracted yet.'}
              </p>
            </div>

            {/* Context Card (Sprint 3) */}
            {contextLoading ? (
              <div className="p-3.5 glass-card rounded-xl border border-indigo-500/10 bg-indigo-500/5 space-y-3 animate-pulse">
                <h4 className="text-[10px] font-bold text-indigo-400 uppercase tracking-wide flex items-center gap-1">
                  <Map className="w-3.5 h-3.5 text-indigo-400" /> Graph Context Details
                </h4>
                <div className="space-y-2">
                  <div className="w-24 h-3 bg-slate-800 rounded" />
                  <div className="flex gap-1 mt-1">
                    <div className="w-16 h-5 bg-slate-800 rounded border border-slate-700/30" />
                    <div className="w-20 h-5 bg-slate-800 rounded border border-slate-700/30" />
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="w-16 h-3 bg-slate-800 rounded" />
                  <div className="flex gap-1 mt-1">
                    <div className="w-24 h-5 bg-slate-800 rounded border border-slate-700/30" />
                    <div className="w-12 h-5 bg-slate-800 rounded border border-slate-700/30" />
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="w-20 h-3 bg-slate-800 rounded" />
                  <div className="w-full h-6 bg-slate-800/60 rounded border border-slate-700/30" />
                </div>
              </div>
            ) : contextCard ? (
              <div className="p-3.5 glass-card rounded-xl border border-indigo-500/10 bg-indigo-500/5 space-y-3">
                <h4 className="text-[10px] font-bold text-indigo-400 uppercase tracking-wide flex items-center gap-1">
                  <Map className="w-3.5 h-3.5" /> Graph Context Details
                </h4>
                
                {/* Prerequisites */}
                <div className="space-y-1">
                  <span className="text-[9px] font-bold text-slate-500 uppercase">Depends On (Prereqs):</span>
                  {contextCard.prerequisites.length > 0 ? (
                    <div className="flex flex-wrap gap-1 mt-0.5">
                      {contextCard.prerequisites.map((p: any) => (
                        <span key={p.id} className="text-[9px] font-semibold bg-slate-800 text-slate-300 px-2 py-0.5 rounded border border-slate-700/50">
                          {p.name}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[10px] text-slate-500 italic mt-0.5">No prerequisite relationships mapped.</p>
                  )}
                </div>

                {/* Related concepts */}
                <div className="space-y-1">
                  <span className="text-[9px] font-bold text-slate-500 uppercase">Related Links:</span>
                  {contextCard.related.length > 0 ? (
                    <div className="flex flex-wrap gap-1 mt-0.5">
                      {contextCard.related.map((r: any) => (
                        <span key={r.id} className="text-[9px] font-semibold bg-slate-800 text-slate-300 px-2 py-0.5 rounded border border-slate-700/50">
                          {r.name}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[10px] text-slate-500 italic mt-0.5">No related connections mapped.</p>
                  )}
                </div>

                {/* Grounding Papers */}
                <div className="space-y-1">
                  <span className="text-[9px] font-bold text-slate-500 uppercase">Related Papers:</span>
                  {contextCard.papers.length > 0 ? (
                    <div className="flex flex-col gap-1 mt-0.5">
                      {contextCard.papers.map((p: any) => (
                        <span key={p.id} className="text-[9px] font-semibold bg-slate-800/55 text-indigo-300 px-2 py-1 rounded border border-indigo-500/10 truncate">
                          {p.name}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-[10px] text-slate-500 italic mt-0.5">No literature records connected.</p>
                  )}
                </div>
              </div>
            ) : null}

            {/* Citation Formatter (Sprint 5) */}
            {selectedNode.label === 'Paper' && (
              <div className="p-3.5 glass-card rounded-xl border border-indigo-500/10 bg-indigo-500/5 space-y-3">
                <h4 className="text-[10px] font-bold text-indigo-400 uppercase tracking-wide flex items-center gap-1.5">
                  <Bookmark className="w-3.5 h-3.5 text-indigo-400" /> Citation Formatter
                </h4>
                <div className="flex gap-2 items-center">
                  <div className="relative flex-1">
                    <select
                      value={selectedStyle}
                      onChange={(e) => setSelectedStyle(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-[11px] font-semibold text-slate-300 focus:outline-none focus:border-indigo-500/50 appearance-none cursor-pointer"
                    >
                      <option value="APA">APA Style</option>
                      <option value="MLA">MLA Style</option>
                      <option value="IEEE">IEEE Style</option>
                    </select>
                    <ChevronDown className="w-3.5 h-3.5 text-slate-500 absolute right-2.5 top-2 pointer-events-none" />
                  </div>
                  <button
                    disabled={citationSaving}
                    onClick={handleSaveCitation}
                    className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:bg-slate-850 text-white rounded-lg font-bold text-[10px] uppercase tracking-wider transition-all duration-150 shadow-md flex-shrink-0"
                  >
                    {citationSaving ? 'Saving...' : 'Save'}
                  </button>
                </div>
              </div>
            )}

            {/* Generate Learning Path (Sprint 5) */}
            {selectedNode.label === 'Concept' && (
              <button
                disabled={pathGenerating}
                onClick={handleGenerateLearningPath}
                className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 disabled:bg-slate-850 text-white rounded-xl font-bold text-[10px] uppercase tracking-wider flex items-center justify-center gap-2 shadow-md transition-colors"
              >
                {pathGenerating ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-white" />
                    <span>Calculating Path...</span>
                  </>
                ) : (
                  <>
                    <GraduationCap className="w-3.5 h-3.5 text-white" />
                    <span>Generate Learning Path</span>
                  </>
                )}
              </button>
            )}

            {/* AI Study Guide (Sprint 5) */}
            {learningPathNarration && (
              <div className="p-3.5 glass-card rounded-xl border border-emerald-500/20 bg-emerald-950/10 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-[10px] font-extrabold text-emerald-400 uppercase tracking-widest flex items-center gap-1.5">
                    <GraduationCap className="w-3.5 h-3.5 text-emerald-400" /> AI Study Guide
                  </h4>
                  <button
                    onClick={handleClearPath}
                    className="p-1 rounded text-slate-500 hover:text-slate-300 hover:bg-white/5 transition-colors"
                    title="Clear Learning Path"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
                
                <p className="text-[11px] text-slate-300 leading-relaxed font-semibold">
                  {learningPathNarration}
                </p>
                
                {/* Steps list */}
                <div className="space-y-1.5">
                  <span className="text-[9px] font-bold text-slate-500 uppercase">Path Steps:</span>
                  <div className="flex flex-col gap-1.5">
                    {pathSteps.map((stepNode: any, idx: number) => {
                      const isSelected = selectedNode?.id === stepNode.id;
                      return (
                        <button
                          key={stepNode.id}
                          onClick={() => handleStepClick(stepNode)}
                          className={`w-full text-left px-2.5 py-1.5 rounded-lg border flex items-center justify-between text-[10px] font-bold transition-all ${
                            isSelected
                              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                              : 'bg-slate-950/40 border-slate-900 text-slate-400 hover:text-slate-200 hover:border-slate-800'
                          }`}
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="w-4 h-4 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center text-[8px] font-bold text-slate-500">
                              {idx + 1}
                            </span>
                            <span className="truncate">{stepNode.name || stepNode.title}</span>
                          </div>
                          <ChevronRight className="w-3 h-3 text-slate-600" />
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {/* Quick Actions (Sprint 3) */}
            {selectedNode.label === 'Concept' && (
              <div className="grid grid-cols-2 gap-2 mt-4">
                <button
                  onClick={() => triggerQuickAction('explain')}
                  className="py-2 px-2.5 bg-slate-900 border border-slate-800 hover:border-indigo-500/40 text-slate-300 text-[10px] font-bold rounded-lg transition-all"
                >
                  Explain Concept
                </button>
                <button
                  onClick={() => triggerQuickAction('compare')}
                  className="py-2 px-2.5 bg-slate-900 border border-slate-800 hover:border-indigo-500/40 text-slate-300 text-[10px] font-bold rounded-lg transition-all"
                >
                  Prereqs Compare
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {/* AI Study Guide (Sprint 5) - Even if no node is selected */}
            {learningPathNarration && (
              <div className="p-3.5 glass-card rounded-xl border border-emerald-500/20 bg-emerald-950/10 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-[10px] font-extrabold text-emerald-400 uppercase tracking-widest flex items-center gap-1.5">
                    <GraduationCap className="w-3.5 h-3.5 text-emerald-400" /> AI Study Guide
                  </h4>
                  <button
                    onClick={handleClearPath}
                    className="p-1 rounded text-slate-500 hover:text-slate-300 hover:bg-white/5 transition-colors"
                    title="Clear Learning Path"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
                
                <p className="text-[11px] text-slate-300 leading-relaxed font-semibold">
                  {learningPathNarration}
                </p>
                
                {/* Steps list */}
                <div className="space-y-1.5">
                  <span className="text-[9px] font-bold text-slate-500 uppercase">Path Steps:</span>
                  <div className="flex flex-col gap-1.5">
                    {pathSteps.map((stepNode: any, idx: number) => (
                      <button
                        key={stepNode.id}
                        onClick={() => handleStepClick(stepNode)}
                        className="w-full text-left px-2.5 py-1.5 rounded-lg border flex items-center justify-between text-[10px] font-bold transition-all bg-slate-950/40 border-slate-900 text-slate-400 hover:text-slate-200 hover:border-slate-800"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="w-4 h-4 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center text-[8px] font-bold text-slate-500">
                            {idx + 1}
                          </span>
                          <span className="truncate">{stepNode.name || stepNode.title}</span>
                        </div>
                        <ChevronRight className="w-3 h-3 text-slate-600" />
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            <div className="h-44 flex flex-col items-center justify-center text-center text-slate-500 border border-dashed border-slate-800 rounded-xl py-6 px-4 bg-slate-900/10">
              <Cpu className="w-8 h-8 text-slate-600 mb-2 animate-pulse" />
              <p className="text-xs font-semibold">Select a Node on the Graph</p>
              <p className="text-[10px] text-slate-500 mt-1 max-w-[200px]">
                Click any element on the map to display its definition, properties, and relationships.
              </p>
            </div>
          </div>
        )}

        {/* AI Copilot Panel (Sprint 3) */}
        <div className="border-t border-slate-800/80 pt-4 flex flex-col h-[340px]">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-[10px] font-bold text-indigo-400 uppercase tracking-widest flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5" /> AI Copilot Workspace
            </h4>
            {chatMessages.length > 0 && (
              <button 
                onClick={clearChat}
                className="p-1 rounded text-slate-500 hover:text-slate-300 hover:bg-slate-800 transition-colors"
                title="Clear Chat"
              >
                <Trash className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Chat scrolling log */}
          <div className="flex-1 overflow-y-auto space-y-3.5 pr-1 border border-slate-800/50 bg-slate-950/20 rounded-xl p-3 scrollbar-thin">
            {chatMessages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-3 text-slate-500 space-y-2">
                <Sparkles className="w-6 h-6 text-slate-600 animate-pulse" />
                <p className="text-[10px] leading-relaxed font-semibold">
                  Ask me anything about the concepts, papers, or prerequisite routes. I'll ground my answer in your graph.
                </p>
              </div>
            ) : (
              chatMessages.map((msg, idx) => (
                <div 
                  key={idx} 
                  className={`flex flex-col max-w-[85%] rounded-xl px-3 py-2 text-[11px] leading-relaxed border ${
                    msg.role === 'user'
                      ? 'bg-indigo-600/10 border-indigo-500/20 text-slate-200 self-end'
                      : 'bg-slate-900 border-slate-800 text-slate-300 self-start'
                  }`}
                >
                  <span className="text-[8px] font-extrabold uppercase text-slate-500 mb-0.5 tracking-wider">
                    {msg.role === 'user' ? 'You' : 'Copilot'}
                  </span>
                  <p className="whitespace-pre-wrap font-medium">{msg.content || (chatLoading && idx === chatMessages.length - 1 ? 'Writing...' : '')}</p>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input text bar */}
          <form 
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage(inputValue);
            }}
            className="flex items-center gap-1.5 mt-3"
          >
            <input
              type="text"
              disabled={chatLoading}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Ask Copilot..."
              className="flex-1 px-3 py-2 rounded-lg bg-slate-950/50 border border-slate-800 text-xs text-slate-100 focus:outline-none focus:border-indigo-500/70 disabled:opacity-50 transition-colors"
            />
            <button
              type="submit"
              disabled={chatLoading || !inputValue.trim()}
              className="p-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 text-white rounded-lg transition-colors flex-shrink-0 shadow-md"
            >
              <Send className="w-3.5 h-3.5" />
            </button>
          </form>
        </div>
      </div>
    </aside>
  );
}

// ==================== BOTTOM PANEL ====================
export function BottomPanel() {
  const [isExpanded, setIsExpanded] = useState(true);
  const highlights = useStore((state) => state.highlights);
  const setHighlights = useStore((state) => state.setHighlights);

  // Fetch highlights on mount
  useEffect(() => {
    const fetchHighlights = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/highlights`);
        if (response.ok) {
          const data = await response.json();
          setHighlights(data);
        }
      } catch (err) {
        console.error('Failed to load highlights', err);
      }
    };
    fetchHighlights();
  }, [setHighlights]);

  return (
    <footer className="w-full glass-panel border-t border-slate-800 bg-[#0d1323]/80 select-none">
      {/* Bar Header Toggle */}
      <div 
        onClick={() => setIsExpanded(!isExpanded)}
        className="px-4 py-2 border-b border-slate-800/50 flex items-center justify-between cursor-pointer hover:bg-white/5 transition-colors"
      >
        <span className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest flex items-center gap-1.5">
          Highlights · Bookmarks · Recent Insights
        </span>
        <button className="text-slate-400 hover:text-white">
          {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
        </button>
      </div>

      {/* Content drawer */}
      {isExpanded && (
        <div className="h-[92px] p-3 overflow-x-auto flex gap-3 scrollbar-thin">
          {highlights.length === 0 ? (
            <div className="min-w-[260px] max-w-[260px] h-full rounded-lg border border-dashed border-slate-800 p-3 flex flex-col justify-center items-center text-center text-[10px] text-slate-500 font-medium">
              No highlights saved yet. Select document text to save key insights.
            </div>
          ) : (
            highlights.map((hl) => (
              <div key={hl.id} className="min-w-[240px] max-w-[240px] p-2.5 glass-card rounded-lg border border-slate-800 flex flex-col justify-between">
                <p className="text-[10px] text-slate-300 italic line-clamp-2 leading-relaxed font-semibold">
                  "{hl.text}"
                </p>
                <div className="flex justify-between items-center text-[8px] text-indigo-400 font-bold uppercase tracking-wide">
                  <span className="truncate max-w-[150px]">{hl.doc_title}</span>
                  <span className="text-[8px] font-medium text-slate-500 flex-shrink-0">Page {hl.page}</span>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </footer>
  );
}
