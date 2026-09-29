import React, { useEffect, useState } from 'react';
import { X, RefreshCw, Folder, CheckCircle, AlertTriangle, Play, Cpu } from 'lucide-react';
import { getIndexingStatus, startIndexing } from '../api';

interface IndexingModalProps {
  isOpen: boolean;
  onClose: () => void;
  onIndexingComplete: (repoPath?: string) => void;
  initialRepoPath?: string;
  autoStart?: boolean;
}

export const IndexingModal: React.FC<IndexingModalProps> = ({
  isOpen,
  onClose,
  onIndexingComplete,
  initialRepoPath = '',
  autoStart = false,
}) => {
  const [repoPath, setRepoPath] = useState(initialRepoPath);
  const [status, setStatus] = useState<'idle' | 'indexing' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState<string | null>(null);

  const handleIndex = async (pathOverride?: string) => {
    setStatus('indexing');
    setMessage('Parsing AST, chunking code, generating ONNX embeddings & BM25 indices...');
    const targetPath = (pathOverride ?? repoPath).trim() || undefined;
    try {
      const res = await startIndexing(targetPath);
      let job = await getIndexingStatus(res.job_id);
      while (job.status === 'pending' || job.status === 'running') {
        setMessage(job.progress || 'Indexing repository...');
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        job = await getIndexingStatus(res.job_id);
      }
      if (job.status === 'error') throw new Error(job.error || 'Indexing failed');
      setStatus('success');
      setMessage('Indexing completed. Searching the repository...');
      onIndexingComplete(targetPath);
      window.setTimeout(() => {
        onClose();
        setStatus('idle');
        setMessage(null);
        setRepoPath('');
      }, 800);
    } catch (err: any) {
      setStatus('error');
      setMessage(err.message || 'Indexing failed');
    }
  };

  useEffect(() => {
    setRepoPath(initialRepoPath);
  }, [initialRepoPath, isOpen]);

  useEffect(() => {
    if (isOpen && autoStart && initialRepoPath && status === 'idle') void handleIndex(initialRepoPath);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, autoStart, initialRepoPath]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fadeIn">
      <div className="bg-[#161b22] border border-[#30363d] rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl">
        <div className="bg-[#0d1117] border-b border-[#30363d] px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <RefreshCw className="w-5 h-5 text-blue-400" />
            <h2 className="font-bold text-base text-gray-100">Index Repository</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-[#21262d] text-gray-400 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5 text-sm">
          <div className="space-y-2">
            <label className="text-xs font-semibold text-gray-300 flex items-center space-x-2">
              <Folder className="w-4 h-4 text-gray-400" />
              <span>Repository Directory Path (Optional)</span>
            </label>
            <input
              type="text"
              value={repoPath}
              onChange={(e) => setRepoPath(e.target.value)}
              placeholder="e.g. ../sample_repo or relative/absolute path"
              className="w-full bg-[#0d1117] border border-[#30363d] rounded-xl px-4 py-2.5 text-xs text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-500 font-mono"
            />
            <p className="text-[11px] text-gray-500">
              Leave blank to trigger indexing on the default codebase directory.
            </p>
          </div>

          {/* Features info */}
          <div className="bg-[#0d1117] border border-[#30363d] rounded-xl p-4 space-y-2 text-xs text-gray-400">
            <div className="font-semibold text-gray-300 flex items-center space-x-1.5">
              <Cpu className="w-4 h-4 text-indigo-400" />
              <span>Incremental Index Pipeline</span>
            </div>
            <ul className="list-disc list-inside space-y-1 text-gray-400 text-[11px]">
              <li>AST-guided chunking for Python, TS, JS, Go, Rust, Java</li>
              <li>CPU-optimized MiniLM-L6-v2 ONNX quantized embedder</li>
              <li>Okapi BM25 keyword indexer + FAISS vector memory</li>
            </ul>
          </div>

          {/* Status message */}
          {message && (
            <div
              className={`p-3 rounded-xl border text-xs flex items-center space-x-2.5 ${
                status === 'indexing'
                  ? 'bg-blue-500/10 border-blue-500/20 text-blue-400'
                  : status === 'success'
                  ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                  : 'bg-red-500/10 border-red-500/20 text-red-400'
              }`}
            >
              {status === 'indexing' && <RefreshCw className="w-4 h-4 animate-spin shrink-0" />}
              {status === 'success' && <CheckCircle className="w-4 h-4 shrink-0" />}
              {status === 'error' && <AlertTriangle className="w-4 h-4 shrink-0" />}
              <span>{message}</span>
            </div>
          )}

          {/* Submit Button */}
          <button
            onClick={() => void handleIndex()}
            disabled={status === 'indexing'}
            className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 text-white font-medium py-2.5 rounded-xl transition-colors flex items-center justify-center space-x-2 text-xs shadow-lg shadow-blue-600/20"
          >
            <Play className="w-4 h-4" />
            <span>{status === 'indexing' ? 'Building Index...' : 'Start Indexing'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
