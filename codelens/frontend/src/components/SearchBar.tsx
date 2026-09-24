import React from 'react';
import { Search, Sliders, Zap, Hash } from 'lucide-react';
import { RepoSelector } from './RepoSelector';

interface SearchBarProps {
  query: string;
  setQuery: (q: string) => void;
  onSearch: () => void;
  useHybrid: boolean;
  setUseHybrid: (val: boolean) => void;
  alpha: number;
  setAlpha: (val: number) => void;
  topK: number;
  setTopK: (k: number) => void;
  selectedRepos: string[];
  setSelectedRepos: (repos: string[], paths?: Record<string, string>) => void;
  inputRef: React.RefObject<HTMLInputElement | null>;
}

export const SearchBar: React.FC<SearchBarProps> = ({
  query,
  setQuery,
  onSearch,
  useHybrid,
  setUseHybrid,
  alpha,
  setAlpha,
  topK,
  setTopK,
  selectedRepos,
  setSelectedRepos,
  inputRef,
}) => {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      onSearch();
    }
  };

  return (
    <div className="bg-[#161b22] border-b border-[#30363d] p-6 space-y-4">
      {/* Main Search Bar */}
      <div className="relative flex items-center">
        <div className="absolute left-4 pointer-events-none text-gray-400">
          <Search className="w-5 h-5 text-blue-400" />
        </div>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Describe what you want to find in plain English (e.g. 'Where is health check handled?' or 'BM25 search engine logic')"
          className="w-full bg-[#0d1117] border border-[#30363d] focus:border-blue-500 rounded-xl pl-12 pr-28 py-3.5 text-sm text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all font-sans"
        />
        <div className="absolute right-3 flex items-center space-x-2">
          <kbd className="hidden sm:inline-block px-2 py-1 text-[10px] font-mono font-semibold text-gray-400 bg-[#21262d] border border-[#30363d] rounded shadow-inner">
            /
          </kbd>
          <button
            onClick={onSearch}
            className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-semibold text-xs px-4 py-2 rounded-lg transition-all shadow-md shadow-blue-600/20"
          >
            Search Code
          </button>
        </div>
      </div>

      {/* Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 pt-1">
        {/* Retrieval Mode Pills */}
        <div className="flex items-center space-x-2">
          <span className="text-xs font-semibold text-gray-400 flex items-center gap-1">
            <Zap className="w-3.5 h-3.5 text-amber-400" /> Search Strategy:
          </span>
          <div className="bg-[#0d1117] border border-[#30363d] p-1 rounded-lg flex space-x-1">
            <button
              onClick={() => setUseHybrid(true)}
              className={`px-3 py-1 text-xs rounded-md font-medium transition-all ${
                useHybrid
                  ? 'bg-blue-600 text-white shadow-sm font-bold'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
              title="Hybrid: Blends exact word search with conceptual AI search"
            >
              Smart Hybrid (Recommended)
            </button>
            <button
              onClick={() => setUseHybrid(false)}
              className={`px-3 py-1 text-xs rounded-md font-medium transition-all ${
                !useHybrid
                  ? 'bg-blue-600 text-white shadow-sm font-bold'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
              title="Dense Only: Searches purely by conceptual meaning"
            >
              Conceptual Only
            </button>
          </div>
        </div>

        {/* Alpha Balance Slider */}
        {useHybrid && (
          <div className="flex items-center space-x-3 bg-[#0d1117] border border-[#30363d] px-3 py-1.5 rounded-lg text-xs">
            <Sliders className="w-3.5 h-3.5 text-blue-400" />
            <span className="text-gray-400" title="Exact Keyword Match weight">Exact Words</span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={alpha}
              onChange={(e) => setAlpha(parseFloat(e.target.value))}
              className="w-20 accent-blue-500 cursor-pointer"
            />
            <span className="text-gray-400" title="Conceptual Meaning weight">Meaning</span>
          </div>
        )}

        {/* Results Limit */}
        <div className="flex items-center space-x-2 text-xs">
          <Hash className="w-3.5 h-3.5 text-purple-400" />
          <span className="text-gray-400">Max Results:</span>
          <select
            value={topK}
            onChange={(e) => setTopK(parseInt(e.target.value))}
            className="bg-[#0d1117] border border-[#30363d] text-gray-200 rounded-md px-2 py-1 focus:outline-none font-mono"
          >
            <option value={5}>5 snippets</option>
            <option value={10}>10 snippets</option>
            <option value={20}>20 snippets</option>
          </select>
        </div>

        {/* Multi / Single / All Repository Dropdown Selector */}
        <RepoSelector
          selectedRepos={selectedRepos}
          onChangeSelectedRepos={(repos, paths) => setSelectedRepos(repos, paths)}
        />
      </div>
    </div>
  );
};
