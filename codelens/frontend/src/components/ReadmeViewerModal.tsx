import React from 'react';
import { BookOpen, X } from 'lucide-react';
import { RepositoryReadme } from '../api';

interface ReadmeViewerModalProps {
  readme: RepositoryReadme | null;
  error?: string | null;
  loading?: boolean;
  onClose: () => void;
}

export const ReadmeViewerModal: React.FC<ReadmeViewerModalProps> = ({ readme, error, loading = false, onClose }) => {
  if (!readme && !error && !loading) return null;

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/80 p-4" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section className="readme-viewer w-full max-w-3xl max-h-[85vh] flex flex-col overflow-hidden rounded-lg border border-[#242525] bg-[#0d0e0e] shadow-2xl" role="dialog" aria-modal="true" aria-label="Repository README">
        <header className="flex items-center justify-between gap-3 border-b border-[#242525] bg-[#090a0a] px-4 py-3">
          <div className="flex min-w-0 items-center gap-2">
            <BookOpen className="h-4 w-4 shrink-0 text-[#d6a85f]" />
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-[#e7e4dc]">{readme?.repo_name || 'Repository'}</div>
              <div className="font-mono text-[10px] text-[#777777]">{readme?.filename || 'README.md'}</div>
            </div>
          </div>
          <button type="button" onClick={onClose} className="rounded-md border border-[#242525] bg-[#121313] p-1.5 text-[#a3a09a] hover:text-[#e7e4dc]" aria-label="Close README">
            <X className="h-4 w-4" />
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-auto p-5">
          {loading ? <p className="text-sm text-[#a3a09a]">Loading README…</p> : error ? <p className="text-sm text-[#d98b7e]">{error}</p> : (
            <pre className="readme-content whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-[#d5d2ca]">{readme?.content}</pre>
          )}
        </div>
      </section>
    </div>
  );
};
