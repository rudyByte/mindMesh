'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useStore } from '../../store/useStore';
import { Database, LogIn, GraduationCap, Compass, Sparkles } from 'lucide-react';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<'student' | 'researcher'>('student');
  const login = useStore((state) => state.login);
  const router = useRouter();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    
    // Perform simulated login
    login(email, role);
    router.push('/');
  };

  return (
    <main className="min-h-screen w-full flex items-center justify-center bg-[#070b13] relative overflow-hidden px-4 select-none">
      {/* Background blobs */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-indigo-500/10 rounded-full filter blur-3xl" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full filter blur-3xl" />

      <div className="w-full max-w-md p-8 glass-panel rounded-2xl shadow-2xl relative z-10 space-y-6">
        {/* Brand identity */}
        <div className="text-center space-y-2">
          <div className="mx-auto w-12 h-12 rounded-xl bg-indigo-600 flex items-center justify-center text-white shadow-lg glow-active">
            <Database className="w-6 h-6" />
          </div>
          <h2 className="text-2xl font-extrabold text-white tracking-wider uppercase">MINDMESH AI</h2>
          <p className="text-xs text-indigo-400 font-bold tracking-widest uppercase">Google Maps for Knowledge</p>
        </div>

        {/* Auth form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">Email Address</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@example.com"
              className="w-full px-4 py-2.5 rounded-xl bg-slate-900/60 border border-slate-800 text-slate-100 text-sm focus:outline-none focus:border-indigo-500/80 transition-colors"
            />
          </div>

          <div className="space-y-1">
            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-4 py-2.5 rounded-xl bg-slate-900/60 border border-slate-800 text-slate-100 text-sm focus:outline-none focus:border-indigo-500/80 transition-colors"
            />
          </div>

          {/* Role selector */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">Select Persona</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setRole('student')}
                className={`py-3 px-4 rounded-xl border flex flex-col items-center gap-1.5 transition-all ${
                  role === 'student'
                    ? 'border-indigo-500 bg-indigo-500/10 text-white shadow-lg'
                    : 'border-slate-800 bg-slate-900/40 text-slate-400 hover:text-slate-200'
                }`}
              >
                <GraduationCap className="w-5 h-5" />
                <span className="text-xs font-bold">Student</span>
              </button>
              
              <button
                type="button"
                onClick={() => setRole('researcher')}
                className={`py-3 px-4 rounded-xl border flex flex-col items-center gap-1.5 transition-all ${
                  role === 'researcher'
                    ? 'border-indigo-500 bg-indigo-500/10 text-white shadow-lg'
                    : 'border-slate-800 bg-slate-900/40 text-slate-400 hover:text-slate-200'
                }`}
              >
                <Compass className="w-5 h-5" />
                <span className="text-xs font-bold">Researcher</span>
              </button>
            </div>
          </div>

          {/* Submit */}
          <button
            type="submit"
            className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-extrabold text-sm rounded-xl flex items-center justify-center gap-2 shadow-lg hover:shadow-indigo-500/25 transition-all"
          >
            <LogIn className="w-4 h-4" />
            Enter MindMesh
          </button>
        </form>

        {/* Footer info */}
        <div className="text-center text-[10px] text-slate-500 font-medium">
          By continuing, you agree to connect your local storage and model environment parameters.
        </div>
      </div>
    </main>
  );
}
