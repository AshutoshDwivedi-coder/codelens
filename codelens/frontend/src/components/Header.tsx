import React from 'react';
import { Search, GitCommit, RefreshCw, Cpu, BookOpen, HelpCircle } from 'lucide-react';
import { HealthResponse } from '../api';

interface HeaderProps {
  health: HealthResponse | null;
  commits: string[];
  selectedCommit: string;
  onSelectCommit: (commit: string) => void;
  onOpenIndexModal: () => void;
  onOpenHelpModal: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  health,
  commits,
  selectedCommit,
  onSelectCommit,
  onOpenIndexModal,
  onOpenHelpModal,
}) => {
  return (
    <header className="bg-[#161b22] border-b border-[#30363d] px-6 py-3.5 flex flex-wrap items-center justify-between gap-4 sticky top-0 z-40 shadow-md">
      {/* Brand & Logo */}
      <div className="flex items-center space-x-3.5">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/20">
          <Search className="w-5 h-5 text-white" />
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="font-bold text-lg text-white tracking-tight">CodeLens</h1>
            <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
              v1.0.0 CPU-Fast
            </span>
          </div>
        </div>
      </div>

      {/* Controls & Actions */}
      <div className="flex items-center space-x-3">
        {/* Help & Guide Button for Non-Engineers */}
        <button
          onClick={onOpenHelpModal}
          className="flex items-center space-x-1.5 bg-gradient-to-r from-purple-600/20 to-indigo-600/20 hover:from-purple-600/30 hover:to-indigo-600/30 text-purple-200 text-xs font-semibold px-3 py-1.5 rounded-lg border border-purple-500/30 transition-all shadow-sm"
          title="Open Plain English Guide & Glossary"
        >
          <BookOpen className="w-3.5 h-3.5 text-purple-400" />
          <span>Guide & Glossary</span>
        </button>

        {/* Commit / Code Snapshot Selector */}
        <div className="flex items-center space-x-2 bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-1.5 text-xs text-gray-300">
          <GitCommit className="w-4 h-4 text-purple-400" />
          <span className="text-gray-400">Snapshot:</span>
          <select
            value={selectedCommit}
            onChange={(e) => onSelectCommit(e.target.value)}
            className="bg-transparent text-gray-200 font-mono focus:outline-none cursor-pointer"
            title="Select project version / git commit"
          >
            <option value="HEAD" className="bg-[#161b22]">Latest Code (HEAD)</option>
            {commits.map((c) => (
              <option key={c} value={c} className="bg-[#161b22]">
                Commit {c.substring(0, 7)}
              </option>
            ))}
          </select>
        </div>

        {/* Index Action Button */}
        <button
          onClick={onOpenIndexModal}
          className="flex items-center space-x-1.5 bg-[#21262d] hover:bg-[#30363d] text-gray-200 text-xs font-medium px-3 py-1.5 rounded-lg border border-[#30363d] transition-colors"
          title="Index a new repository folder"
        >
          <RefreshCw className="w-3.5 h-3.5 text-blue-400" />
          <span>Rebuild Index</span>
        </button>

        {/* System Health Indicator */}
        <div className="hidden md:flex items-center space-x-2 bg-[#0d1117] border border-[#30363d] rounded-lg px-3 py-1.5 text-xs">
          <Cpu className="w-3.5 h-3.5 text-emerald-400" />
          {health ? (
            <div className="flex items-center space-x-1.5">
              <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span className="text-gray-300 font-medium">System Ready</span>
            </div>
          ) : (
            <div className="flex items-center space-x-1.5">
              <span className="inline-block w-2 h-2 rounded-full bg-amber-500 animate-ping"></span>
              <span className="text-amber-400">Connecting...</span>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
