import React, { useState } from 'react';
import {
  FileCode,
  Copy,
  Check,
  GitCommit,
  Code,
  Sparkles,
  FileText,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { SearchResult } from '../api';
import { explainCodeSnippet } from '../utils/codeExplainer';

interface CodeCardProps {
  result: SearchResult;
  rank: number;
  onOpenHistory: (result: SearchResult) => void;
}

export const CodeCard: React.FC<CodeCardProps> = ({ result, rank, onOpenHistory }) => {
  const [copied, setCopied] = useState(false);
  const [viewMode, setViewMode] = useState<'plain' | 'code'>('plain');
  const [showScoreDetails, setShowScoreDetails] = useState(false);

  const handleCopy = () => {
    const textToCopy = result.content || result.code || '';
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const lines = (result.content || result.code || '').split('\n');
  const explanation = explainCodeSnippet(result);

  // Compute percentage & human friendly relevance label
  const rawScore = result.score || 0.5;
  const matchPct = Math.min(Math.round(rawScore * 100), 99);
  const matchQuality =
    matchPct >= 80 ? 'Strong Match' : matchPct >= 50 ? 'Moderate Match' : 'Possible Match';
  const matchColor =
    matchPct >= 80
      ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
      : matchPct >= 50
      ? 'bg-amber-500/10 text-amber-300 border-amber-500/30'
      : 'bg-blue-500/10 text-blue-300 border-blue-500/30';

  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-2xl overflow-hidden hover:border-[#484f58] transition-all shadow-lg group">
      {/* Header Bar */}
      <div className="bg-[#0d1117] border-b border-[#30363d] px-5 py-3.5 flex flex-wrap items-center justify-between gap-3">
        {/* Left: Rank & File Path */}
        <div className="flex items-center space-x-3 min-w-0">
          <span className="w-7 h-7 rounded-lg bg-[#21262d] text-blue-400 font-mono text-xs font-bold flex items-center justify-center border border-[#30363d] shadow-inner">
            #{rank}
          </span>
          <div className="flex items-center space-x-2 truncate">
            <FileCode className="w-4 h-4 text-blue-400 shrink-0" />
            <span className="font-mono text-xs text-gray-200 font-semibold truncate" title={result.file_path}>
              {result.file_path}
            </span>
            <span className="text-[11px] text-gray-400 font-mono bg-[#161b22] px-2 py-0.5 rounded border border-[#30363d] shrink-0">
              Lines {result.start_line}–{result.end_line}
            </span>
          </div>
        </div>

        {/* Right: Relevance Badge, View Mode Switch, Actions */}
        <div className="flex items-center space-x-3 shrink-0">
          {/* Friendly Match Quality Indicator */}
          <div className="relative">
            <button
              onClick={() => setShowScoreDetails(!showScoreDetails)}
              className={`flex items-center space-x-1.5 px-3 py-1 rounded-full border text-xs font-medium cursor-pointer transition-all ${matchColor}`}
              title="Click for score details"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{matchPct}% {matchQuality}</span>
              {showScoreDetails ? (
                <ChevronUp className="w-3 h-3 ml-0.5 opacity-70" />
              ) : (
                <ChevronDown className="w-3 h-3 ml-0.5 opacity-70" />
              )}
            </button>

            {/* Score Details Popover */}
            {showScoreDetails && (
              <div className="absolute right-0 mt-2 w-64 bg-[#161b22] border border-[#30363d] rounded-xl p-3 shadow-2xl z-30 text-xs space-y-2 font-sans">
                <div className="font-bold text-gray-200 border-b border-[#30363d] pb-1 flex items-center justify-between">
                  <span>Match Score Breakdown</span>
                  <span className="text-[10px] text-gray-400 font-normal">How score is calculated</span>
                </div>
                {result.score_breakdown?.bm25_rank && (
                  <div className="flex justify-between items-center text-gray-300">
                    <span className="text-blue-400 font-medium">Exact Keyword Rank:</span>
                    <span className="font-mono font-bold">#{result.score_breakdown.bm25_rank}</span>
                  </div>
                )}
                {result.score_breakdown?.dense_score !== undefined && (
                  <div className="flex justify-between items-center text-gray-300">
                    <span className="text-purple-400 font-medium">Semantic Meaning Match:</span>
                    <span className="font-mono font-bold">
                      {(result.score_breakdown.dense_score * 100).toFixed(1)}%
                    </span>
                  </div>
                )}
                <p className="text-[11px] text-gray-400 pt-1 border-t border-[#30363d] leading-normal">
                  Score represents confidence that this code directly answers your query.
                </p>
              </div>
            )}
          </div>

          {/* View Mode Toggle Switch */}
          <div className="bg-[#161b22] border border-[#30363d] p-0.5 rounded-lg flex space-x-0.5 text-xs font-medium">
            <button
              onClick={() => setViewMode('plain')}
              className={`flex items-center space-x-1 px-2.5 py-1 rounded-md transition-all ${
                viewMode === 'plain'
                  ? 'bg-blue-600 text-white shadow-sm font-semibold'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
              title="View code description and summary"
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Description</span>
            </button>
            <button
              onClick={() => setViewMode('code')}
              className={`flex items-center space-x-1 px-2.5 py-1 rounded-md transition-all ${
                viewMode === 'code'
                  ? 'bg-blue-600 text-white shadow-sm font-semibold'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
              title="View source code snippet"
            >
              <Code className="w-3.5 h-3.5" />
              <span>Code Snippet</span>
            </button>
          </div>

          {/* History / Evolution Button */}
          <button
            onClick={() => onOpenHistory(result)}
            className="flex items-center space-x-1.5 px-3 py-1 rounded-lg bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 border border-purple-500/30 text-xs font-medium transition-colors"
            title="View how this code snippet evolved across git commits"
          >
            <GitCommit className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Evolution</span>
          </button>

          {/* Copy Button */}
          <button
            onClick={handleCopy}
            className="p-1.5 rounded-lg bg-[#21262d] hover:bg-[#30363d] text-gray-300 transition-colors"
            title="Copy code content"
          >
            {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Main Body: Description View vs Code View */}
      {viewMode === 'plain' ? (
        <div className="p-5 bg-[#0d1117] space-y-4 text-sm">
          {/* Code Description Card */}
          <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4 space-y-2">
            <span className="text-xs font-bold uppercase tracking-wider text-blue-400 flex items-center gap-1.5">
              <FileText className="w-4 h-4 text-blue-400" /> Code Description
            </span>
            <p className="text-gray-200 text-sm font-medium leading-relaxed">
              {explanation.purpose}
            </p>
          </div>

          {/* Step-by-Step Breakdown */}
          <div className="space-y-2">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">
              Key Operations:
            </span>
            <ul className="space-y-2">
              {explanation.steps.map((step, i) => (
                <li key={i} className="flex items-start space-x-2.5 text-xs text-gray-300 bg-[#161b22] p-2.5 rounded-lg border border-[#21262d]">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  <span>{step}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Key Attributes Footer */}
          <div className="flex flex-wrap items-center justify-between pt-2 border-t border-[#21262d] text-xs text-gray-400 gap-2 font-mono">
            <div className="flex items-center space-x-3">
              <span>Language: <strong className="text-gray-200 uppercase">{result.language || 'python'}</strong></span>
              {result.symbol_name && (
                <span>Symbol: <strong className="text-purple-300">{result.symbol_name}</strong></span>
              )}
            </div>
            <button
              onClick={() => setViewMode('code')}
              className="text-blue-400 hover:text-blue-300 font-sans font-medium hover:underline text-xs"
            >
              Switch to full source code →
            </button>
          </div>
        </div>
      ) : (
        /* Source Code Container with Line Numbers */
        <div className="p-4 bg-[#0d1117] overflow-x-auto text-xs font-mono leading-relaxed">
          <table className="w-full border-collapse">
            <tbody>
              {lines.map((line, idx) => {
                const lineNum = result.start_line + idx;
                return (
                  <tr key={idx} className="hover:bg-[#161b22]/70">
                    <td className="w-10 select-none text-right pr-4 text-gray-600 border-r border-[#21262d] font-mono text-[11px]">
                      {lineNum}
                    </td>
                    <td className="pl-4 text-gray-200 whitespace-pre">
                      {line}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
