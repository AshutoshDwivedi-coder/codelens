import React, { useState } from 'react';
import {
  X,
  BookOpen,
  Search,
  Zap,
  GitCommit,
  Layers,
  HelpCircle,
  Lightbulb,
  CheckCircle2,
  Shield,
  Code2,
} from 'lucide-react';

interface HelpModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const HelpModal: React.FC<HelpModalProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<'guide' | 'glossary' | 'faq'>('guide');

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-fadeIn">
      <div className="bg-[#161b22] border border-[#30363d] rounded-2xl w-full max-w-3xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="bg-gradient-to-r from-blue-900/40 via-indigo-900/30 to-purple-900/40 border-b border-[#30363d] px-6 py-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/30 flex items-center justify-center text-blue-400">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                CodeLens Plain English Guide & Glossary
              </h2>
              <p className="text-xs text-blue-300/80">
                Designed for everyone — product managers, designers, executives, and engineers alike
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg bg-[#21262d] text-gray-400 hover:text-white hover:bg-[#30363d] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-[#30363d] bg-[#0d1117] px-6 pt-3 space-x-4">
          <button
            onClick={() => setActiveTab('guide')}
            className={`pb-3 text-xs font-semibold flex items-center space-x-2 border-b-2 transition-all ${
              activeTab === 'guide'
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
          >
            <Lightbulb className="w-4 h-4" />
            <span>How to Search</span>
          </button>
          <button
            onClick={() => setActiveTab('glossary')}
            className={`pb-3 text-xs font-semibold flex items-center space-x-2 border-b-2 transition-all ${
              activeTab === 'glossary'
                ? 'border-purple-500 text-purple-400'
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
          >
            <BookOpen className="w-4 h-4" />
            <span>Plain English Glossary</span>
          </button>
          <button
            onClick={() => setActiveTab('faq')}
            className={`pb-3 text-xs font-semibold flex items-center space-x-2 border-b-2 transition-all ${
              activeTab === 'faq'
                ? 'border-emerald-500 text-emerald-400'
                : 'border-transparent text-gray-400 hover:text-gray-200'
            }`}
          >
            <HelpCircle className="w-4 h-4" />
            <span>Frequently Asked Questions</span>
          </button>
        </div>

        {/* Modal Body Content */}
        <div className="p-6 overflow-y-auto space-y-6 text-sm text-gray-300">
          {activeTab === 'guide' && (
            <div className="space-y-5">
              <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4 flex items-start space-x-3 text-xs leading-relaxed text-blue-200">
                <Lightbulb className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold text-blue-300 block mb-1">
                    You don't need to write code to search code!
                  </span>
                  CodeLens uses AI-assisted semantic search. You can search using plain English business descriptions, feature names, or technical terms.
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-[#0d1117] border border-[#30363d] rounded-xl p-4 space-y-2">
                  <div className="flex items-center space-x-2 text-emerald-400 font-semibold text-xs uppercase tracking-wider">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Plain English Examples</span>
                  </div>
                  <ul className="text-xs space-y-2 text-gray-300">
                    <li className="bg-[#161b22] p-2 rounded border border-[#21262d] font-mono text-[11px] text-emerald-300">
                      "Where is health check status checked?"
                    </li>
                    <li className="bg-[#161b22] p-2 rounded border border-[#21262d] font-mono text-[11px] text-emerald-300">
                      "How are search scores blended together?"
                    </li>
                    <li className="bg-[#161b22] p-2 rounded border border-[#21262d] font-mono text-[11px] text-emerald-300">
                      "Where is query caching saved in memory?"
                    </li>
                  </ul>
                </div>

                <div className="bg-[#0d1117] border border-[#30363d] rounded-xl p-4 space-y-2">
                  <div className="flex items-center space-x-2 text-purple-400 font-semibold text-xs uppercase tracking-wider">
                    <Code2 className="w-4 h-4" />
                    <span>Technical / Keyword Search</span>
                  </div>
                  <ul className="text-xs space-y-2 text-gray-300">
                    <li className="bg-[#161b22] p-2 rounded border border-[#21262d] font-mono text-[11px] text-purple-300">
                      "bm25.py search"
                    </li>
                    <li className="bg-[#161b22] p-2 rounded border border-[#21262d] font-mono text-[11px] text-purple-300">
                      "def get_cache"
                    </li>
                    <li className="bg-[#161b22] p-2 rounded border border-[#21262d] font-mono text-[11px] text-purple-300">
                      "VersionManager"
                    </li>
                  </ul>
                </div>
              </div>

              <div className="space-y-3">
                <h3 className="font-bold text-gray-100 text-sm flex items-center gap-2">
                  <Zap className="w-4 h-4 text-amber-400" /> Understanding Retrieval Modes
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div className="bg-[#0d1117] p-3 rounded-lg border border-[#30363d]">
                    <span className="font-bold text-blue-400 block mb-1">Hybrid Mode (Recommended)</span>
                    Blends exact word matching with deep conceptual meaning search. Gives the highest accuracy.
                  </div>
                  <div className="bg-[#0d1117] p-3 rounded-lg border border-[#30363d]">
                    <span className="font-bold text-purple-400 block mb-1">Dense Only Mode</span>
                    Focuses strictly on meaning and concept search, ignoring exact word spelling. Great for open-ended queries.
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'glossary' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-3 text-xs">
                <div className="bg-[#0d1117] border border-[#30363d] p-4 rounded-xl space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-blue-400 text-sm">BM25 (Lexical Match)</span>
                    <span className="px-2 py-0.5 bg-blue-500/10 text-blue-300 rounded text-[10px] font-mono">
                      Keyword Search
                    </span>
                  </div>
                  <p className="text-gray-300 leading-relaxed">
                    Like a high-speed Ctrl+F search. It checks if the specific words you typed appear directly inside the code or docstrings.
                  </p>
                </div>

                <div className="bg-[#0d1117] border border-[#30363d] p-4 rounded-xl space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-purple-400 text-sm">Dense Embedding (Semantic Match)</span>
                    <span className="px-2 py-0.5 bg-purple-500/10 text-purple-300 rounded text-[10px] font-mono">
                      AI Concept Search
                    </span>
                  </div>
                  <p className="text-gray-300 leading-relaxed">
                    Converts code and queries into numerical representations of meaning. It allows finding relevant code even if you use different vocabulary than the engineer who wrote it.
                  </p>
                </div>

                <div className="bg-[#0d1117] border border-[#30363d] p-4 rounded-xl space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-amber-400 text-sm">RRF Fusion (Reciprocal Rank Fusion)</span>
                    <span className="px-2 py-0.5 bg-amber-500/10 text-amber-300 rounded text-[10px] font-mono">
                      Hybrid Scoring
                    </span>
                  </div>
                  <p className="text-gray-300 leading-relaxed">
                    An algorithm that combines keyword rankings and semantic rankings into one fair, unified score so the best overall match appears at the top.
                  </p>
                </div>

                <div className="bg-[#0d1117] border border-[#30363d] p-4 rounded-xl space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-emerald-400 text-sm">AST / Function Chunking</span>
                    <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-300 rounded text-[10px] font-mono">
                      Code Parsing
                    </span>
                  </div>
                  <p className="text-gray-300 leading-relaxed">
                    Abstract Syntax Tree parsing. Instead of chopping code by arbitrary page lines, CodeLens smartly groups code into self-contained functions and classes.
                  </p>
                </div>

                <div className="bg-[#0d1117] border border-[#30363d] p-4 rounded-xl space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-cyan-400 text-sm">Commit & Lineage Evolution</span>
                    <span className="px-2 py-0.5 bg-cyan-500/10 text-cyan-300 rounded text-[10px] font-mono">
                      History Tracking
                    </span>
                  </div>
                  <p className="text-gray-300 leading-relaxed">
                    Tracks how a piece of code changed across git version snapshots. Allows seeing how a function evolved over time or across refactorings.
                  </p>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'faq' && (
            <div className="space-y-4 text-xs">
              <div className="bg-[#0d1117] border border-[#30363d] p-4 rounded-xl space-y-1">
                <span className="font-bold text-gray-100 text-sm block mb-1">
                  Can non-engineers use CodeLens to understand codebase architecture?
                </span>
                <p className="text-gray-300 leading-relaxed">
                  Yes! CodeLens includes a <strong>Plain English Mode</strong> for every search result. Toggle the "Plain English Explanation" tab on any snippet card to read a layperson breakdown of what that code accomplishes, what inputs it accepts, and why it exists.
                </p>
              </div>

              <div className="bg-[#0d1117] border border-[#30363d] p-4 rounded-xl space-y-1">
                <span className="font-bold text-gray-100 text-sm block mb-1">
                  What does a 90%+ match score mean?
                </span>
                <p className="text-gray-300 leading-relaxed">
                  A high percentage score indicates high confidence that the snippet directly answers your search intention. A green badge indicates strong confidence, while yellow indicates moderate relevance.
                </p>
              </div>

              <div className="bg-[#0d1117] border border-[#30363d] p-4 rounded-xl space-y-1">
                <span className="font-bold text-gray-100 text-sm block mb-1">
                  How do I search a different repository folder?
                </span>
                <p className="text-gray-300 leading-relaxed">
                  Click <strong>"Rebuild Index"</strong> in the top header, paste the folder path of any local repository on your computer, and CodeLens will process and index it.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="bg-[#0d1117] border-t border-[#30363d] px-6 py-3 flex items-center justify-between text-xs text-gray-400">
          <span className="flex items-center gap-1 text-gray-400">
            <Shield className="w-3.5 h-3.5 text-blue-400" /> CodeLens 100% CPU-Local Security (No cloud data leakage)
          </span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold transition-colors"
          >
            Got it!
          </button>
        </div>
      </div>
    </div>
  );
};
