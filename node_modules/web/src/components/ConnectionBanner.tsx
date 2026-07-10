'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { AlertTriangle, X, RefreshCw } from 'lucide-react';
import { API_BASE_URL, checkApiHealth } from '../lib/api';

export function ConnectionBanner() {
  const [isConnected, setIsConnected] = useState<boolean | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [checking, setChecking] = useState(false);

  const checkConnection = useCallback(async () => {
    setChecking(true);
    const ok = await checkApiHealth();
    setIsConnected(ok);
    setChecking(false);
  }, []);

  useEffect(() => {
    checkConnection();
    const interval = setInterval(checkConnection, 30000);
    return () => clearInterval(interval);
  }, [checkConnection]);

  // Don't show anything while first check is pending, and hide if connected
  if (isConnected === null || isConnected || dismissed) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-50 px-4 py-2.5 bg-rose-950/90 backdrop-blur border-b border-rose-800/50 flex items-center justify-between gap-3 shadow-xl">
      <div className="flex items-center gap-2.5 text-sm">
        <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
        <span className="text-rose-200 font-semibold text-xs">
          Can&apos;t connect to the API backend at <code className="text-rose-300 bg-rose-950 px-1.5 py-0.5 rounded text-[10px] font-mono">{API_BASE_URL}</code>
        </span>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={checkConnection}
          disabled={checking}
          className="px-2.5 py-1 text-[10px] font-bold text-rose-300 hover:text-rose-100 bg-rose-950/60 hover:bg-rose-900/60 border border-rose-800/40 rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50"
        >
          <RefreshCw className={`w-3 h-3 ${checking ? 'animate-spin' : ''}`} />
          Retry
        </button>
        <button
          onClick={() => setDismissed(true)}
          className="p-1 rounded text-rose-400 hover:text-rose-200 hover:bg-rose-900/40 transition-colors"
          aria-label="Dismiss"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
