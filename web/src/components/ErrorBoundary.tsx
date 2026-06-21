'use client';

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children?: ReactNode;
  name?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(`ErrorBoundary caught an error in ${this.props.name || 'Component'}:`, error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="h-full w-full flex flex-col items-center justify-center p-6 text-center bg-slate-950/40 border border-slate-900 rounded-2xl">
          <div className="p-3 bg-rose-500/10 rounded-full text-rose-500 mb-3 animate-pulse">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <h3 className="text-xs font-bold text-slate-200 uppercase tracking-widest">
            {this.props.name || 'Component'} Error
          </h3>
          <p className="text-[10px] text-slate-500 mt-2 max-w-[200px] leading-relaxed">
            An error occurred while loading this view. You can reload or reset.
          </p>
          <button
            onClick={this.handleReset}
            className="mt-4 px-3.5 py-1.5 bg-slate-900 hover:bg-slate-850 text-slate-300 hover:text-white rounded-lg border border-slate-800 text-[10px] font-bold uppercase tracking-wider transition-all flex items-center gap-1.5 shadow-md cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Reload Panel
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
