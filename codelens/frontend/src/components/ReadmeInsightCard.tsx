import React from 'react';
import {
  BookOpen,
  ChevronDown,
  ChevronUp,
  FileCode2,
  RefreshCw,
  Layers,
  Compass,
  HelpCircle,
  Sparkles,
} from 'lucide-react';
import { ReadmeAnalysis } from '../api';

interface ReadmeInsightCardProps {
  analysis: ReadmeAnalysis | null;
  isLoading: boolean;
  onRefresh: () => void;
  selectedRepoName: string;
}

/** Compact architecture overview (questions live in the panel under the search bar). */
export const ReadmeInsightCard: React.FC<ReadmeInsightCardProps> = ({
  analysis,
  isLoading,
  onRefresh,
  selectedRepoName,
}) => {
  const [isExpanded, setIsExpanded] = React.useState(false);

  if (isLoading) {
    return (
      <div className="bg-[#161b22]/80 border border-[#30363d] rounded-2xl p-5 space-y-4 animate-pulse">
        <div className="h-4 bg-[#21262d] rounded w-48" />
        <div className="h-10 bg-[#21262d] rounded-xl w-full" />
      </div>
    );
  }

  if (!analysis) return null;

  const hasDetails =
    (analysis.key_modules && analysis.key_modules.length > 0) ||
    (analysis.features && analysis.features.length > 0);

  if (!hasDetails) return null;

  return (
    <div className="readme-insight relative overflow-hidden bg-[#0d0e0e] border border-[#242525] rounded-md px-3 py-2 shadow-none">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-start space-x-3.5 min-w-0">
          <div className="w-7 h-7 rounded-md bg-[#151411] border border-[#393226] flex items-center justify-center text-[#d6a85f] shrink-0">
            <BookOpen className="w-3.5 h-3.5" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-bold text-sm text-gray-100 tracking-tight">
                {analysis.title || `${selectedRepoName} Architecture`}
              </h3>
              {analysis.has_readme ? (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-mono bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
                  <FileCode2 className="w-3 h-3" />
                  {analysis.filename || 'README.md'}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-amber-500/10 text-amber-300 border border-amber-500/30">
                  <HelpCircle className="w-3 h-3" /> Default index
                </span>
              )}
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] bg-[#121313] text-gray-400 border border-[#242525]">
                <Sparkles className="w-3 h-3" /> Details
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2 shrink-0">
          <button
            type="button"
            onClick={onRefresh}
            className="p-1.5 rounded-lg bg-[#21262d] hover:bg-[#30363d] text-gray-400 hover:text-gray-200 border border-[#30363d] transition-all"
            title="Re-analyze repository README"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center space-x-1 px-2.5 py-1.5 rounded-lg bg-[#21262d] hover:bg-[#30363d] text-gray-300 border border-[#30363d] text-xs transition-all"
          >
            <span>{isExpanded ? 'Collapse' : 'Expand'}</span>
            {isExpanded ? (
              <ChevronUp className="w-3.5 h-3.5 ml-0.5" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5 ml-0.5" />
            )}
          </button>
        </div>
      </div>

      {isExpanded && (
        <div className="mt-4 pt-4 border-t border-[#30363d]/80 space-y-4">
          {analysis.key_modules && analysis.key_modules.length > 0 && (
            <div className="space-y-1.5">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-indigo-400" />
                Key Architectural Files
              </span>
              <div className="flex flex-wrap gap-1.5">
                {analysis.key_modules.slice(0, 8).map((mod) => (
                  <span
                    key={mod}
                    className="font-mono text-[11px] bg-[#0d1117] text-gray-300 border border-[#30363d] px-2.5 py-1 rounded-md"
                  >
                    {mod}
                  </span>
                ))}
              </div>
            </div>
          )}

          {analysis.features && analysis.features.length > 0 && (
            <div className="space-y-1.5">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                <Compass className="w-3.5 h-3.5 text-blue-400" />
                Documented Features
              </span>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                {analysis.features.slice(0, 4).map((feat, idx) => (
                  <div
                    key={idx}
                    className="bg-[#0d1117]/80 border border-[#30363d] rounded-lg p-2 text-gray-300 text-[11px] flex items-start space-x-2"
                  >
                    <span className="text-blue-400 font-bold shrink-0 mt-0.5">•</span>
                    <span className="leading-snug">{feat}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
