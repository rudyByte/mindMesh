import React from 'react';
import { useStore } from '../store/useStore';
import { X, Search, BookOpen, ChevronRight, AlertCircle, Loader2 } from 'lucide-react';

export default function LearningRoadmap() {
  const isLearningMode = useStore((state) => state.isLearningMode);
  const setIsLearningMode = useStore((state) => state.setIsLearningMode);
  const gapPrerequisites = useStore((state) => state.gapPrerequisites);
  const gapLoading = useStore((state) => state.gapLoading);
  const gapError = useStore((state) => state.gapError);
  const setSelectedNode = useStore((state) => state.setSelectedNode);
  const selectedNode = useStore((state) => state.selectedNode);

  if (!isLearningMode) return null;

  return (
    <div className="absolute inset-0 z-40 bg-[#030c0b]/95 backdrop-blur-xl flex flex-col items-center justify-start overflow-y-auto overflow-x-hidden p-4 md:p-8 font-sans animate-in fade-in duration-500 text-slate-200">
      
      {/* Header */}
      <div className="w-full max-w-4xl flex items-center justify-between mb-8 sticky top-0 z-50 bg-[#030c0b]/90 py-4 border-b border-cyan-500/20 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-cyan-950/50 border border-cyan-500/30 flex items-center justify-center shadow-[0_0_15px_rgba(6,182,212,0.15)]">
            <BookOpen className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white tracking-wide">Learning Roadmap</h2>
            <p className="text-xs text-cyan-400/70 font-mono tracking-widest uppercase mt-0.5">
              TARGET: {selectedNode?.name || 'Concept'}
            </p>
          </div>
        </div>
        
        <button
          onClick={() => setIsLearningMode(false)}
          className="flex items-center gap-2 px-4 py-2 bg-slate-800/50 hover:bg-red-950/40 border border-slate-700 hover:border-red-500/30 text-slate-300 hover:text-red-400 rounded-lg transition-all text-xs font-bold uppercase tracking-wider cursor-pointer shadow-sm"
        >
          <X className="w-4 h-4" /> Exit Learning Mode
        </button>
      </div>

      {/* Content */}
      <div className="w-full max-w-3xl flex-1 flex flex-col pb-20 relative">
        
        {gapLoading && (
          <div className="flex-1 flex flex-col items-center justify-center gap-4 text-cyan-400/80 mt-20">
            <Loader2 className="w-10 h-10 animate-spin" />
            <p className="text-sm font-mono uppercase tracking-widest animate-pulse">Generating Roadmap...</p>
          </div>
        )}

        {gapError && !gapLoading && (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 text-red-400 mt-20 p-8 glass-card border border-red-500/20 bg-red-950/10 rounded-2xl">
            <AlertCircle className="w-8 h-8" />
            <p className="text-sm">{gapError}</p>
          </div>
        )}

        {!gapLoading && !gapError && gapPrerequisites.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 text-slate-400 mt-20 p-8 glass-card border border-cyan-500/10 bg-cyan-950/5 rounded-2xl text-center">
            <Search className="w-8 h-8 text-cyan-500/50 mb-2" />
            <p className="text-base font-bold text-slate-300">No prerequisites found.</p>
            <p className="text-xs">You may be ready to tackle this concept directly!</p>
          </div>
        )}

        {/* Timeline / Nodes */}
        {!gapLoading && !gapError && gapPrerequisites.length > 0 && (
          <div className="relative pl-6 md:pl-10 space-y-8 py-8 before:absolute before:inset-y-0 before:left-[19px] md:before:left-[35px] before:w-[2px] before:bg-gradient-to-b before:from-cyan-500/50 before:to-transparent">
            {gapPrerequisites.map((prereq, idx) => {
              const isSelected = selectedNode?.id === prereq.id;
              return (
                <div 
                  key={prereq.nodeId || prereq.id || idx}
                  className="relative group cursor-pointer"
                  onClick={() => {
                    // Normalize the object for the global store to ensure id exists
                    setSelectedNode({
                      ...prereq,
                      id: prereq.nodeId || prereq.id
                    });
                  }}
                >
                  {/* Timeline Node Ring */}
                  <div className={`absolute -left-[37px] md:-left-[53px] top-4 w-4 h-4 rounded-full border-2 bg-[#030c0b] z-10 transition-colors duration-300 ${isSelected ? 'border-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.5)]' : 'border-cyan-500 group-hover:border-cyan-300 group-hover:shadow-[0_0_8px_rgba(6,182,212,0.4)]'}`} />
                  
                  {/* Card */}
                  <div className={`p-5 rounded-xl border backdrop-blur-md transition-all duration-300 ${
                    isSelected 
                      ? 'bg-emerald-950/20 border-emerald-500/40 shadow-[0_0_20px_rgba(52,211,153,0.1)]' 
                      : 'bg-cyan-950/10 border-cyan-500/20 hover:bg-cyan-950/20 hover:border-cyan-500/40 hover:shadow-lg hover:shadow-cyan-900/20 hover:-translate-y-0.5'
                  }`}>
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border uppercase tracking-wider ${isSelected ? 'bg-emerald-500/20 border-emerald-500/30 text-emerald-300' : 'bg-cyan-500/10 border-cyan-500/30 text-cyan-300'}`}>
                            Step {idx + 1}
                          </span>
                          <h3 className={`text-lg font-bold ${isSelected ? 'text-emerald-50' : 'text-slate-100'}`}>
                            {prereq.name}
                          </h3>
                        </div>
                        {(prereq.reason || prereq.description) && (
                          <p className={`text-sm leading-relaxed ${isSelected ? 'text-emerald-100/70' : 'text-slate-400'}`}>
                            {prereq.reason || prereq.description}
                          </p>
                        )}
                      </div>
                      
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 transition-colors ${isSelected ? 'bg-emerald-500/20 text-emerald-400' : 'bg-cyan-500/10 text-cyan-500/50 group-hover:text-cyan-400 group-hover:bg-cyan-500/20'}`}>
                        <ChevronRight className="w-4 h-4" />
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
