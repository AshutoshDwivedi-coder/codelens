import React, { useEffect, useState } from 'react';
import { X, GitCommit, Calendar, User, ArrowRight, Loader2, FileCode } from 'lucide-react';
import { getSnippetHistory, SearchResult, SnippetHistoryVersion } from '../api';

interface EvolutionModalProps {
  result: SearchResult | null;
  onClose: () => void;
}

export const EvolutionModal: React.FC<EvolutionModalProps> = ({ result, onClose }) => {
  const [versions, setVersions] = useState<SnippetHistoryVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedVersionIdx, setSelectedVersionIdx] = useState(0);

  useEffect(() => {
    if (!result) return;
    setLoading(true);
    setError(null);

    getSnippetHistory(result.file_path, result.commit_id)
      .then((data) => {
        setVersions(data.versions || []);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Failed to fetch evolution history');
        setLoading(false);
      });
  }, [result]);

  if (!result) return null;

  const currentVersion = versions[selectedVersionIdx];

  return (
    <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4 sm:p-6 animate-fadeIn">
      <div className="bg-[#161b22] border border-[#30363d] rounded-2xl w-full max-w-5xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="bg-[#0d1117] border-b border-[#30363d] px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-purple-500/10 border border-purple-500/20 flex items-center justify-center">
              <GitCommit className="w-4 h-4 text-purple-400" />
            </div>
            <div>
              <h2 className="font-bold text-base text-gray-100 flex items-center space-x-2">
                <span>Evolutionary History</span>
                <span className="text-xs font-normal text-purple-400 font-mono">
                  {result.symbol_name || result.file_path}
                </span>
              </h2>
              <p className="text-xs text-gray-400 font-mono">{result.file_path}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-[#21262d] text-gray-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading ? (
            <div className="py-20 flex flex-col items-center justify-center space-y-3 text-gray-400">
              <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
              <p className="text-sm font-medium">Tracking code lineage across git history...</p>
            </div>
          ) : error ? (
            <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          ) : versions.length === 0 ? (
            <div className="py-12 text-center text-gray-400 text-sm">
              No historical commit variants found for this snippet.
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Commit Timeline (Left Column) */}
              <div className="space-y-3 border-r border-[#30363d] pr-4">
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Commit Timeline ({versions.length} versions)
                </h3>
                <div className="space-y-2">
                  {versions.map((v, idx) => (
                    <button
                      key={v.commit_id}
                      onClick={() => setSelectedVersionIdx(idx)}
                      className={`w-full text-left p-3 rounded-xl border transition-all text-xs font-mono ${
                        selectedVersionIdx === idx
                          ? 'bg-purple-600/10 border-purple-500/50 text-white shadow-sm'
                          : 'bg-[#0d1117] border-[#30363d] text-gray-400 hover:bg-[#21262d]'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-bold text-purple-400">
                          {v.commit_id.substring(0, 7)}
                        </span>
                        <span className="text-[10px] text-gray-500">
                          {v.timestamp ? new Date(v.timestamp).toLocaleDateString() : 'recent'}
                        </span>
                      </div>
                      <p className="text-gray-300 font-sans text-xs line-clamp-1">
                        {v.commit_message || 'Commit update'}
                      </p>
                      <div className="mt-1 flex items-center space-x-2 text-[10px] text-gray-500">
                        <User className="w-3 h-3 text-gray-500" />
                        <span>{v.author || 'dev'}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Version Detail View (Right Column) */}
              <div className="lg:col-span-2 space-y-4">
                {currentVersion && (
                  <div className="bg-[#0d1117] border border-[#30363d] rounded-xl p-4 space-y-4">
                    <div className="flex items-center justify-between border-b border-[#30363d] pb-3">
                      <div>
                        <div className="flex items-center space-x-2 text-xs">
                          <span className="font-bold text-purple-400 font-mono">
                            Commit {currentVersion.commit_id.substring(0, 7)}
                          </span>
                          <span className="text-gray-500">•</span>
                          <span className="text-gray-400">{currentVersion.author}</span>
                        </div>
                        <p className="text-sm font-medium text-gray-200 mt-1">
                          {currentVersion.commit_message}
                        </p>
                      </div>
                      <span className="text-xs font-mono text-gray-500">
                        L{currentVersion.start_line}-L{currentVersion.end_line}
                      </span>
                    </div>

                    {/* Code Container */}
                    <div className="bg-[#161b22] p-4 rounded-lg overflow-x-auto text-xs font-mono leading-relaxed border border-[#30363d]">
                      <pre className="text-gray-200 whitespace-pre">{currentVersion.content}</pre>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
