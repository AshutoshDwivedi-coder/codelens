import React, { useState } from 'react';
import { BookOpen, FileCode2, Layers } from 'lucide-react';

interface CodebaseSummaryProps {
  title: string;
  summary: string;
  repoName: string;
  hasReadme?: boolean;
  filename?: string | null;
  keyModules?: string[];
  isLoading?: boolean;
  onOpenReadme?: () => void;
  selectedRepoNames?: string[];
  selectedRepoDescriptions?: { id: string; name: string; description: string }[];
  repoScopeLabel?: string;
}

export const CodebaseSummary: React.FC<CodebaseSummaryProps> = ({
  title,
  summary,
  repoName,
  hasReadme = false,
  filename,
  keyModules = [],
  isLoading = false,
  onOpenReadme,
  selectedRepoNames = [],
  selectedRepoDescriptions = [],
  repoScopeLabel = 'SELECTED REPOSITORIES',
}) => {
  const [summaryExpanded, setSummaryExpanded] = useState(false);
  if (isLoading) {
    return (
      <div className="bg-[#161b22] border-b border-[#30363d] px-6 py-4 animate-pulse">
        <div className="max-w-7xl mx-auto space-y-2">
          <div className="h-4 bg-[#21262d] rounded w-56" />
          <div className="h-3 bg-[#21262d] rounded w-full max-w-3xl" />
          <div className="h-3 bg-[#21262d] rounded w-2/3 max-w-2xl" />
        </div>
      </div>
    );
  }

  if (!summary) return null;

  return (
    <div className="bg-[#161b22] border-b border-[#30363d] px-6 py-4">
      <div className="max-w-7xl mx-auto flex items-start gap-3">
        <div className="w-7 h-7 rounded-md bg-[#151411] border border-[#393226] flex items-center justify-center shrink-0">
          <BookOpen className="w-3.5 h-3.5 text-[#d6a85f]" />
        </div>
        <div className="min-w-0 flex-1 space-y-1.5">
          {selectedRepoNames.length > 0 && (
            <div className="project-selected-repos" aria-label={repoScopeLabel}>
              <span className="project-selected-repos-label">{repoScopeLabel}</span>
              <div className="project-selected-repos-list">
                {selectedRepoNames.map((name, index) => <span className="project-selected-repo" key={`${name}-${index}`} title={name}>{name}</span>)}
              </div>
            </div>
          )}
          {selectedRepoDescriptions.length > 1 && (
            <div className="project-selected-repo-descriptions">
              {selectedRepoDescriptions.map((repo) => (
                <div className="project-selected-repo-description" key={repo.id}>
                  <span className="project-selected-repo-description-name">{repo.name}</span>
                  <p>{repo.description}</p>
                </div>
              ))}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-bold text-gray-100 tracking-tight">
              {title || `${repoName} Overview`}
            </h2>
            {selectedRepoDescriptions.length > 1 ? null : hasReadme ? (
              <button type="button" className="readme-link" onClick={onOpenReadme} title="Open this repository's README">
                <FileCode2 className="w-3 h-3" />
                {filename || 'README.md'}
              </button>
            ) : (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] bg-amber-500/10 text-amber-300 border border-amber-500/30">
                Selected codebase
              </span>
            )}
          </div>
          {selectedRepoDescriptions.length <= 1 && <p className={`project-summary-text text-xs text-gray-300 leading-relaxed ${summaryExpanded ? '' : 'line-clamp-3'}`}>
            {summary}
          </p>}
          {selectedRepoDescriptions.length <= 1 && summary.length > 150 && (
            <button
              type="button"
              className="project-summary-toggle"
              aria-expanded={summaryExpanded}
              onClick={() => setSummaryExpanded((expanded) => !expanded)}
            >
              {summaryExpanded ? 'Show less' : 'Show more'}
            </button>
          )}
          {selectedRepoDescriptions.length <= 1 && keyModules.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
              <span className="text-[9px] uppercase tracking-wider text-gray-500 flex items-center gap-1">
                <Layers className="w-3 h-3 text-[#777777]" />
                Key files
              </span>
              {keyModules.slice(0, 6).map((mod) => (
                <span
                  key={mod}
                  className="font-mono text-[10px] bg-[#0d1117] text-gray-400 border border-[#30363d] px-2 py-0.5 rounded"
                >
                  {mod}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
