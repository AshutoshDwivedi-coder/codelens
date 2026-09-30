import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Database, ChevronDown, Check, FolderGit2, Plus, X, RefreshCw, AlertCircle, Cpu } from 'lucide-react';
import { getRepos, RepoInfo } from '../api';

interface RepoSelectorProps {
  selectedRepos?: string[]; // an empty array means all indexed repos
  onChangeSelectedRepos: (repos: string[], repoPaths?: Record<string, string>) => void;
  /** Called when a new repo was just indexed so the parent can refresh */
  onRepoListRefresh?: () => void;
  repoListRevision?: number;
  onAddRepository?: (repoPath: string) => void;
}

const SOURCE_BADGE: Record<string, { label: string; cls: string }> = {
  indexed: { label: 'Indexed', cls: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' },
  demo:    { label: 'Demo',    cls: 'text-amber-400 bg-amber-500/10 border-amber-500/20' },
  cloned:  { label: 'Cloned',  cls: 'text-blue-400 bg-blue-500/10 border-blue-500/20' },
  custom:  { label: 'Custom',  cls: 'text-purple-400 bg-purple-500/10 border-purple-500/20' },
};

export const RepoSelector: React.FC<RepoSelectorProps> = ({
  selectedRepos = [],
  onChangeSelectedRepos,
  onRepoListRefresh,
  repoListRevision = 0,
  onAddRepository,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [customInput, setCustomInput] = useState('');
  const [repos, setRepos] = useState<RepoInfo[]>([]);
  const [isLoadingRepos, setIsLoadingRepos] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  /** Maps repo id → absolute path for custom/cloned entries */
  const [repoPaths, setRepoPaths] = useState<Record<string, string>>({});
  const dropdownRef = useRef<HTMLDivElement>(null);

  const loadRepos = useCallback(async () => {
    setIsLoadingRepos(true);
    setLoadError(null);
    try {
      const data = await getRepos();
      const fetched = (data.repos || []).filter((repo) => repo.source === 'indexed' && repo.chunk_count > 0);
      setRepos(fetched);
      // Build path map from fetched repos
      const pathMap: Record<string, string> = {};
      fetched.forEach((r) => { if (r.path) pathMap[r.id] = r.path; });
      setRepoPaths((prev) => ({ ...pathMap, ...prev }));
    } catch (err: any) {
      setLoadError('Could not load repositories from backend.');
      console.warn('RepoSelector load error:', err);
    } finally {
      setIsLoadingRepos(false);
    }
  }, []);

  // Load on mount + whenever the dropdown opens (so newly-indexed repos appear)
  useEffect(() => {
    loadRepos();
  }, [loadRepos, repoListRevision]);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const currentList = Array.isArray(selectedRepos) ? selectedRepos : [];
  const isAllSelected = currentList.length === 0;

  const notifyChange = (next: string[], extraPaths?: Record<string, string>) => {
    const allPaths = { ...repoPaths, ...(extraPaths || {}) };
    onChangeSelectedRepos(next, allPaths);
  };

  const handleSelectAll = () => notifyChange([]);

  const handleToggleRepo = (repoId: string) => {
    let next: string[];
    if (isAllSelected) {
      next = [repoId];
    } else if (currentList.includes(repoId)) {
      next = currentList.filter((r) => r !== repoId);
    } else {
      next = [...currentList, repoId];
    }
    notifyChange(next);
  };

  const handleAddCustom = () => {
    const trimmed = customInput.trim().replace(/['"]/g, '');
    if (!trimmed) return;

    const newId = trimmed;
    const isPath = trimmed.includes('/') || trimmed.includes('\\') || trimmed.includes(':');
    if (!repos.some((r) => r.id === newId)) {
      const extraPaths: Record<string, string> = {};
      if (isPath) extraPaths[newId] = trimmed;
      setRepoPaths((prev) => ({ ...prev, ...extraPaths }));
      // Keep unindexed entries out of the scope list until indexing succeeds.
      onAddRepository?.(trimmed);
    } else {
      handleToggleRepo(newId);
    }
    setCustomInput('');
  };

  const getDisplayText = () => {
    if (isAllSelected) return 'All Indexed Repositories';
    if (currentList.length === 1) {
      const match = repos.find((r) => r.id === currentList[0]);
      return match ? match.name : currentList[0];
    }
    return `${currentList.length} Repos Selected`;
  };

  const handleOpenToggle = () => {
    if (!isOpen) loadRepos(); // refresh list each time user opens
    setIsOpen(!isOpen);
  };

  return (
    <div className="relative text-xs font-sans" ref={dropdownRef}>
      <div className="flex items-center space-x-2">
        <span className="text-gray-400 font-semibold flex items-center gap-1">
          <Database className="w-3.5 h-3.5 text-emerald-400" /> Scope:
        </span>
        <button
          type="button"
          onClick={handleOpenToggle}
          className="bg-[#0d1117] border border-[#30363d] hover:border-emerald-500/50 text-gray-200 rounded-lg px-3 py-1.5 focus:outline-none flex items-center justify-between min-w-[170px] max-w-[240px] transition-all"
        >
          <div className="flex items-center space-x-1.5 truncate">
            <FolderGit2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
            <span className="truncate font-medium">{getDisplayText()}</span>
          </div>
          <ChevronDown className={`w-3.5 h-3.5 text-gray-400 ml-2 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 bg-[#161b22] border border-[#30363d] rounded-xl shadow-2xl p-3 z-50 space-y-2 animate-fadeIn">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-[#30363d] pb-2">
            <span className="font-bold text-gray-200 text-xs">Select Repository</span>
            <button
              type="button"
              onClick={loadRepos}
              disabled={isLoadingRepos}
              className="p-1 rounded hover:bg-[#21262d] text-gray-400 hover:text-white transition-colors"
              title="Refresh repository list"
            >
              <RefreshCw className={`w-3 h-3 ${isLoadingRepos ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {/* Error banner */}
          {loadError && (
            <div className="flex items-center gap-1.5 text-red-400 text-[10px] bg-red-500/10 border border-red-500/20 rounded-lg px-2 py-1.5">
              <AlertCircle className="w-3 h-3 shrink-0" />
              <span>{loadError}</span>
            </div>
          )}

          {/* Repo list */}
          <div className="space-y-1 max-h-56 overflow-y-auto pr-0.5">
            {repos.length === 0 && !isLoadingRepos && (
              <div className="text-center text-gray-500 text-[11px] py-4">
                <Cpu className="w-4 h-4 mx-auto mb-1 text-gray-600" />
                No indexed repos found.<br />Index a repository first.
              </div>
            )}
            {repos.map((repo) => {
              const checked = isAllSelected || currentList.includes(repo.id);
              const isCustom = !['indexed', 'demo', 'cloned'].includes(repo.id) &&
                !['indexed', 'demo', 'cloned'].includes(repo.source);
              const badgeKey = isCustom ? 'custom' : repo.source;
              const badge = SOURCE_BADGE[badgeKey] || SOURCE_BADGE.indexed;

              return (
                <button
                  key={repo.id}
                  type="button"
                  onClick={() => handleToggleRepo(repo.id)}
                  className={`w-full flex items-center justify-between p-2 rounded-lg text-left transition-colors cursor-pointer ${
                    checked
                      ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-300'
                      : 'hover:bg-[#21262d] text-gray-300 border border-transparent'
                  }`}
                >
                  <div className="space-y-0.5 truncate pr-2 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="font-semibold block text-xs truncate">{repo.name}</span>
                      <span className={`shrink-0 text-[9px] font-medium px-1 py-0.5 rounded border ${badge.cls}`}>
                        {badge.label}
                      </span>
                    </div>
                    <span className="text-[10px] text-gray-400 block truncate">{repo.description}</span>
                    {repo.chunk_count > 0 && (
                      <span className="text-[9px] text-gray-500">{repo.chunk_count} chunks</span>
                    )}
                  </div>
                  <div className={`repo-checkbox w-4 h-4 rounded flex items-center justify-center border shrink-0 ${checked ? 'is-checked' : ''}`}>
                    {checked && <Check className="w-3 h-3 stroke-[3]" />}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Add repo input */}
          <div className="pt-2 border-t border-[#30363d] space-y-1.5">
            <p className="text-[10px] text-gray-500 leading-snug">
              Enter a local folder path (e.g. <code className="bg-[#0d1117] px-1 rounded">C:\projects\myapp</code>) or a GitHub URL (e.g. <code className="bg-[#0d1117] px-1 rounded">owner/repo</code>).
            </p>
            <div className="flex items-center space-x-1.5">
              <input
                type="text"
                value={customInput}
                onChange={(e) => setCustomInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddCustom()}
                placeholder="C:\path\to\repo or owner/repo"
                className="bg-[#0d1117] border border-[#30363d] focus:border-emerald-500/50 text-gray-200 rounded-md px-2 py-1.5 text-xs focus:outline-none flex-1 placeholder-gray-600 font-mono"
              />
              <button
                type="button"
                onClick={handleAddCustom}
                disabled={!customInput.trim()}
                className="bg-[#21262d] hover:bg-[#30363d] disabled:opacity-40 text-emerald-400 p-1.5 rounded-md border border-[#30363d] transition-colors"
                title="Add repository"
              >
                <Plus className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Reset */}
          {!isAllSelected && (
            <div className="pt-1 flex justify-end">
              <button
                type="button"
                onClick={handleSelectAll}
                className="text-[11px] text-blue-400 hover:text-blue-300 hover:underline"
              >
                Clear selection
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
