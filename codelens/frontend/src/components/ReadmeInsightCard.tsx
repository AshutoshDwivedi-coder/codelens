import React, { useState } from 'react';
import {
  BookOpen,
  Sparkles,
  ChevronDown,
  ChevronUp,
  FileCode2,
  RefreshCw,
  Search,
  Layers,
  Cpu,
  Settings,
  HelpCircle,
  ExternalLink,
  Compass,
} from 'lucide-react';
import { ReadmeAnalysis } from '../api';

interface ReadmeInsightCardProps {
  analysis: ReadmeAnalysis | null;
  isLoading: boolean;
  onSelectQuestion: (question: string) => void;
  onRefresh: () => void;
  selectedRepoName: string;
}

export const ReadmeInsightCard: React.FC<ReadmeInsightCardProps> = ({
  analysis,
  isLoading,
  onSelectQuestion,
  onRefresh,
  selectedRepoName,
}) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const [activeTab, setActiveTab] = useState<string>('all');

  if (isLoading) {
    return (
      <div className="bg-[#161b22]/80 border border-blue-500/30 rounded-2xl p-5 space-y-4 animate-pulse backdrop-blur-sm shadow-xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-blue-500/20" />
            <div className="space-y-1.5">
              <div className="h-4 bg-[#21262d] rounded w-48" />
              <div className="h-3 bg-[#21262d] rounded w-32" />
            </div>
          </div>
          <div className="h-7 w-24 bg-[#21262d] rounded-lg" />
        </div>
        <div className="h-10 bg-[#21262d] rounded-xl w-full" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 pt-2">
          <div className="h-12 bg-[#21262d] rounded-xl" />
          <div className="h-12 bg-[#21262d] rounded-xl" />
        </div>
      </div>
    );
  }

  if (!analysis) return null;

  const categories = analysis.categories || {};
  const categoryKeys = Object.keys(categories).filter(
    (k) => categories[k] && categories[k].length > 0
  );

  // Determine questions for current tab
  const displayedQuestions =
    activeTab === 'all'
      ? analysis.suggested_questions || []
      : categories[activeTab] || [];

  return (
    <div className="relative overflow-hidden bg-gradient-to-br from-[#161b22] via-[#0f141c] to-[#0d1117] border border-blue-500/30 hover:border-blue-500/50 rounded-2xl p-5 shadow-2xl transition-all font-sans">
      {/* Ambient background glow accent */}
      <div className="absolute top-0 right-0 w-80 h-32 bg-blue-500/5 rounded-full blur-3xl pointer-events-none -mr-16 -mt-10" />

      {/* Header bar */}
      <div className="flex items-start justify-between gap-3 relative z-10">
        <div className="flex items-start space-x-3.5">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600/30 to-indigo-600/20 border border-blue-400/30 flex items-center justify-center text-blue-400 shrink-0 shadow-inner">
            <BookOpen className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-bold text-sm text-gray-100 tracking-tight">
                {analysis.title || `${selectedRepoName} Architecture Overview`}
              </h3>
              {analysis.has_readme ? (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-mono bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 font-semibold">
                  <FileCode2 className="w-3 h-3 text-emerald-400" />
                  {analysis.filename || 'README.md'}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-amber-500/10 text-amber-300 border border-amber-500/30">
                  <HelpCircle className="w-3 h-3 text-amber-400" /> Default Codebase Index
                </span>
              )}
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-blue-500/10 text-blue-300 border border-blue-500/20">
                <Sparkles className="w-3 h-3 text-blue-400" /> README Analysis
              </span>
            </div>
            <p className="text-xs text-gray-300 mt-1 line-clamp-2 leading-relaxed">
              {analysis.summary}
            </p>
          </div>
        </div>

        {/* Action Controls */}
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
            className="flex items-center space-x-1 px-2.5 py-1.5 rounded-lg bg-[#21262d] hover:bg-[#30363d] text-gray-300 hover:text-white border border-[#30363d] text-xs transition-all font-medium"
          >
            <span>{isExpanded ? 'Collapse' : 'Explore Questions'}</span>
            {isExpanded ? (
              <ChevronUp className="w-3.5 h-3.5 ml-0.5" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5 ml-0.5" />
            )}
          </button>
        </div>
      </div>

      {/* Expandable Section */}
      {isExpanded && (
        <div className="mt-4 pt-4 border-t border-[#30363d]/80 space-y-4 relative z-10 animate-fadeIn">
          {/* Detected Modules & Architecture Tags */}
          {analysis.key_modules && analysis.key_modules.length > 0 && (
            <div className="space-y-1.5">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-indigo-400" />
                Key Architectural Files Identified:
              </span>
              <div className="flex flex-wrap gap-1.5">
                {analysis.key_modules.slice(0, 8).map((mod) => (
                  <span
                    key={mod}
                    className="font-mono text-[11px] bg-[#0d1117] text-gray-300 border border-[#30363d] px-2.5 py-1 rounded-md flex items-center space-x-1.5 hover:border-indigo-500/40 transition-colors"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                    <span>{mod}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Key Features pills if extracted */}
          {analysis.features && analysis.features.length > 0 && (
            <div className="space-y-1.5">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                <Compass className="w-3.5 h-3.5 text-blue-400" />
                Documented Features & Capabilities:
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

          {/* Suggested Codebase Questions Section */}
          <div className="space-y-2.5 pt-1">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-bold text-gray-200 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                Suggested Questions to Ask this Codebase:
              </span>
              <span className="text-[11px] text-gray-400">
                Click any question to search instantly
              </span>
            </div>

            {/* Category Filter Tabs */}
            {categoryKeys.length > 1 && (
              <div className="flex flex-wrap items-center gap-1.5 text-xs">
                <button
                  type="button"
                  onClick={() => setActiveTab('all')}
                  className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${
                    activeTab === 'all'
                      ? 'bg-blue-600 text-white font-bold shadow-sm'
                      : 'bg-[#0d1117] text-gray-400 hover:text-gray-200 border border-[#30363d]'
                  }`}
                >
                  All Suggestions ({analysis.suggested_questions.length})
                </button>
                {categoryKeys.map((catKey) => (
                  <button
                    key={catKey}
                    type="button"
                    onClick={() => setActiveTab(catKey)}
                    className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${
                      activeTab === catKey
                        ? 'bg-blue-600 text-white font-bold shadow-sm'
                        : 'bg-[#0d1117] text-gray-400 hover:text-gray-200 border border-[#30363d]'
                    }`}
                  >
                    {catKey} ({categories[catKey]?.length || 0})
                  </button>
                ))}
              </div>
            )}

            {/* Suggested Question Chips Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1">
              {displayedQuestions.map((q, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => onSelectQuestion(q)}
                  className="group flex items-start space-x-2.5 text-left p-3 rounded-xl bg-[#0d1117] hover:bg-[#21262d] border border-[#30363d] hover:border-blue-500/50 transition-all text-xs text-gray-200 shadow-sm hover:shadow-md cursor-pointer"
                >
                  <Search className="w-3.5 h-3.5 text-blue-400 shrink-0 mt-0.5 group-hover:scale-110 transition-transform" />
                  <span className="flex-1 font-medium group-hover:text-blue-300 transition-colors leading-snug">
                    {q}
                  </span>
                  <span className="text-[10px] text-gray-500 group-hover:text-gray-300 font-mono shrink-0 mt-0.5">
                    ↵
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
