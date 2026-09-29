import React from 'react';
import { Search, GitCommit, RefreshCw, Cpu, BookOpen } from 'lucide-react';
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
    <header className="app-header bg-[#050505] border-b border-[#242525] px-5 py-3 flex flex-wrap items-center justify-between gap-3 sticky top-0 z-40">
      {/* Brand & Logo */}
      <div className="flex items-center space-x-3.5">
        <div className="w-8 h-8 rounded-md bg-[#171613] border border-[#3a3326] flex items-center justify-center">
          <Search className="w-4 h-4 text-[#d6a85f]" />
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="font-semibold text-[17px] text-[#e7e4dc] tracking-tight">CodeLens</h1>
          </div>
        </div>
      </div>

      {/* Controls & Actions */}
      <div className="flex items-center space-x-3">
        {/* Help & Guide Button for Non-Engineers */}
        <button
          onClick={onOpenHelpModal}
          className="header-guide flex items-center space-x-1.5 text-gray-400 hover:text-gray-100 text-xs font-medium px-2 py-1.5 rounded-md border border-transparent hover:border-[#30363d] transition-colors"
          title="Open Plain English Guide & Glossary"
        >
          <BookOpen className="w-3.5 h-3.5 text-[#a3a09a]" />
          <span>Guide & Glossary</span>
        </button>

        {/* Commit / Code Snapshot Selector */}
        <div className="flex items-center space-x-2 bg-[#080909] border border-[#242525] rounded-lg px-3 py-1.5 text-xs text-gray-300">
          <GitCommit className="w-3.5 h-3.5 text-[#d6a85f]" />
          <span className="text-gray-400">Snapshot</span>
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
          className="flex items-center space-x-1.5 bg-[#121313] hover:bg-[#1a1b1a] text-gray-200 text-xs font-medium px-3 py-1.5 rounded-lg border border-[#242525] transition-colors"
          title="Index a new repository folder"
        >
          <RefreshCw className="w-3.5 h-3.5 text-[#d6a85f]" />
          <span>Rebuild Index</span>
        </button>

        {/* System Health Indicator */}
        <div className="hidden md:flex items-center space-x-2 bg-transparent border border-transparent rounded-lg px-2 py-1.5 text-xs">
          <Cpu className="w-3.5 h-3.5 text-[#777777]" />
          {health ? (
            <div className="flex items-center space-x-1.5">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#4faf73]"></span>
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
