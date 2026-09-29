import React from 'react';
import { Search, Sliders, Hash } from 'lucide-react';
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
  onAddRepository?: (repoPath: string) => void;
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
  onAddRepository,
}) => {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      onSearch();
    }
  };

  return (
    <div className="search-panel bg-[#0d1117] border-b border-[#30363d] px-7 py-6 space-y-3">
      {/* Main Search Bar */}
      <div className="relative flex items-center">
        <div className="absolute left-4 pointer-events-none text-gray-400">
          <Search className="w-5 h-5 text-[#d6a85f]" />
        </div>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Where is Stripe webhook processing implemented?"
          className="w-full bg-[#080909] border border-[#242525] focus:border-[#d6a85f] rounded-md pl-12 pr-32 py-3.5 text-[15px] text-gray-100 placeholder-gray-500 focus:outline-none transition-colors font-sans"
        />
        <div className="absolute right-3 flex items-center space-x-2">
          <button
            onClick={onSearch}
            className="bg-[#171715] hover:bg-[#20201d] border border-[#3a3326] text-[#e8c07d] font-semibold text-xs px-4 py-2 rounded-md transition-colors"
          >
            Search
          </button>
        </div>
      </div>

      {/* Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 pt-1">
        {/* Retrieval Mode Pills */}
        <div className="flex items-center space-x-2">
          <div className="bg-[#0d1117] border border-[#30363d] p-1 rounded-lg flex space-x-1">
            <button
              onClick={() => setUseHybrid(true)}
              className={`px-3 py-1 text-xs rounded-md font-medium transition-all ${
                useHybrid
                  ? 'bg-[#30363d] text-[#f0c98d] shadow-sm font-medium'
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
                  ? 'bg-[#30363d] text-[#f0c98d] shadow-sm font-medium'
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
          <Sliders className="w-3.5 h-3.5 text-[#8b949e]" />
            <span className="text-gray-400" title="Exact Keyword Match weight">Exact Words</span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={alpha}
              onChange={(e) => setAlpha(parseFloat(e.target.value))}
              className="w-20 accent-[#f0c98d] cursor-pointer"
            />
            <span className="text-gray-400" title="Conceptual Meaning weight">Meaning</span>
          </div>
        )}

        {/* Results Limit */}
        <div className="flex items-center space-x-2 text-xs">
          <Hash className="w-3.5 h-3.5 text-[#8b949e]" />
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
          onAddRepository={onAddRepository}
        />
      </div>
    </div>
  );
};
