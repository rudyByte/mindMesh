import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, BookOpen, ChevronRight, Milestone, Zap, Activity, Cpu, Code, Atom, ChevronLeft, Loader2 } from 'lucide-react';
import { useStore, GraphNode } from '../store/useStore';
import { API_BASE_URL } from '../lib/api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export interface RoadmapNode {
  name: string;
  description?: string;
  [key: string]: any;
}

export interface LearningRoadmapOverlayProps {
  isOpen: boolean;
  selectedNode: any;
  roadmap: RoadmapNode[];
  onClose: () => void;
  onLearnThis: (node: RoadmapNode, e?: React.MouseEvent) => void;
}

export default function LearningRoadmapOverlay({
  isOpen,
  selectedNode,
  roadmap,
  onClose,
  onLearnThis,
}: LearningRoadmapOverlayProps) {
  const [activeSubTopic, setActiveSubTopic] = useState<any>(null);
  const [localStudyGuide, setLocalStudyGuide] = useState<any>(null);
  const [isGuideLoading, setIsGuideLoading] = useState(false);

  const user = useStore((state) => state.user);
  const activeDocumentId = useStore((state) => state.activeDocumentId);

  const getIconForStep = (name: string) => {
    const lowerName = name.toLowerCase();
    if (lowerName.includes('charge') || lowerName.includes('potential') || lowerName.includes('voltage')) {
      return <Zap className="w-4 h-4 text-cyan-400" />;
    }
    if (lowerName.includes('current') || lowerName.includes('wave')) {
      return <Activity className="w-4 h-4 text-cyan-400" />;
    }
    if (lowerName.includes('resistance') || lowerName.includes('circuit')) {
      return <Cpu className="w-4 h-4 text-cyan-400" />;
    }
    if (lowerName.includes('syntax') || lowerName.includes('variables') || lowerName.includes('memory') || lowerName.includes('oop')) {
      return <Code className="w-4 h-4 text-cyan-400" />;
    }
    return <Atom className="w-4 h-4 text-cyan-400" />;
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="absolute inset-0 z-50 flex items-center justify-center p-4 bg-[#010605]/80 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
        >
          <motion.div
            className="relative w-full max-w-[800px] max-h-[85vh] flex flex-col bg-[#030c0b]/95 backdrop-blur-xl border border-cyan-500/30 rounded-2xl shadow-[0_0_40px_rgba(6,182,212,0.15)] overflow-hidden font-sans"
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-cyan-500/20 bg-cyan-950/20">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-cyan-900/40 border border-cyan-500/30 flex items-center justify-center shadow-[0_0_15px_rgba(6,182,212,0.2)]">
                  <BookOpen className="w-5 h-5 text-cyan-400" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-slate-100 tracking-wide">
                    Learning Roadmap
                  </h2>
                  <p className="text-xs text-cyan-400/80 font-mono tracking-widest uppercase mt-0.5">
                    Target: {selectedNode?.name || 'Concept'}
                  </p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="p-2 rounded-lg bg-slate-800/50 hover:bg-red-950/40 border border-slate-700/50 hover:border-red-500/30 text-slate-400 hover:text-red-400 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content / Roadmap Steps */}
            <div className="flex-1 overflow-y-auto p-6 md:p-8 custom-scrollbar">
              {activeSubTopic ? (() => {
                let finalDefinition = localStudyGuide?.definition || activeSubTopic.description || `${activeSubTopic.name} is a concept extracted from your uploaded document.`;
                let finalHowItWorks = localStudyGuide?.how_it_works || "Use the graph links around this node to understand how it fits into the document-local learning path.";
                let finalFormula = localStudyGuide?.formula_syntax || "No formula or syntax was grounded for this concept yet.";
                let finalProperties = localStudyGuide?.properties || "• Document-local concept\n• Dynamic roadmap step\n• Grounded by extracted graph context";

                const currentName = activeSubTopic.name.toLowerCase();

                if (false && currentName.includes('array')) {
                  finalDefinition = "An Array is a linear data structure that stores a collection of elements of the same data type in contiguous (sequential) memory locations.";
                  finalHowItWorks = "Since memory is sequential, the system uses a base pointer index calculation: Address = BaseAddress + (Index * ElementSize). This allows instant random access with an O(1) time complexity.";
                  finalFormula = "int[] arr = new int[5];\narr[0] = 10; // Zero-indexed access";
                  finalProperties = "• Contiguous memory allocation\n• Fixed capacity size constraint\n• Fast O(1) random lookup element retrieval";
                } else if (false && (currentName.includes('syntax') || currentName.includes('basic'))) {
                  finalDefinition = "Basic Programming Syntax defines the foundational structural laws, tokens, and rules for writing valid, compilable code statements in a language.";
                  finalHowItWorks = "The code parser and compiler scan tokens sequentially. If keywords, data types, brackets, or semicolons violate grammar constraints, the build logs break immediately.";
                  finalFormula = "public static void main(String[] args) {\n    System.out.println(\"Hello World\");\n}";
                  finalProperties = "• Enforces strict source code layout\n• Parsed directly by lexical analyzers\n• Eliminates structural runtime syntax bugs";
                } else if (false && (currentName.includes('java core') || currentName.includes('core java'))) {
                  finalDefinition = "Java Core handles the foundational engine ecosystem of Java, managing bytecode instructions, object references, and execution thread contexts.";
                  finalHowItWorks = "Java source code is compiled down into architecture-neutral .class bytecode, which is then interpreted and executed line-by-line via the Java Virtual Machine (JVM).";
                  finalFormula = "Compile: javac App.java\nRun: java App";
                  finalProperties = "• Platform Independent (WORA architecture)\n• Automated background Garbage Collection\n• Strong Type Safety checks";
                } else if (false && (currentName.includes('voltage') || currentName.includes('potential'))) {
                  finalDefinition = "Voltage, or electric potential difference, is the pressure from an electrical circuit's power source that pushes charged electrons through a conducting loop.";
                  finalHowItWorks = "Think of it as water pressure in a pipe. Higher pressure forces more water to drift; similarly, higher voltage pushes a stronger flow of electrons to do real work.";
                  finalFormula = "V = I × R (Ohm's Law) or V = W / Q";
                  finalProperties = "• SI Unit: Volts (V)\n• Measured using an isolated Voltmeter";
                } else if (false && currentName.includes('charge')) {
                  finalDefinition = "Electric Charge is the physical property of atomic matter that causes it to experience an inward or outward force when placed within an electromagnetic field.";
                  finalHowItWorks = "Protons carry positive charges and electrons carry negative charges. Stationary charges generate electric fields, while moving charges generate magnetic fields.";
                  finalFormula = "Q = I × t (Current × Time) or Q = n × e";
                  finalProperties = "• SI Unit: Coulombs (C)\n• Quantized and universally conserved property";
                }

                return (
                  <div className="flex flex-col gap-6 p-4 text-zinc-100 max-h-[70vh] overflow-y-auto custom-scrollbar">
                    {/* Header & Back Action */}
                    <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
                      <div>
                        <span className="text-xs font-semibold tracking-wider uppercase text-cyan-400">Concept Study Guide</span>
                        <h2 className="text-2xl font-bold text-white mt-1">{activeSubTopic.name}</h2>
                      </div>
                      <button 
                        onClick={(e) => { e.preventDefault(); e.stopPropagation(); setActiveSubTopic(null); }}
                        className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-sm font-medium text-zinc-200 rounded-lg transition-colors cursor-pointer"
                      >
                        ← Back to Roadmap
                      </button>
                    </div>

                    {/* Clean Academic Content Blocks */}
                    <div className="space-y-4">
                      <div className="bg-zinc-900/40 p-4 rounded-xl border border-zinc-800/60">
                        <h3 className="text-sm font-semibold text-cyan-400 uppercase tracking-wider mb-2">Core Definition</h3>
                        <p className="text-zinc-300 text-sm leading-relaxed">
                          {finalDefinition}
                        </p>
                      </div>

                      <div className="bg-zinc-900/40 p-4 rounded-xl border border-zinc-800/60">
                        <h3 className="text-sm font-semibold text-cyan-400 uppercase tracking-wider mb-2">How It Works</h3>
                        <p className="text-zinc-300 text-sm leading-relaxed">
                          {finalHowItWorks}
                        </p>
                      </div>

                      {/* Research / Formulas / Unit Blocks */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="bg-zinc-900/40 p-4 rounded-xl border border-zinc-800/60">
                          <h3 className="text-sm font-semibold text-amber-400 uppercase tracking-wider mb-1">Formula & Technical Syntax</h3>
                          <p className="text-zinc-300 font-mono text-xs bg-zinc-950 p-3 rounded-lg border border-zinc-900 mt-2 whitespace-pre-wrap">
                            {finalFormula}
                          </p>
                        </div>
                        <div className="bg-zinc-900/40 p-4 rounded-xl border border-zinc-800/60">
                          <h3 className="text-sm font-semibold text-emerald-400 uppercase tracking-wider mb-1">Key Research Properties</h3>
                          <p className="text-zinc-300 text-xs mt-2 leading-relaxed whitespace-pre-wrap">
                            {finalProperties}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })() : (!roadmap || roadmap.length === 0) ? (
                <div className="flex flex-col items-center justify-center py-12 text-slate-400">
                  <p className="text-sm font-medium">No prerequisites available for this concept.</p>
                </div>
              ) : (
                <div className="relative flex flex-col gap-6 pl-8">
                  {/* Vertical Timeline Connector Line */}
                  <div className="absolute left-[20px] top-4 bottom-4 w-[2px] bg-zinc-700" />

                  {roadmap.map((step, idx) => (
                    <motion.div
                      key={idx}
                      className="relative group"
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.05, duration: 0.3 }}
                    >
                      {/* Timeline Icon centered over the vertical line */}
                      <div className="absolute -left-[32px] top-4 w-10 h-10 rounded-full bg-[#030c0b] border-2 border-cyan-500/40 flex items-center justify-center z-10 group-hover:border-cyan-400 group-hover:shadow-[0_0_12px_rgba(6,182,212,0.4)] transition-all">
                        {getIconForStep(step.name)}
                      </div>

                      {/* Roadmap Card */}
                      <div 
                        className="p-5 rounded-xl border border-cyan-500/20 bg-cyan-950/10 hover:bg-cyan-950/20 hover:border-cyan-500/40 transition-all cursor-pointer flex items-start justify-between gap-4"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          
                          setActiveSubTopic(step);
                          setLocalStudyGuide(null);
                          setIsGuideLoading(true);

                          fetch(`${API_BASE_URL}/copilot/explain`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                              concept_name: step.name
                            }),
                          })
                          .then((response) => response.json())
                          .then((data) => {
                            setLocalStudyGuide(data);
                          })
                          .catch((err) => {
                            console.error('Streaming error', err);
                            setLocalStudyGuide({
                                definition: "*(Error connecting to AI Copilot. Check server connection.)*",
                                how_it_works: "N/A",
                                formula_syntax: "N/A",
                                properties: "N/A"
                            });
                          })
                          .finally(() => {
                            setIsGuideLoading(false);
                          });
                        }}
                      >
                        <div className="flex-1">
                          <div className="flex flex-wrap items-center gap-3 mb-2">
                            <span className="text-[10px] font-mono font-bold text-cyan-400 uppercase tracking-wider bg-cyan-500/10 border border-cyan-500/30 px-2.5 py-1 rounded-md">
                              Step {idx + 1}
                            </span>
                            
                            <h3 className="text-base font-bold text-slate-100 group-hover:text-cyan-50 transition-colors">
                              {step.name}
                            </h3>

                            {step.difficulty && (
                              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                                step.difficulty.toLowerCase().includes('easy') ? 'bg-green-500/10 text-green-400 border-green-500/20' :
                                step.difficulty.toLowerCase().includes('medium') ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' :
                                'bg-red-500/10 text-red-400 border-red-500/20'
                              } uppercase tracking-wider`}>
                                {step.difficulty}
                              </span>
                            )}
                          </div>
                          
                          {step.description && (
                            <p className="text-sm text-slate-400 leading-relaxed group-hover:text-slate-300 transition-colors pl-[2px]">
                              {step.description}
                            </p>
                          )}
                          
                          {step.duration && (
                            <p className="text-xs font-mono text-slate-500 mt-2 pl-[2px]">
                              ⏱ {step.duration}
                            </p>
                          )}
                        </div>
                        
                        <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-cyan-500/10 text-cyan-500/60 group-hover:bg-cyan-500/20 group-hover:text-cyan-400 transition-colors mt-1">
                          <ChevronRight className="w-4 h-4" />
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
