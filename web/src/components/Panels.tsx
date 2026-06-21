'use client';

import React, { useState } from 'react';
import { useStore, GraphNode } from '../store/useStore';
import { 
  FileText, Plus, Database, Cpu, HelpCircle, 
  Map, Sparkles, BookOpen, GraduationCap, 
  ArrowRight, Landmark, Tag, ChevronDown, ChevronUp, UserCheck
} from 'lucide-react';

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
      <div className="px-4 py-3 border-b border-slate-800/60 flex items-center gap-2 bg-slate-900/20">
        <UserCheck className="w-4 h-4 text-emerald-400" />
        <div className="min-w-0">
          <p className="text-xs font-semibold text-slate-300 truncate">{user?.email || 'Guest User'}</p>
          <p className="text-[9px] text-slate-500 font-medium capitalize">{user?.role || 'student'}</p>
        </div>
      </div>

      {/* Ingest Actions */}
      <div className="p-3">
        <button
          onClick={onOpenUpload}
          className="w-full py-2 px-3.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white rounded-xl font-bold text-xs flex items-center justify-center gap-2 shadow-lg hover:shadow-indigo-500/25 transition-all duration-200"
        >
          <Plus className="w-4 h-4" />
          Ingest Document
        </button>
      </div>

      {/* Pages Navigation */}
      <nav className="flex-1 px-2.5 py-2 overflow-y-auto space-y-1">
        <div className="text-[10px] text-slate-500 font-bold px-2 py-1 tracking-wider">SECTIONS</div>
        <a href="#" className="flex items-center gap-2.5 px-3 py-2 text-xs font-bold text-slate-300 bg-white/5 rounded-lg border border-white/5"><GraduationCap className="w-4 h-4 text-indigo-400" /> Concepts</a>
        <a href="#" className="flex items-center gap-2.5 px-3 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 hover:bg-white/5 rounded-lg transition-colors"><BookOpen className="w-4 h-4" /> Papers</a>
        <a href="#" className="flex items-center gap-2.5 px-3 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 hover:bg-white/5 rounded-lg transition-colors"><Landmark className="w-4 h-4" /> Authors</a>
        <a href="#" className="flex items-center gap-2.5 px-3 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 hover:bg-white/5 rounded-lg transition-colors"><Tag className="w-4 h-4" /> Keywords</a>
        <a href="#" className="flex items-center gap-2.5 px-3 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 hover:bg-white/5 rounded-lg transition-colors"><Map className="w-4 h-4" /> Learning Paths</a>

        {/* Documents Queue */}
        <div className="pt-4 space-y-1">
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
      </nav>

      {/* Footer Support Info */}
      <div className="p-4 border-t border-slate-800 flex items-center justify-between text-[10px] text-slate-500 font-medium">
        <span className="flex items-center gap-1.5"><HelpCircle className="w-3.5 h-3.5" /> Docs</span>
        <span>Sprint 2 Live</span>
      </div>
    </aside>
  );
}

// ==================== RIGHT SIDEBAR ====================
import { useEffect, useRef } from 'react';
import { Send, Trash } from 'lucide-react';

export function RightSidebar() {
  const selectedNode = useStore((state) => state.selectedNode);
  const user = useStore((state) => state.user);
  
  // Chat state
  const chatMessages = useStore((state) => state.chatMessages);
  const chatLoading = useStore((state) => state.chatLoading);
  const addChatMessage = useStore((state) => state.addChatMessage);
  const updateLastChatMessage = useStore((state) => state.updateLastChatMessage);
  const setChatLoading = useStore((state) => state.setChatLoading);
  const clearChat = useStore((state) => state.clearChat);

  // Local state
  const [contextCard, setContextCard] = useState<any>(null);
  const [contextLoading, setContextLoading] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

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
            {contextCard && (
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
            )}

            {/* Quick Actions (Sprint 3) */}
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
          </div>
        ) : (
          <div className="h-44 flex flex-col items-center justify-center text-center text-slate-500 border border-dashed border-slate-800 rounded-xl py-6 px-4 bg-slate-900/10">
            <Cpu className="w-8 h-8 text-slate-600 mb-2 animate-pulse" />
            <p className="text-xs font-semibold">Select a Node on the Graph</p>
            <p className="text-[10px] text-slate-500 mt-1 max-w-[200px]">
              Click any element on the map to display its definition, properties, and relationships.
            </p>
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

  return (
    <footer className="w-full glass-panel border-t border-slate-800 bg-[#0d1323]/80 select-none">
      {/* Bar Header Toggle */}
      <div 
        onClick={() => setIsExpanded(!isExpanded)}
        className="px-4 py-2 border-b border-slate-800/50 flex items-center justify-between cursor-pointer hover:bg-white/5 transition-colors"
      >
        <span className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest flex items-center gap-1.5">
          Highlights · Bookmarks · Recent Nodes
        </span>
        <button className="text-slate-400 hover:text-white">
          {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
        </button>
      </div>

      {/* Content drawer */}
      {isExpanded && (
        <div className="h-[92px] p-3 overflow-x-auto flex gap-3 scrollbar-thin">
          <div className="min-w-[200px] max-w-[200px] h-full rounded-lg border border-dashed border-slate-800 p-2 flex flex-col justify-center items-center text-center text-[10px] text-slate-500 font-medium">
            No highlights saved yet.
          </div>
          <div className="min-w-[240px] max-w-[240px] p-2.5 glass-card rounded-lg border border-slate-800 flex flex-col justify-between">
            <p className="text-[10px] text-slate-400 italic line-clamp-2 leading-relaxed">
              "Attention weights denote how strongly tokens connect dynamically."
            </p>
            <div className="flex justify-between items-center text-[8px] text-indigo-400 font-bold uppercase tracking-wide">
              <span>Attention Paper</span>
              <span className="text-[8px] font-medium text-slate-500">Page 4</span>
            </div>
          </div>
        </div>
      )}
    </footer>
  );
}
