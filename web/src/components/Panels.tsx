'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useStore, GraphNode } from '../store/useStore';
import { 
  FileText, Plus, Database, Cpu, HelpCircle, 
  Map as MapIcon, Sparkles, BookOpen, GraduationCap, 
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
  const graphFilter = useStore((state) => state.graphFilter);
  const setGraphFilter = useStore((state) => state.setGraphFilter);

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
        const response = await fetch('http://localhost:8000/health/deep');
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
  // Fetch notes on load and document change
  useEffect(() => {
    const fetchNotes = async () => {
      try {
        const response = await fetch('http://localhost:8000/notes');
        if (response.ok) {
          const data = await response.json();
          setNotes(data);
        }
      } catch (err) {
        console.error('Failed to load notes', err);
      }
    };
    fetchNotes();
  }, [activeDocumentId, setNotes]);

  // Fetch citations on load and document change
  useEffect(() => {
    const fetchCitations = async () => {
      setCitationsLoading(true);
      try {
        const response = await fetch('http://localhost:8000/citations');
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
  }, [activeDocumentId, setCitations]);

  const handleDocumentSelect = async (docId: string) => {
    setActiveDocumentId(docId);
    try {
      const response = await fetch(`http://localhost:8000/documents/${docId}/graph`);
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
        ? `http://localhost:8000/notes/search?q=${encodeURIComponent(q)}`
        : 'http://localhost:8000/notes';
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
      const response = await fetch('http://localhost:8000/notes', {
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
    <aside className="w-60 h-full flex flex-col glass-panel border-r border-cyan-500/10 bg-[#030e0d]/70 select-none">
      {/* Brand Logo */}
      <div className="p-4 border-b border-cyan-500/10 flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-lg bg-cyan-950/80 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shadow-[0_0_12px_rgba(6,182,212,0.25)] glow-active">
          <Database className="w-4.5 h-4.5" />
        </div>
        <div>
          <h1 className="font-extrabold text-sm text-white tracking-wider font-sans">MINDMESH AI</h1>
          <p className="text-[9px] text-cyan-400 font-mono font-bold tracking-widest">Knowledge Graph</p>
        </div>
      </div>

      {/* User Session Badge */}
      <div className="px-4 py-3 border-b border-cyan-500/5 flex items-center justify-between bg-[#061211]/25">
        <div className="flex items-center gap-2">
          <UserCheck className="w-4 h-4 text-cyan-400" />
          <div className="min-w-0">
            <p className="text-xs font-semibold text-slate-300 truncate font-sans">{user?.email || 'Guest User'}</p>
            <p className="text-[9px] text-cyan-400 font-mono font-bold tracking-wider uppercase">{user?.role || 'student'}</p>
          </div>
        </div>
      </div>

      {/* Nav Selector Tabs */}
      <div className="px-3 pt-3 flex gap-1 border-b border-cyan-500/5 pb-2">
        <button
          onClick={() => setActiveNavTab('navigation')}
          className={`flex-1 py-1.5 text-[10px] font-bold rounded-lg uppercase tracking-wider transition-colors font-sans ${
            activeNavTab === 'navigation'
              ? 'bg-cyan-950/40 text-cyan-300 border border-cyan-500/25 shadow-[0_0_10px_rgba(6,182,212,0.1)]'
              : 'text-slate-500 hover:text-slate-300 hover:bg-[#061211]/20'
          }`}
        >
          Index
        </button>
        <button
          onClick={() => setActiveNavTab('notes')}
          className={`flex-1 py-1.5 text-[10px] font-bold rounded-lg uppercase tracking-wider transition-colors font-sans ${
            activeNavTab === 'notes'
              ? 'bg-cyan-950/40 text-cyan-300 border border-cyan-500/25 shadow-[0_0_10px_rgba(6,182,212,0.1)]'
              : 'text-slate-500 hover:text-slate-300 hover:bg-[#061211]/20'
          }`}
        >
          Notes ({notes.length})
        </button>
        <button
          onClick={() => setActiveNavTab('citations')}
          className={`flex-1 py-1.5 text-[10px] font-bold rounded-lg uppercase tracking-wider transition-colors font-sans ${
            activeNavTab === 'citations'
              ? 'bg-cyan-950/40 text-cyan-300 border border-cyan-500/25 shadow-[0_0_10px_rgba(6,182,212,0.1)]'
              : 'text-slate-500 hover:text-slate-300 hover:bg-[#061211]/20'
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
                className="w-full py-2 px-3.5 bg-gradient-to-r from-cyan-600 to-teal-600 hover:from-cyan-500 hover:to-teal-500 text-white rounded-xl font-bold text-xs flex items-center justify-center gap-2 shadow-[0_0_15px_rgba(6,182,212,0.2)] border border-cyan-400/20 transition-all duration-200 cursor-pointer"
              >
                <Plus className="w-4 h-4 text-white" />
                Ingest Document
              </button>
            </div>

            {/* Navigation options */}
            <nav className="space-y-1">
              <div className="text-[9px] text-cyan-500/60 font-mono font-bold px-2 py-1 tracking-widest">SECTIONS</div>
              <a 
                href="#"
                onClick={(e) => { e.preventDefault(); setGraphFilter(graphFilter === 'Concept' ? null : 'Concept'); }}
                className={`flex items-center gap-2.5 px-3 py-2 text-xs transition-all rounded-lg border cursor-pointer ${
                  graphFilter === 'Concept' || graphFilter === null
                    ? 'font-bold text-cyan-400 bg-cyan-950/20 border-cyan-500/15 shadow-[0_0_10px_rgba(6,182,212,0.05)]'
                    : 'font-semibold text-slate-400 hover:text-cyan-300 hover:bg-cyan-950/10 border-transparent hover:border-cyan-500/5'
                }`}
              >
                <GraduationCap className="w-4 h-4" />
                Concepts
              </a>
              <a 
                href="#"
                onClick={(e) => { e.preventDefault(); setGraphFilter(graphFilter === 'Paper' ? null : 'Paper'); }}
                className={`flex items-center gap-2.5 px-3 py-2 text-xs transition-all rounded-lg border cursor-pointer ${
                  graphFilter === 'Paper'
                    ? 'font-bold text-cyan-400 bg-cyan-950/20 border-cyan-500/15 shadow-[0_0_10px_rgba(6,182,212,0.05)]'
                    : 'font-semibold text-slate-400 hover:text-cyan-300 hover:bg-cyan-950/10 border-transparent hover:border-cyan-500/5'
                }`}
              >
                <BookOpen className="w-4 h-4" />
                Papers
              </a>
              <a 
                href="#"
                onClick={(e) => { e.preventDefault(); setGraphFilter(graphFilter === 'Author' ? null : 'Author'); }}
                className={`flex items-center gap-2.5 px-3 py-2 text-xs transition-all rounded-lg border cursor-pointer ${
                  graphFilter === 'Author'
                    ? 'font-bold text-cyan-400 bg-cyan-950/20 border-cyan-500/15 shadow-[0_0_10px_rgba(6,182,212,0.05)]'
                    : 'font-semibold text-slate-400 hover:text-cyan-300 hover:bg-cyan-950/10 border-transparent hover:border-cyan-500/5'
                }`}
              >
                <Landmark className="w-4 h-4" />
                Authors
              </a>
              <a 
                href="#"
                onClick={(e) => { e.preventDefault(); setGraphFilter(graphFilter === 'Keyword' ? null : 'Keyword'); }}
                className={`flex items-center gap-2.5 px-3 py-2 text-xs transition-all rounded-lg border cursor-pointer ${
                  graphFilter === 'Keyword'
                    ? 'font-bold text-cyan-400 bg-cyan-950/20 border-cyan-500/15 shadow-[0_0_10px_rgba(6,182,212,0.05)]'
                    : 'font-semibold text-slate-400 hover:text-cyan-300 hover:bg-cyan-950/10 border-transparent hover:border-cyan-500/5'
                }`}
              >
                <Tag className="w-4 h-4" />
                Keywords
              </a>
              <a 
                href="#"
                onClick={(e) => { e.preventDefault(); setGraphFilter(graphFilter === 'Learning Path' ? null : 'Learning Path'); }}
                className={`flex items-center gap-2.5 px-3 py-2 text-xs transition-all rounded-lg border cursor-pointer ${
                  graphFilter === 'Learning Path'
                    ? 'font-bold text-cyan-400 bg-cyan-950/20 border-cyan-500/15 shadow-[0_0_10px_rgba(6,182,212,0.05)]'
                    : 'font-semibold text-slate-400 hover:text-cyan-300 hover:bg-cyan-950/10 border-transparent hover:border-cyan-500/5'
                }`}
              >
                <MapIcon className="w-4 h-4" />
                Learning Paths
              </a>
            </nav>

            {/* Documents Queue */}
            <div className="space-y-1">
              <div className="text-[9px] text-cyan-500/60 font-mono font-bold px-2 py-1 tracking-widest">DOCUMENTS QUEUE</div>
              {documents.length === 0 ? (
                <div className="px-3 py-4 text-center rounded-lg border border-dashed border-cyan-950 text-[10px] text-slate-500 font-medium">
                  No documents ingested yet.
                </div>
              ) : (
                documents.map((doc) => (
                  <button
                    key={doc.id}
                    onClick={() => handleDocumentSelect(doc.id)}
                    className={`w-full text-left px-3 py-2 rounded-lg flex flex-col gap-1 border transition-all ${
                      activeDocumentId === doc.id
                        ? 'bg-cyan-950/30 border-cyan-500/25 text-cyan-100 shadow-[0_0_10px_rgba(6,182,212,0.05)]'
                        : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-cyan-950/10'
                    }`}
                  >
                    <div className="flex items-center gap-2 w-full">
                      <FileText className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0" />
                      <span className="text-[11px] font-semibold truncate flex-1 font-sans">{doc.title}</span>
                    </div>
                    {doc.status !== 'done' && (
                      <div className="w-full bg-[#030c0b] border border-cyan-500/10 h-1.5 rounded-full overflow-hidden mt-1">
                        <div 
                          className={`h-full rounded-full transition-all duration-300 ${doc.status === 'error' ? 'bg-rose-500' : 'bg-cyan-500'}`}
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
              className="w-full px-3 py-1.5 rounded-lg bg-[#030c0b] border border-cyan-500/10 text-[11px] text-cyan-100 placeholder-slate-600 focus:outline-none focus:border-cyan-500/45 font-medium"
            />

            {/* Note Composer */}
            <div className="space-y-2">
              <textarea
                value={noteInput}
                onChange={(e) => setNoteInput(e.target.value)}
                placeholder="Write a personal note..."
                className="w-full h-20 p-2.5 rounded-lg bg-[#030c0b]/40 border border-cyan-500/10 text-[11px] text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500/40 resize-none font-medium leading-relaxed"
              />
              <button
                disabled={noteSubmitLoading || !noteInput.trim()}
                onClick={handleAddNote}
                className="w-full py-1.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-900 border border-cyan-500/10 text-white rounded-lg font-bold text-[10px] uppercase tracking-wider flex items-center justify-center gap-1.5 shadow-[0_0_10px_rgba(6,182,212,0.15)] cursor-pointer"
              >
                {noteSubmitLoading ? 'Saving...' : 'Add Note'}
              </button>
            </div>

            {/* Scrollable list of Notes */}
            <div className="space-y-2.5 pt-2">
              <div className="text-[9px] text-cyan-500/60 font-mono font-bold tracking-widest uppercase">SAVED NOTES</div>
              {notes.length === 0 ? (
                <div className="text-center py-6 text-[10px] text-slate-500 border border-dashed border-cyan-950 rounded-lg font-medium">
                  No notes saved yet. Write a personal note above to capture insights.
                </div>
              ) : (
                notes.map((note) => (
                  <div key={note.id} className="p-2.5 rounded-lg bg-cyan-950/10 border border-cyan-500/5 space-y-2">
                    <p className="text-[11px] text-slate-300 font-medium leading-relaxed whitespace-pre-wrap">{note.content}</p>
                    {note.concepts && note.concepts.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {note.concepts.map((c: string, idx: number) => (
                          <span key={idx} className="bg-cyan-500/10 text-cyan-300 border border-cyan-500/15 px-1.5 py-0.5 rounded text-[8px] font-mono font-bold">
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
              <div className="text-[9px] text-cyan-500/60 font-mono font-bold tracking-widest uppercase">Saved Citations</div>
              {citationsLoading ? (
                <div className="space-y-2.5">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="p-3 rounded-lg bg-cyan-950/10 border border-cyan-500/5 space-y-2.5 animate-pulse">
                      <div className="w-12 h-3 bg-slate-800 rounded" />
                      <div className="w-24 h-2 bg-slate-800 rounded" />
                      <div className="w-full h-8 bg-[#030c0b]/40 rounded border border-cyan-500/5" />
                    </div>
                  ))}
                </div>
              ) : citations.length === 0 ? (
                <div className="text-center py-6 text-[10px] text-slate-500 border border-dashed border-cyan-950 rounded-lg font-medium">
                  No citations saved yet. Select a Paper node to format and save a citation.
                </div>
              ) : (
                <div className="space-y-2.5">
                  {citations.map((cit) => (
                    <div key={cit.id} className="p-3 rounded-lg bg-cyan-950/10 border border-cyan-500/5 space-y-2 relative group hover:border-cyan-500/15 transition-all">
                      <div className="flex items-center justify-between">
                        <span className="bg-cyan-500/10 text-cyan-300 border border-cyan-500/15 px-1.5 py-0.5 rounded text-[8px] font-mono font-bold uppercase tracking-wider">
                          {cit.style}
                        </span>
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(cit.formatted_text);
                            setCopiedCitationId(cit.id);
                            setTimeout(() => setCopiedCitationId(null), 2000);
                          }}
                          className="text-[9px] font-bold text-slate-500 hover:text-cyan-300 transition-colors flex items-center gap-1 cursor-pointer"
                        >
                          {copiedCitationId === cit.id ? (
                            <>
                              <Check className="w-3 h-3 text-emerald-400" />
                              <span className="text-emerald-400 font-mono">Copied</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3 h-3" />
                              <span className="font-mono">Copy</span>
                            </>
                          )}
                        </button>
                      </div>
                      <p className="text-[9px] font-bold text-slate-400 uppercase tracking-wide truncate max-w-[200px] font-sans">
                        {cit.paper_title || 'Research Paper'}
                      </p>
                      <p className="text-[11px] text-slate-300 font-medium leading-relaxed bg-[#030c0b]/40 p-2 rounded border border-cyan-500/5 font-sans select-text">
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
      <div className="p-4 border-t border-cyan-500/10 flex items-center justify-between text-[10px] text-slate-500 font-medium">
        <span className="flex items-center gap-1.5"><HelpCircle className="w-3.5 h-3.5 text-cyan-500/60" /> Docs</span>
        <div className="flex items-center gap-2">
          {healthStatus ? (
            <div className="flex items-center gap-1.5" title={`Neo4j: ${healthStatus.neo4j.status} (${healthStatus.neo4j.mode})\nSupabase: ${healthStatus.supabase.status} (${healthStatus.supabase.mode})\nAI: ${healthStatus.anthropic.status} (${healthStatus.anthropic.mode})`}>
              <span className="text-[9px] font-bold text-slate-600 mr-0.5 font-mono">STATUS:</span>
              <span className={`w-2 h-2 rounded-full cursor-help ${healthStatus.neo4j.status === 'ok' ? 'bg-cyan-500 shadow-[0_0_8px_rgba(6,182,212,0.6)]' : 'bg-rose-500 animate-ping'}`} title={`Neo4j (${healthStatus.neo4j.mode})`} />
              <span className={`w-2 h-2 rounded-full cursor-help ${healthStatus.supabase.status === 'ok' ? 'bg-violet-500 shadow-[0_0_8px_rgba(139,92,246,0.6)]' : 'bg-rose-500 animate-ping'}`} title={`Supabase (${healthStatus.supabase.mode})`} />
              <span className={`w-2 h-2 rounded-full cursor-help ${healthStatus.anthropic.status === 'ok' ? 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)]' : 'bg-rose-500 animate-ping'}`} title={`AI Copilot (${healthStatus.anthropic.mode})`} />
            </div>
          ) : (
            <span className="animate-pulse text-[9px] text-slate-600 font-mono">Verifying...</span>
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
      const response = await fetch('http://localhost:8000/citations', {
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
      const response = await fetch(`http://localhost:8000/learning-path?target=${selectedNode.id}`);
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

  const handleStepClick = async (stepNode: any) => {
    const clickedNode: GraphNode = {
      id: stepNode.id,
      label: stepNode.label || 'Concept',
      name: stepNode.name || stepNode.title || 'Unknown',
      description: stepNode.description || '',
      difficulty_level: stepNode.difficulty_level || 'Beginner'
    };
    setSelectedNode(clickedNode);
    try {
      const response = await fetch(`http://localhost:8000/graph/node/${stepNode.id}`);
      if (response.ok) {
        const detailsData = await response.json();
        setSelectedNode(detailsData);
      }
    } catch (err) {
      console.error('Failed to fetch step details', err);
    }
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
        const response = await fetch('http://localhost:8000/copilot/context', {
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
      const response = await fetch('http://localhost:8000/copilot/chat', {
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
    <aside className="w-80 h-full flex flex-col glass-panel border-l border-cyan-500/10 bg-[#030e0d]/70 select-none">
      {/* Tab Header */}
      <div className="p-4 border-b border-cyan-500/10 flex items-center justify-between">
        <h2 className="text-xs font-bold text-slate-300 flex items-center gap-1.5 uppercase tracking-wider font-sans">
          <Sparkles className="w-4 h-4 text-cyan-400 animate-pulse" />
          AI Detail Panel
        </h2>
        <span className="text-[9px] text-cyan-400 font-mono font-bold bg-cyan-950/30 border border-cyan-500/20 px-2 py-0.5 rounded-full uppercase tracking-wider">
          {user?.role || 'student'} Mode
        </span>
      </div>

      {/* Details & Copilot Container */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5 scrollbar-thin">
        {selectedNode ? (
          <div className="space-y-4">
            {/* Header Identity */}
            <div className="space-y-2">
              <span className={`px-2 py-0.5 text-[9px] font-mono font-bold tracking-widest uppercase border rounded ${getNodeColor(selectedNode.label)}`}>
                {selectedNode.label}
              </span>
              <h3 className="text-base font-extrabold text-slate-100 font-sans">{selectedNode.name}</h3>
            </div>

            {/* Description Card */}
            <div className="p-3.5 glass-card rounded-xl border border-cyan-500/10 space-y-2.5">
              <h4 className="text-[9px] font-mono font-bold text-cyan-500/60 uppercase tracking-widest">Description</h4>
              <p className="text-xs text-slate-300 leading-relaxed font-medium font-sans">
                {selectedNode.description || 'No description extracted yet.'}
              </p>
            </div>

            {/* Context Card (Sprint 3) */}
            {contextLoading ? (
              <div className="p-3.5 glass-card rounded-xl border border-cyan-500/15 bg-cyan-950/10 space-y-3 animate-pulse">
                <h4 className="text-[9px] font-mono font-bold text-cyan-400 uppercase tracking-widest flex items-center gap-1">
                  <MapIcon className="w-3.5 h-3.5 text-cyan-400" /> Graph Context Details
                </h4>
                <div className="space-y-2">
                  <div className="w-24 h-3 bg-slate-800 rounded" />
                  <div className="flex gap-1 mt-1">
                    <div className="w-16 h-5 bg-slate-800 rounded border border-slate-700/30" />
                    <div className="w-20 h-5 bg-slate-800 rounded border border-slate-700/30" />
                  </div>
                </div>
              </div>
            ) : contextCard ? (
              <div className="p-3.5 glass-card rounded-xl border border-cyan-500/10 bg-cyan-950/10 space-y-3">
                <h4 className="text-[9px] font-mono font-bold text-cyan-400 uppercase tracking-widest flex items-center gap-1">
                  <MapIcon className="w-3.5 h-3.5" /> Graph Context Details
                </h4>
                
                {/* Prerequisites */}
                <div className="space-y-1">
                  <span className="text-[9px] font-mono font-bold text-slate-500 uppercase">Depends On (Prereqs):</span>
                  {contextCard.prerequisites.length > 0 ? (
                    <div className="flex flex-wrap gap-1 mt-0.5">
                      {Array.from(new Map(contextCard.prerequisites.map((p: any) => [p.id, p])).values()).map((p: any) => (
                        <span key={p.id} className="text-[9px] font-mono font-bold bg-[#030c0b] text-cyan-300 px-2 py-0.5 rounded border border-cyan-500/10">
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
                  <span className="text-[9px] font-mono font-bold text-slate-500 uppercase">Related Links:</span>
                  {contextCard.related.length > 0 ? (
                    <div className="flex flex-wrap gap-1 mt-0.5">
                      {Array.from(new Map(contextCard.related.map((r: any) => [r.id, r])).values()).map((r: any) => (
                        <span key={r.id} className="text-[9px] font-mono font-bold bg-[#030c0b] text-slate-300 px-2 py-0.5 rounded border border-cyan-500/10">
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
                  <span className="text-[9px] font-mono font-bold text-slate-500 uppercase">Related Papers:</span>
                  {contextCard.papers.length > 0 ? (
                    <div className="flex flex-col gap-1 mt-0.5">
                      {Array.from(new Map(contextCard.papers.map((p: any) => [p.id, p])).values()).map((p: any) => (
                        <span key={p.id} className="text-[9px] font-semibold bg-[#030c0b]/40 text-violet-300 px-2 py-1 rounded border border-violet-500/10 truncate font-sans">
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

            {/* Paper Metadata Panel */}
            {selectedNode.label === 'Paper' && (
              <div className="p-3.5 glass-card rounded-xl border border-cyan-500/10 bg-[#030c0b]/40 space-y-3">
                <h4 className="text-[9px] font-mono font-bold text-cyan-400 uppercase tracking-widest flex items-center gap-1">
                  Paper Publications Details
                </h4>
                <div className="grid grid-cols-2 gap-3 text-xs font-sans">
                  <div>
                    <span className="text-[9px] font-mono font-bold text-slate-500 uppercase block">Published Year</span>
                    <span className="text-slate-300 font-semibold">{(selectedNode as any).year || 'Unknown Year'}</span>
                  </div>
                  <div>
                    <span className="text-[9px] font-mono font-bold text-slate-500 uppercase block">DOI Reference</span>
                    <span className="text-slate-300 font-semibold font-mono truncate block" title={(selectedNode as any).doi || 'None'}>
                      {(selectedNode as any).doi || 'None'}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Citation Formatter (Sprint 5) */}
            {selectedNode.label === 'Paper' && (
              <div className="p-3.5 glass-card rounded-xl border border-cyan-500/10 bg-cyan-950/5 space-y-3">
                <h4 className="text-[9px] font-mono font-bold text-cyan-400 uppercase tracking-widest flex items-center gap-1.5">
                  <Bookmark className="w-3.5 h-3.5 text-cyan-400" /> Citation Formatter
                </h4>
                <div className="flex gap-2 items-center">
                  <div className="relative flex-1">
                    <select
                      value={selectedStyle}
                      onChange={(e) => setSelectedStyle(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded-lg bg-[#030c0b] border border-cyan-500/10 text-[11px] font-semibold text-cyan-300 focus:outline-none focus:border-cyan-500/40 appearance-none cursor-pointer font-sans"
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
                    className="px-3.5 py-1.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-900 border border-cyan-500/10 text-white rounded-lg font-bold text-[10px] uppercase tracking-wider transition-all duration-150 shadow-md flex-shrink-0 cursor-pointer"
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
                className="w-full py-2.5 px-4 bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-500 hover:to-cyan-500 disabled:bg-slate-900 border border-cyan-500/10 text-white rounded-xl font-bold text-[10px] uppercase tracking-wider flex items-center justify-center gap-2 shadow-[0_0_12px_rgba(20,184,166,0.15)] transition-colors cursor-pointer"
              >
                {pathGenerating ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin text-white" />
                    <span className="font-sans">Calculating Path...</span>
                  </>
                ) : (
                  <>
                    <GraduationCap className="w-3.5 h-3.5 text-white" />
                    <span className="font-sans">Generate Learning Path</span>
                  </>
                )}
              </button>
            )}

            {/* AI Study Guide (Sprint 5) */}
            {learningPathNarration && (
              <div className="p-3.5 glass-card rounded-xl border border-emerald-500/20 bg-emerald-950/10 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-[9px] font-mono font-bold text-emerald-400 uppercase tracking-widest flex items-center gap-1.5">
                    <GraduationCap className="w-3.5 h-3.5 text-emerald-400" /> AI Study Guide
                  </h4>
                  <button
                    onClick={handleClearPath}
                    className="p-1 rounded text-slate-555 hover:text-slate-333 hover:bg-white/5 transition-colors cursor-pointer"
                    title="Clear Learning Path"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
                
                <p className="text-[11px] text-slate-300 leading-relaxed font-semibold font-sans">
                  {learningPathNarration}
                </p>
                
                {/* Steps list */}
                <div className="space-y-1.5">
                  <span className="text-[9px] font-mono font-bold text-slate-500 uppercase">Path Steps:</span>
                  <div className="flex flex-col gap-1.5">
                    {pathSteps.map((stepNode: any, idx: number) => {
                      const isSelected = selectedNode?.id === stepNode.id;
                      return (
                        <button
                          key={stepNode.id}
                          onClick={() => handleStepClick(stepNode)}
                          className={`w-full text-left px-2.5 py-1.5 rounded-lg border flex items-center justify-between text-[10px] font-bold transition-all cursor-pointer font-sans ${
                            isSelected
                              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                              : 'bg-[#030c0b] border-cyan-500/5 text-slate-400 hover:text-slate-200 hover:border-cyan-500/20'
                          }`}
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="w-4 h-4 rounded-full bg-[#030c0b] border border-cyan-500/10 flex items-center justify-center text-[8px] font-mono font-bold text-cyan-400/80">
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
                  className="py-2 px-2.5 bg-[#030c0b] border border-cyan-500/10 hover:border-cyan-500/30 text-slate-300 hover:text-cyan-300 text-[10px] font-bold rounded-lg transition-all cursor-pointer font-sans"
                >
                  Explain Concept
                </button>
                <button
                  onClick={() => triggerQuickAction('compare')}
                  className="py-2 px-2.5 bg-[#030c0b] border border-cyan-500/10 hover:border-cyan-500/30 text-slate-300 hover:text-cyan-300 text-[10px] font-bold rounded-lg transition-all cursor-pointer font-sans"
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
                  <h4 className="text-[9px] font-mono font-bold text-emerald-400 uppercase tracking-widest flex items-center gap-1.5">
                    <GraduationCap className="w-3.5 h-3.5 text-emerald-400" /> AI Study Guide
                  </h4>
                  <button
                    onClick={handleClearPath}
                    className="p-1 rounded text-slate-500 hover:text-slate-300 hover:bg-white/5 transition-colors cursor-pointer"
                    title="Clear Learning Path"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
                
                <p className="text-[11px] text-slate-300 leading-relaxed font-semibold font-sans">
                  {learningPathNarration}
                </p>
                
                {/* Steps list */}
                <div className="space-y-1.5">
                  <span className="text-[9px] font-mono font-bold text-slate-500 uppercase">Path Steps:</span>
                  <div className="flex flex-col gap-1.5">
                    {pathSteps.map((stepNode: any, idx: number) => (
                      <button
                        key={stepNode.id}
                        onClick={() => handleStepClick(stepNode)}
                        className="w-full text-left px-2.5 py-1.5 rounded-lg border flex items-center justify-between text-[10px] font-bold transition-all bg-[#030c0b] border-cyan-500/5 text-slate-400 hover:text-slate-200 hover:border-cyan-500/20 cursor-pointer font-sans"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="w-4 h-4 rounded-full bg-[#030c0b] border border-cyan-500/10 flex items-center justify-center text-[8px] font-mono font-bold text-cyan-400/80">
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

            <div className="h-44 flex flex-col items-center justify-center text-center text-slate-500 border border-dashed border-cyan-950 rounded-xl py-6 px-4 bg-cyan-950/5">
              <Cpu className="w-8 h-8 text-cyan-500/40 mb-2 animate-pulse" />
              <p className="text-xs font-semibold font-sans text-slate-400">Select a Node on the Graph</p>
              <p className="text-[10px] text-slate-500 mt-1 max-w-[200px] font-sans">
                Click any element on the map to display its definition, properties, and relationships.
              </p>
            </div>
          </div>
        )}

        {/* AI Copilot Panel (Sprint 3) */}
        <div className="border-t border-cyan-500/10 pt-4 flex flex-col h-[340px]">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-[9px] font-mono font-bold text-cyan-400 uppercase tracking-widest flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5" /> AI Copilot Workspace
            </h4>
            {chatMessages.length > 0 && (
              <button 
                onClick={clearChat}
                className="p-1 rounded text-slate-500 hover:text-slate-300 hover:bg-slate-800/40 transition-colors cursor-pointer"
                title="Clear Chat"
              >
                <Trash className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Chat scrolling log */}
          <div className="flex-1 overflow-y-auto space-y-3.5 pr-1 border border-cyan-500/10 bg-[#030c0b]/40 rounded-xl p-3 scrollbar-thin">
            {chatMessages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-3 text-slate-500 space-y-2">
                <Sparkles className="w-6 h-6 text-cyan-500/30 animate-pulse" />
                <p className="text-[10px] leading-relaxed font-semibold font-sans">
                  Ask me anything about the concepts, papers, or prerequisite routes. I'll ground my answer in your graph.
                </p>
              </div>
            ) : (
              chatMessages.map((msg, idx) => (
                <div 
                  key={idx} 
                  className={`flex flex-col max-w-[85%] rounded-xl px-3 py-2 text-[11px] leading-relaxed border ${
                    msg.role === 'user'
                      ? 'bg-cyan-500/10 border-cyan-500/15 text-cyan-200 self-end shadow-[0_0_10px_rgba(6,182,212,0.05)]'
                      : 'bg-cyan-950/15 border border-cyan-500/5 text-slate-300 self-start'
                  }`}
                >
                  <span className="text-[8px] font-mono font-bold uppercase text-cyan-400/55 mb-0.5 tracking-wider">
                    {msg.role === 'user' ? 'You' : 'Copilot'}
                  </span>
                  <p className="whitespace-pre-wrap font-sans font-medium">{msg.content || (chatLoading && idx === chatMessages.length - 1 ? 'Writing...' : '')}</p>
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
              className="flex-1 px-3 py-2 rounded-lg bg-[#030c0b] border border-cyan-500/10 text-xs text-cyan-100 placeholder-slate-600 focus:outline-none focus:border-cyan-500/40 disabled:opacity-50 transition-colors font-sans"
            />
            <button
              type="submit"
              disabled={chatLoading || !inputValue.trim()}
              className="p-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-900 text-white rounded-lg transition-colors flex-shrink-0 shadow-md cursor-pointer"
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
        const response = await fetch('http://localhost:8000/highlights');
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
    <footer className="w-full glass-panel border-t border-cyan-500/10 bg-[#030e0d]/70 select-none">
      {/* Bar Header Toggle */}
      <div 
        onClick={() => setIsExpanded(!isExpanded)}
        className="px-4 py-2 border-b border-cyan-500/5 flex items-center justify-between cursor-pointer hover:bg-cyan-950/10 transition-colors"
      >
        <span className="text-[9px] font-mono font-bold text-cyan-400/80 uppercase tracking-widest flex items-center gap-1.5">
          Highlights · Bookmarks · Recent Insights
        </span>
        <button className="text-cyan-400 hover:text-white cursor-pointer">
          {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
        </button>
      </div>

      {/* Content drawer */}
      {isExpanded && (
        <div className="h-[92px] p-3 overflow-x-auto flex gap-3 scrollbar-thin">
          {highlights.length === 0 ? (
            <div className="min-w-[260px] max-w-[260px] h-full rounded-lg border border-dashed border-cyan-950 p-3 flex flex-col justify-center items-center text-center text-[10px] text-slate-500 font-medium font-sans">
              No highlights saved yet. Select document text to save key insights.
            </div>
          ) : (
            highlights.map((hl) => (
              <div key={hl.id} className="min-w-[240px] max-w-[240px] p-2.5 glass-card rounded-lg border border-cyan-500/10 hover:border-cyan-500/20 flex flex-col justify-between transition-all">
                <p className="text-[10px] text-slate-300 italic line-clamp-2 leading-relaxed font-semibold font-sans">
                  "{hl.text}"
                </p>
                <div className="flex justify-between items-center text-[8px] text-cyan-400 font-mono font-bold uppercase tracking-wider">
                  <span className="truncate max-w-[150px] font-sans">{hl.doc_title}</span>
                  <span className="text-[8px] font-bold text-slate-500 flex-shrink-0">PAGE {hl.page}</span>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </footer>
  );
}
