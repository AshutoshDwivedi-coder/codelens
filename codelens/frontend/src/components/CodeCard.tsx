import React, { useState } from 'react';
import {
  FileCode,
  Copy,
  Check,
  GitCommit,
  Code,
  Sparkles,
  FileText,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { SearchResult } from '../api';

const TOKEN_PATTERN = /(#[^\n]*|\/\/[^\n]*|\/\*.*?\*\/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|\b\d+(?:\.\d+)?\b|\b(?:async|await|break|case|catch|class|const|continue|def|del|elif|else|export|extends|false|finally|for|from|function|if|implements|import|in|interface|let|new|null|of|pass|private|public|raise|return|static|super|this|throw|true|try|var|while|with|yield|None|True|False)\b|\b[A-Z][A-Za-z0-9_]*\b|\b[A-Za-z_$][\w$]*(?=\s*\()|[^\w\s]+|\s+)/g;

function highlightLine(line: string) {
  const tokens = line.match(TOKEN_PATTERN) || [line];
  return tokens.map((token, index) => {
    let kind = '';
    if (/^(#|\/\/|\/\*)/.test(token)) kind = 'syn-comment';
    else if (/^["'`]/.test(token)) kind = 'syn-string';
    else if (/^\d/.test(token)) kind = 'syn-number';
    else if (/^(async|await|break|case|catch|class|const|continue|def|del|elif|else|export|extends|false|finally|for|from|function|if|implements|import|in|interface|let|new|null|of|pass|private|public|raise|return|static|super|this|throw|true|try|var|while|with|yield|None|True|False)$/.test(token)) kind = 'syn-keyword';
    else if (/^[A-Z]/.test(token) && /[A-Za-z]/.test(token)) kind = 'syn-type';
    else if (/^[A-Za-z_$][\w$]*$/.test(token) && new RegExp(`\\b${token.replace(/[$]/g, '\\$&')}\\s*\\(`).test(line)) kind = 'syn-function';
    else if (/^[^\w\s]+$/.test(token)) kind = 'syn-operator';
    return kind ? <span className={kind} key={index}>{token}</span> : token;
  });
}

interface CodeCardProps {
  result: SearchResult;
  rank: number;
  query: string;
  onOpenHistory: (result: SearchResult) => void;
}

const QUERY_STOP_WORDS = new Set(['where', 'what', 'when', 'which', 'who', 'how', 'does', 'are', 'the', 'and', 'for', 'from', 'with', 'this', 'that', 'into', 'implemented', 'implementation', 'codebase', 'code', 'show', 'find']);

export const CodeCard: React.FC<CodeCardProps> = ({ result, rank, query = '', onOpenHistory }) => {
  const [copied, setCopied] = useState(false);
  const [viewMode, setViewMode] = useState<'plain' | 'code'>('code');
  const [showScoreDetails, setShowScoreDetails] = useState(false);

  const handleCopy = () => {
    const textToCopy = result.content || result.code || '';
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const lines = (result.content || result.code || '').split('\n');
  const queryTerms = Array.from(new Set((query.toLowerCase().match(/[a-z0-9_]+/g) || [])
    .filter((term) => term.length > 2 && !QUERY_STOP_WORDS.has(term))));
  const searchableText = `${result.content || result.code || ''} ${result.docstring || ''} ${result.symbol_name || ''} ${result.file_path || ''}`.toLowerCase();
  const matchedTerms = queryTerms.filter((term) => searchableText.includes(term)).slice(0, 5);
  const queryFocus = queryTerms.slice(0, 4).join(', ') || 'your question';
  const queryLabel = query.trim() || 'your search';
  const firstDocLine = result.docstring?.trim().split('\n').find(Boolean)?.replace(/^['"\s]+|['"\s]+$/g, '');
  const relevanceText = firstDocLine
    ? `Your question focuses on ${queryFocus}. The ${result.symbol_type || 'code'}${result.symbol_name ? ` “${result.symbol_name}”` : ''} is documented as: ${firstDocLine}`
    : matchedTerms.length
      ? `Your question focuses on ${queryFocus}. This snippet contains references to ${matchedTerms.join(', ')}, which connect it to your question. It is in ${result.file_path}, lines ${result.start_line}–${result.end_line}; review the code below to see how those references are used.`
      : `This snippet in ${result.file_path}, lines ${result.start_line}–${result.end_line}, was ranked as conceptually related to “${queryLabel}”. The search did not find the question’s key terms verbatim here, so use the code below to check whether it implements the behavior you mean.`;
  const relatedFiles = Array.from((result.content || '').matchAll(/(?:from\s+|import\s+)["']?([\w./-]+)["']?/g))
    .map((match) => match[1])
    .filter((path) => path.includes('/') || path.endsWith('.py'))
    .filter((path) => !path.startsWith('.') && path !== result.file_path)
    .slice(0, 3);

  // Compute percentage & human friendly relevance label
  const rawScore = result.score_breakdown?.dense_score ?? result.score_breakdown?.fused_score ?? result.score ?? 0;
  const matchPct = Math.max(0, Math.min(rawScore * 100, 100));
  const matchColor =
    matchPct >= 80
      ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
      : matchPct >= 50
      ? 'bg-[#f0c98d]/5 text-[#c9b58f] border-[#30363d]'
      : 'bg-[#161b22] text-gray-500 border-[#30363d]';

  return (
    <div className="code-preview bg-[#161b22] border border-[#30363d] rounded-md overflow-hidden group">
      {/* Header Bar */}
      <div className="bg-[#161b22] border-b border-[#30363d] px-4 py-3 flex flex-wrap items-center justify-between gap-3">
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
              <span>{matchPct.toFixed(1)}%</span>
              {showScoreDetails ? (
                <ChevronUp className="w-3 h-3 ml-0.5 opacity-70" />
              ) : (
                <ChevronDown className="w-3 h-3 ml-0.5 opacity-70" />
              )}
            </button>

            {/* Score Details Popover */}
            {showScoreDetails && (
              <div className="score-details-popover absolute left-0 mt-2 w-64 bg-[#161b22] border border-[#30363d] rounded-xl p-3 shadow-2xl z-30 text-xs space-y-2 font-sans">
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
          <div className="code-tabs flex items-center gap-1 text-xs font-medium">
            <button
              onClick={() => setViewMode('plain')}
              className={`flex items-center space-x-1 px-2.5 py-2 border-b-2 transition-colors ${
                viewMode === 'plain'
                  ? 'border-[#d6a85f] text-[#e7e4dc] font-semibold'
                  : 'border-transparent text-gray-400 hover:text-gray-200'
              }`}
              title="View code description and summary"
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Explanation</span>
            </button>
            <button
              onClick={() => setViewMode('code')}
              className={`flex items-center space-x-1 px-2.5 py-2 border-b-2 transition-colors ${
                viewMode === 'code'
                  ? 'border-[#d6a85f] text-[#e7e4dc] font-semibold'
                  : 'border-transparent text-gray-400 hover:text-gray-200'
              }`}
              title="View source code snippet"
            >
              <Code className="w-3.5 h-3.5" />
              <span>Code</span>
            </button>
          </div>

          {/* History / Evolution Button */}
          <button
            onClick={() => onOpenHistory(result)}
            className="flex items-center space-x-1.5 px-2 py-1 rounded-md bg-[#1c2128] hover:bg-[#21262d] text-gray-300 border border-[#30363d] text-xs font-medium transition-colors"
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
            <span className="explanation-label">
              <FileText className="w-3.5 h-3.5" /> Why this matches
            </span>
            <p className="text-gray-200 text-sm font-medium leading-relaxed">
              {relevanceText}
            </p>
            {matchedTerms.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1" aria-label="Query terms found in this result">
                {matchedTerms.map((term) => <span className="explanation-evidence-term" key={term}>{term}</span>)}
              </div>
            )}
          </div>

          {/* Step-by-Step Breakdown */}
          <div className="space-y-2">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider block">
              Related files:
            </span>
            <ul className="space-y-2">
              {relatedFiles.length ? relatedFiles.map((file) => (
                <li key={file} className="related-file-row">
                  <code>{file}</code>
                </li>
              )) : <li className="related-file-row text-gray-400">{result.file_path}</li>}
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
        <div className="p-3 bg-[#0b0f14] overflow-x-auto text-[11px] font-mono leading-snug">
          <table className="w-full border-collapse">
            <tbody>
              {lines.map((line, idx) => {
                const lineNum = result.start_line + idx;
                return (
                  <tr key={idx} className="hover:bg-[#161b22]/70">
                    <td className="w-10 select-none text-right pr-4 text-gray-600 border-r border-[#21262d] font-mono text-[11px]">
                      {lineNum}
                    </td>
                    <td className="code-line pl-4 whitespace-pre">
                      {highlightLine(line)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {viewMode === 'code' && (
        <div className="relevance-footer">
          <div className="relevance-heading">Why this matches</div>
          <p>{relevanceText}</p>
        </div>
      )}
    </div>
  );
};
