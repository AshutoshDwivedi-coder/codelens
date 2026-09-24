import React, { useEffect, useRef, useState } from 'react';
import { Header } from './components/Header';
import { SearchBar } from './components/SearchBar';
import { CodeCard } from './components/CodeCard';
import { EvolutionModal } from './components/EvolutionModal';
import { IndexingModal } from './components/IndexingModal';
import { HelpModal } from './components/HelpModal';
import { ReadmeInsightCard } from './components/ReadmeInsightCard';
import {
  getHealth,
  getVersions,
  searchCode,
  analyzeReadme,
  HealthResponse,
  SearchResult,
  ReadmeAnalysis,
} from './api';
import {
  Search,
  Zap,
  Clock,
  Database,
  Code,
  Sparkles,
  BookOpen,
  HelpCircle,
  Lightbulb,
  ShieldCheck,
  CheckCircle2,
} from 'lucide-react';

export function App() {
  const [query, setQuery] = useState('');
  const [useHybrid, setUseHybrid] = useState(true);
  const [alpha, setAlpha] = useState(0.5);
  const [topK, setTopK] = useState(10);
  const [selectedRepos, setSelectedRepos] = useState<string[]>(['all']);
  // Maps repo id → actual filesystem/URL path for README analysis
  const [repoPaths, setRepoPaths] = useState<Record<string, string>>({});
  const [selectedCommit, setSelectedCommit] = useState('HEAD');

  const [results, setResults] = useState<SearchResult[]>([]);
  const [timingMs, setTimingMs] = useState<number | null>(null);
  const [totalCandidates, setTotalCandidates] = useState<number>(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [commits, setCommits] = useState<string[]>([]);

  const [readmeAnalysis, setReadmeAnalysis] = useState<ReadmeAnalysis | null>(null);
  const [isReadmeLoading, setIsReadmeLoading] = useState(false);

  const [historyResult, setHistoryResult] = useState<SearchResult | null>(null);
  const [isIndexModalOpen, setIsIndexModalOpen] = useState(false);
  const [isHelpModalOpen, setIsHelpModalOpen] = useState(false);

  const searchInputRef = useRef<HTMLInputElement>(null);

  const fetchHealthAndVersions = () => {
    getHealth()
      .then(setHealth)
      .catch((err) => console.warn('Health check warning:', err));
    getVersions()
      .then((data) => setCommits(data.commits.map((c) => c.commit_id)))
      .catch((err) => console.warn('Versions warning:', err));
  };

  const fetchReadmeAnalysis = (repoList: string[], paths?: Record<string, string>) => {
    setIsReadmeLoading(true);
    const activePaths = paths || repoPaths;
    let targetRepo: string | undefined;
    if (repoList.length > 0 && !repoList.includes('all')) {
      const repoId = repoList[0];
      // Prefer the actual path if we have it, otherwise use the id
      targetRepo = activePaths[repoId] || repoId;
    }

    analyzeReadme(targetRepo)
      .then((data) => setReadmeAnalysis(data))
      .catch((err) => {
        console.warn('README analysis warning:', err);
        setReadmeAnalysis(null);
      })
      .finally(() => setIsReadmeLoading(false));
  };

  useEffect(() => {
    fetchHealthAndVersions();
  }, []);

  useEffect(() => {
    fetchReadmeAnalysis(selectedRepos, repoPaths);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRepos]);

  // Keyboard shortcut listener for '/' to focus search bar
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.key === '/' &&
        document.activeElement?.tagName !== 'INPUT' &&
        document.activeElement?.tagName !== 'TEXTAREA'
      ) {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleSearch = async (overrideQuery?: string) => {
    const q = overrideQuery !== undefined ? overrideQuery : query;
    if (!q.trim()) return;

    setLoading(true);
    setError(null);

    const repoFilterString =
      selectedRepos.length === 0 || selectedRepos.includes('all')
        ? undefined
        : selectedRepos.join(',');

    try {
      const res = await searchCode({
        query: q,
        top_k: topK,
        repo_filter: repoFilterString,
        commit_id: selectedCommit !== 'HEAD' ? selectedCommit : undefined,
        use_hybrid: useHybrid,
        alpha,
      });
      setResults(res.results || []);
      setTimingMs(res.timing_ms);
      setTotalCandidates(res.total_candidates);
    } catch (err: any) {
      setError(err.message || 'Search execution failed');
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const sampleQueries = [
    { label: 'Health & Server Status', query: 'Where is health check status endpoint defined?' },
    { label: 'Search Query Caching', query: 'Where is query search result caching stored?' },
    { label: 'BM25 Keyword Engine', query: 'How does BM25 keyword matching compute scores?' },
    { label: 'Vector AI Embeddings', query: 'Calculate sentence transformer embedding vectors' },
    { label: 'Commit History Lineage', query: 'AST structural similarity and git history lineage' },
  ];

  const suggestedQuestions = readmeAnalysis?.suggested_questions || [];
  const quickQueries = suggestedQuestions.length > 0
    ? suggestedQuestions.slice(0, 5).map((q) => {
        let label = q;
        if (label.length > 36) {
          label = label.replace(/^Where is (the )?/i, '').replace(/^How does (the )?/i, '').replace(/\?$/, '');
          label = label.charAt(0).toUpperCase() + label.slice(1);
          if (label.length > 32) label = label.slice(0, 30) + '…';
        }
        return { label, query: q };
      })
    : sampleQueries;

  const currentRepoDisplayName =
    selectedRepos.includes('all') || selectedRepos.length === 0
      ? 'CodeLens'
      : selectedRepos[0];

  return (
    <div className="min-h-screen bg-[#0d1117] text-[#c9d1d9] flex flex-col font-sans selection:bg-blue-600/30 selection:text-blue-200">
      {/* Header Navigation */}
      <Header
        health={health}
        commits={commits}
        selectedCommit={selectedCommit}
        onSelectCommit={setSelectedCommit}
        onOpenIndexModal={() => setIsIndexModalOpen(true)}
        onOpenHelpModal={() => setIsHelpModalOpen(true)}
      />

      {/* Main Search Controls */}
      <SearchBar
        query={query}
        setQuery={setQuery}
        onSearch={() => handleSearch()}
        useHybrid={useHybrid}
        setUseHybrid={setUseHybrid}
        alpha={alpha}
        setAlpha={setAlpha}
        topK={topK}
        setTopK={setTopK}
        selectedRepos={selectedRepos}
        setSelectedRepos={(repos, paths) => {
          setSelectedRepos(repos);
          if (paths) {
            setRepoPaths((prev) => ({ ...prev, ...paths }));
            fetchReadmeAnalysis(repos, { ...repoPaths, ...paths });
          }
        }}
        inputRef={searchInputRef}
      />

      {/* Main Workspace Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">
        {/* Repository README Analysis & Suggested Questions */}
        <ReadmeInsightCard
          analysis={readmeAnalysis}
          isLoading={isReadmeLoading}
          onSelectQuestion={(q) => {
            setQuery(q);
            handleSearch(q);
          }}
          onRefresh={() => fetchReadmeAnalysis(selectedRepos)}
          selectedRepoName={currentRepoDisplayName}
        />

        {/* Sample Queries Bar */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-gray-400 font-semibold flex items-center gap-1.5 shrink-0">
            <Sparkles className="w-3.5 h-3.5 text-blue-400" />
            {readmeAnalysis?.has_readme ? `Suggested for ${currentRepoDisplayName}:` : 'Quick Search Ideas:'}
          </span>
          {quickQueries.map((item) => (
            <button
              key={item.label}
              onClick={() => {
                setQuery(item.query);
                handleSearch(item.query);
              }}
              className="bg-[#161b22] hover:bg-[#21262d] hover:border-blue-500/40 text-gray-300 border border-[#30363d] px-3 py-1.5 rounded-lg transition-all font-sans text-xs flex items-center space-x-1.5 group"
            >
              <span>{item.label}</span>
            </button>
          ))}
        </div>

        {/* Search Telemetry Bar */}
        {timingMs !== null && !loading && (
          <div className="bg-[#161b22] border border-[#30363d] px-5 py-3 rounded-xl flex flex-wrap items-center justify-between text-xs text-gray-300 gap-3 shadow-sm">
            <div className="flex items-center space-x-5 font-mono">
              <div className="flex items-center space-x-1.5 text-blue-400" title="Response time in milliseconds">
                <Clock className="w-4 h-4" />
                <span>Search Speed: <strong>{timingMs.toFixed(1)} ms</strong></span>
              </div>
              <div className="flex items-center space-x-1.5 text-purple-400" title="Total code blocks evaluated">
                <Database className="w-4 h-4" />
                <span>Scanned Code Blocks: <strong>{totalCandidates}</strong></span>
              </div>
              <div className="flex items-center space-x-1.5 text-emerald-400">
                <Zap className="w-4 h-4" />
                <span>Algorithm: <strong>{useHybrid ? 'Smart Hybrid (Keyword + AI)' : 'Conceptual AI'}</strong></span>
              </div>
            </div>
            <span className="text-gray-400 font-medium">
              Found <strong>{results.length}</strong> top matching code snippets
            </span>
          </div>
        )}

        {/* Error Banner */}
        {error && (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="space-y-4">
            {[1, 2, 3].map((n) => (
              <div key={n} className="bg-[#161b22] border border-[#30363d] rounded-2xl p-6 space-y-4 animate-pulse">
                <div className="h-5 bg-[#21262d] rounded-lg w-1/3"></div>
                <div className="h-20 bg-[#21262d] rounded-xl w-full"></div>
              </div>
            ))}
          </div>
        )}

        {/* Search Results List */}
        {!loading && results.length > 0 && (
          <div className="space-y-5">
            {results.map((r, idx) => (
              <CodeCard
                key={r.chunk_id || idx}
                result={r}
                rank={idx + 1}
                onOpenHistory={(res) => setHistoryResult(res)}
              />
            ))}
          </div>
        )}

        {/* Initial Empty State / Non-Technical Onboarding */}
        {!loading && results.length === 0 && !error && (
          <div className="py-14 px-8 border border-dashed border-[#30363d] rounded-2xl bg-[#161b22]/40 text-center space-y-6 max-w-4xl mx-auto">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-blue-600/20 to-indigo-600/20 border border-blue-500/30 flex items-center justify-center mx-auto text-blue-400 shadow-lg shadow-blue-500/10">
              <Lightbulb className="w-7 h-7 text-amber-400" />
            </div>

            <div className="space-y-2 max-w-xl mx-auto">
              <h3 className="font-bold text-xl text-white tracking-tight">
                Search Source Code in Plain English
              </h3>
              <p className="text-sm text-gray-300 leading-relaxed">
                CodeLens uses AI-powered semantic search to connect natural business questions directly to the underlying source code.
              </p>
            </div>

            {/* Feature Cards Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-left pt-2">
              <div className="bg-[#0d1117] border border-[#30363d] rounded-xl p-4 space-y-2">
                <div className="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-400 flex items-center justify-center font-bold text-xs">
                  💡
                </div>
                <h4 className="font-bold text-gray-200 text-sm">Plain English Views</h4>
                <p className="text-xs text-gray-400 leading-relaxed">
                  Every result comes with an automatic plain-English breakdown of what the code does step-by-step.
                </p>
              </div>

              <div className="bg-[#0d1117] border border-[#30363d] rounded-xl p-4 space-y-2">
                <div className="w-8 h-8 rounded-lg bg-purple-500/10 text-purple-400 flex items-center justify-center font-bold text-xs">
                  🌿
                </div>
                <h4 className="font-bold text-gray-200 text-sm">Version History</h4>
                <p className="text-xs text-gray-400 leading-relaxed">
                  Track how functions and features changed across git commits over time with AST lineage tracking.
                </p>
              </div>

              <div className="bg-[#0d1117] border border-[#30363d] rounded-xl p-4 space-y-2">
                <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center font-bold text-xs">
                  ⚡
                </div>
                <h4 className="font-bold text-gray-200 text-sm">Sub-10ms Fast CPU</h4>
                <p className="text-xs text-gray-400 leading-relaxed">
                  Lightning fast hybrid search powered by BM25 exact keywords and CPU dense embeddings.
                </p>
              </div>
            </div>

            <div className="pt-2">
              <button
                onClick={() => setIsHelpModalOpen(true)}
                className="inline-flex items-center space-x-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-semibold text-xs px-5 py-2.5 rounded-xl shadow-lg shadow-blue-600/20 transition-all"
              >
                <BookOpen className="w-4 h-4" />
                <span>Open Plain English Guide & Glossary</span>
              </button>
            </div>
          </div>
        )}
      </main>

      {/* Evolutionary Code History Modal */}
      <EvolutionModal
        result={historyResult}
        onClose={() => setHistoryResult(null)}
      />

      {/* Index Management Modal */}
      <IndexingModal
        isOpen={isIndexModalOpen}
        onClose={() => setIsIndexModalOpen(false)}
        onIndexingComplete={(repoPath?: string) => {
          fetchHealthAndVersions();
          // After indexing a new repo, select it automatically and refresh questions
          if (repoPath && repoPath !== '.') {
            const repoId = repoPath.split(/[/\\]/).filter(Boolean).pop() || repoPath;
            const newPaths = { ...repoPaths, [repoId]: repoPath };
            setRepoPaths(newPaths);
            setSelectedRepos([repoId]);
            fetchReadmeAnalysis([repoId], newPaths);
          } else {
            fetchReadmeAnalysis(selectedRepos);
          }
        }}
      />

      {/* Help & Plain English Glossary Modal */}
      <HelpModal
        isOpen={isHelpModalOpen}
        onClose={() => setIsHelpModalOpen(false)}
      />
    </div>
  );
}
