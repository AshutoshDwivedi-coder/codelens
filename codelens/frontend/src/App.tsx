import React, { useEffect, useRef, useState } from 'react';
import { Header } from './components/Header';
import { SearchBar } from './components/SearchBar';
import { CodeCard } from './components/CodeCard';
import { EvolutionModal } from './components/EvolutionModal';
import { IndexingModal } from './components/IndexingModal';
import { HelpModal } from './components/HelpModal';
import { ReadmeInsightCard } from './components/ReadmeInsightCard';
import { CodebaseSummary } from './components/CodebaseSummary';
import { RecommendedQuestionsPanel } from './components/RecommendedQuestionsPanel';
import { ReadmeViewerModal } from './components/ReadmeViewerModal';
import {
  getHealth,
  getRepos,
  getVersions,
  searchCode,
  analyzeReadme,
  HealthResponse,
  SearchResult,
  ReadmeAnalysis,
  RepositoryReadme,
  getRepositoryReadme,
  RepoInfo,
} from './api';
import {
  Clock,
  Database,
  BookOpen,
  Lightbulb,
  SearchX,
} from 'lucide-react';

/** Fallback queries aligned with CodeLens itself when README has none. */
const SAMPLE_QUERIES = [
  'Where is health check status endpoint defined?',
  'Where is query search result caching stored?',
  'How does BM25 keyword matching compute scores?',
  'Where are dense vector embeddings generated?',
  'How does Tree-Sitter AST chunking parse code?',
];

export function App() {
  const [query, setQuery] = useState('');
  const [useHybrid, setUseHybrid] = useState(true);
  const [alpha, setAlpha] = useState(0.5);
  const [topK, setTopK] = useState(10);
  const [selectedRepos, setSelectedRepos] = useState<string[]>([]);
  const [repoListRevision, setRepoListRevision] = useState(0);
  // Maps repo id → actual filesystem/URL path for README analysis
  const [repoPaths, setRepoPaths] = useState<Record<string, string>>({});
  const [selectedCommit, setSelectedCommit] = useState('HEAD');

  const [results, setResults] = useState<SearchResult[]>([]);
  const [activeResultIndex, setActiveResultIndex] = useState(0);
  const [timingMs, setTimingMs] = useState<number | null>(null);
  const [totalCandidates, setTotalCandidates] = useState<number>(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [commits, setCommits] = useState<string[]>([]);
  const [availableRepos, setAvailableRepos] = useState<RepoInfo[]>([]);

  const [readmeAnalysis, setReadmeAnalysis] = useState<ReadmeAnalysis | null>(null);
  const [selectedRepoDescriptions, setSelectedRepoDescriptions] = useState<{ id: string; name: string; description: string }[]>([]);
  const [repositoryReadme, setRepositoryReadme] = useState<RepositoryReadme | null>(null);
  const [isRepositoryReadmeLoading, setIsRepositoryReadmeLoading] = useState(false);
  const [repositoryReadmeError, setRepositoryReadmeError] = useState<string | null>(null);
  const [isReadmeLoading, setIsReadmeLoading] = useState(false);

  const [historyResult, setHistoryResult] = useState<SearchResult | null>(null);
  const [isIndexModalOpen, setIsIndexModalOpen] = useState(false);
  const [indexTargetPath, setIndexTargetPath] = useState('');
  const [autoStartIndexing, setAutoStartIndexing] = useState(false);
  const [searchAfterIndex, setSearchAfterIndex] = useState<string | null>(null);
  const [isHelpModalOpen, setIsHelpModalOpen] = useState(false);

  const searchInputRef = useRef<HTMLInputElement>(null);

  const fetchHealthAndVersions = () => {
    getHealth()
      .then(setHealth)
      .catch((err) => console.warn('Health check warning:', err));
    getVersions()
      .then((data) => setCommits(data.commits.map((c) => c.commit_id)))
      .catch((err) => console.warn('Versions warning:', err));
    getRepos()
      .then((data) => setAvailableRepos(data.repos || []))
      .catch((err) => console.warn('Repositories warning:', err));
  };

  const fetchReadmeAnalysis = (repoList: string[], paths?: Record<string, string>) => {
    setIsReadmeLoading(true);
    const activePaths = paths || repoPaths;
    let targetRepo: string | undefined;
    if (repoList.length > 0) {
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

  const openRepositoryReadme = async () => {
    const repoId = selectedRepos[0];
    const repoPath = repoId ? repoPaths[repoId] || repoId : undefined;
    setRepositoryReadme(null);
    setRepositoryReadmeError(null);
    setIsRepositoryReadmeLoading(true);
    try {
      setRepositoryReadme(await getRepositoryReadme(repoPath));
    } catch (err: any) {
      setRepositoryReadmeError(err.message || 'Could not open repository README');
    } finally {
      setIsRepositoryReadmeLoading(false);
    }
  };

  useEffect(() => {
    fetchHealthAndVersions();
  }, []);

  useEffect(() => {
    fetchReadmeAnalysis(selectedRepos, repoPaths);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRepos]);

  useEffect(() => {
    let cancelled = false;
    const descriptionRepoIds = selectedRepos.length === 0
      ? availableRepos.filter((repo) => repo.source === 'indexed').map((repo) => repo.id)
      : selectedRepos;
    if (descriptionRepoIds.length < 2) {
      setSelectedRepoDescriptions([]);
      return () => { cancelled = true; };
    }

    const selected = descriptionRepoIds.map((id) => {
      const repo = availableRepos.find((item) => item.id === id);
      return {
        id,
        name: repo?.name || id.split(/[\\/]/).filter(Boolean).pop() || id,
        path: repoPaths[id] || repo?.path || id,
        fallback: repo?.description || 'Selected repository',
      };
    });
    void Promise.all(selected.map(async (repo) => {
      try {
        const analysis = await analyzeReadme(repo.path);
        return { id: repo.id, name: repo.name, description: analysis.summary || repo.fallback };
      } catch {
        return { id: repo.id, name: repo.name, description: repo.fallback };
      }
    })).then((descriptions) => {
      if (!cancelled) setSelectedRepoDescriptions(descriptions);
    });

    return () => { cancelled = true; };
  }, [selectedRepos, availableRepos, repoPaths]);

  // Keyboard shortcut listener for '/' to focus search bar (hint badge removed from UI)
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

  const handleSearch = async (overrideQuery?: string, repoFilterOverride?: string) => {
    const q = overrideQuery !== undefined ? overrideQuery : query;
    if (!q.trim()) return;

    setLoading(true);
    setError(null);
    setHasSearched(true);

    const repoFilterString = repoFilterOverride ?? (
      selectedRepos.length === 0
        ? undefined
        : selectedRepos.join(',')
    );

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
      setActiveResultIndex(0);
      setTimingMs(res.timing_ms);
      setTotalCandidates(res.total_candidates);
      if (res.error) {
        const selectedId = selectedRepos[0];
        const resolvedPath = repoPaths[selectedId] || selectedId || '';
        setError(
          res.error.includes('not indexed')
            ? `"${repoFilterString || 'Selected repository'}" is not indexed yet. Click "Index Now" — search will run automatically after indexing.`
            : res.error
        );
        if (res.error.includes('not indexed')) {
          setSearchAfterIndex(q);
          setIndexTargetPath(resolvedPath);
          setAutoStartIndexing(true);
          setIsIndexModalOpen(true);
        }
      }
    } catch (err: any) {
      const message = err.message || 'Search execution failed';
      // Guide users when nothing is indexed yet
      if (
        typeof message === 'string' &&
        (message.includes('not initialised') || message.includes('Index a repository'))
      ) {
        setError('No codebase is indexed yet. Open Index Repository, index the selected repo, then try the recommended questions again.');
      } else {
        setError(message);
      }
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const suggestedQuestions = readmeAnalysis?.suggested_questions || [];
  const recommendedQuestions =
    suggestedQuestions.length > 0 ? suggestedQuestions.slice(0, 8) : SAMPLE_QUERIES;

  const currentRepoDisplayName =
    selectedRepos.length === 0
      ? readmeAnalysis?.repo_name || 'CodeLens'
      : selectedRepos[0];

  const sidebarRepositories = selectedRepos.length === 0
    ? availableRepos.filter((repo) => repo.source === 'indexed')
    : selectedRepos.map((id) => availableRepos.find((repo) => repo.id === id) || ({
        id,
        name: id.split(/[\\/]/).filter(Boolean).pop() || id,
        description: 'Selected repository',
        path: repoPaths[id] || id,
        source: 'indexed' as const,
        chunk_count: 0,
      }));

  return (
    <div className="app-shell min-h-screen bg-[#0d1117] text-[#c9d1d9] flex flex-col font-sans selection:bg-amber-600/20 selection:text-amber-100">
      {/* Header Navigation */}
      <Header
        health={health}
        commits={commits}
        selectedCommit={selectedCommit}
        onSelectCommit={setSelectedCommit}
        onOpenIndexModal={() => setIsIndexModalOpen(true)}
        onOpenHelpModal={() => setIsHelpModalOpen(true)}
      />

      {/* Codebase summary above the search bar */}
      <div className="app-body">
      <aside className="project-sidebar">
        <nav className="side-nav" aria-label="Main navigation">
          <button className="side-nav-item active" onClick={() => searchInputRef.current?.focus()}><SearchX size={15}/>Search</button>
          <button className="side-nav-item" onClick={() => setIsHelpModalOpen(true)}><BookOpen size={15}/>Guide &amp; Glossary</button>
        </nav>
        <div className="sidebar-project-label">PROJECT</div>
        <CodebaseSummary
        title={sidebarRepositories.length > 1
          ? selectedRepos.length === 0
            ? `${sidebarRepositories.length} indexed repositories`
            : `${sidebarRepositories.length} repositories selected`
          : readmeAnalysis?.title || `${currentRepoDisplayName} Overview`}
        summary={
          readmeAnalysis?.summary ||
          'Select a repository to see a short summary of what it does and how it is structured.'
        }
        repoName={currentRepoDisplayName}
        hasReadme={!!readmeAnalysis?.has_readme}
        filename={readmeAnalysis?.filename}
        keyModules={readmeAnalysis?.key_modules}
        isLoading={isReadmeLoading}
        onOpenReadme={() => void openRepositoryReadme()}
        selectedRepoNames={sidebarRepositories.map((repo) => repo.name)}
        selectedRepoDescriptions={selectedRepoDescriptions}
        repoScopeLabel={selectedRepos.length === 0 ? 'ALL INDEXED REPOSITORIES' : 'SELECTED REPOSITORIES'}
        />
      </aside>
      <div className="workspace-column">

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
        repoListRevision={repoListRevision}
        setSelectedRepos={(repos, paths) => {
          setSelectedRepos(repos);
          if (paths) {
            setRepoPaths((prev) => ({ ...prev, ...paths }));
            fetchReadmeAnalysis(repos, { ...repoPaths, ...paths });
          }
        }}
        inputRef={searchInputRef}
        onAddRepository={(path) => {
          setIndexTargetPath(path);
          setAutoStartIndexing(true);
          setSearchAfterIndex(null);
          setIsIndexModalOpen(true);
        }}
      />

      {/* Recommended questions panel directly under the search bar */}
      <div className="bg-[#161b22] border-b border-[#30363d] px-6 pb-5">
        <div className="max-w-7xl mx-auto">
          <RecommendedQuestionsPanel
            questions={recommendedQuestions}
            repoName={currentRepoDisplayName}
            hasReadme={!!readmeAnalysis?.has_readme}
            isLoading={isReadmeLoading}
            onSelectQuestion={(q) => {
              setQuery(q);
              // If nothing indexed yet, open the indexing modal first
              const nothingIndexed = availableRepos.filter((r) => r.source === 'indexed').length === 0;
              if (nothingIndexed && selectedRepos.length > 0) {
                const sid = selectedRepos[0];
                const rp = repoPaths[sid] || sid || '';
                setSearchAfterIndex(q);
                setIndexTargetPath(rp);
                setAutoStartIndexing(!!rp);
                setIsIndexModalOpen(true);
              } else {
                handleSearch(q);
              }
            }}
          />
        </div>
      </div>

      {/* Main Workspace Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6 workspace-main">
        {/* Optional architecture details */}
        <ReadmeInsightCard
          analysis={readmeAnalysis}
          isLoading={isReadmeLoading}
          onRefresh={() => fetchReadmeAnalysis(selectedRepos)}
          selectedRepoName={currentRepoDisplayName}
          selectedRepoCount={sidebarRepositories.length}
        />

        {/* Search Telemetry Bar */}
        {timingMs !== null && !loading && (
          <div className="metadata-strip">
            <span><Clock size={13}/><strong>{(timingMs / 1000).toFixed(2)}s</strong></span>
            <span><Database size={13}/><strong>{totalCandidates}</strong> blocks scanned</span>
            <span>{useHybrid ? 'Hybrid retrieval' : 'Conceptual retrieval'}</span>
            <span><strong>{results.length}</strong> results</span>
          </div>
        )}

        {/* Error Banner */}
        {error && (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex flex-wrap items-center justify-between gap-3">
            <span>{error}</span>
            <button
              type="button"
              onClick={() => {
                if (error.includes('not indexed') || error.includes('No codebase')) {
                  const selectedId = selectedRepos[0];
                  const resolvedPath = repoPaths[selectedId] || selectedId || '';
                  if (resolvedPath) { setIndexTargetPath(resolvedPath); setAutoStartIndexing(true); }
                }
                setIsIndexModalOpen(true);
              }}
              className="px-3 py-1.5 rounded-lg bg-red-500/20 hover:bg-red-500/30 border border-red-500/30 text-red-200 text-xs font-semibold"
            >
              {error.includes('not indexed') ? 'Index Now →' : 'Open Index Repository'}
            </button>
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
          <div className="result-workspace">
            <div className="result-list" aria-label="Search results">
              {results.map((r, idx) => (
                <button key={r.chunk_id || idx} type="button" className={`result-row ${activeResultIndex === idx ? 'selected' : ''}`} onClick={() => setActiveResultIndex(idx)}>
                  <span className="result-rank">{idx + 1}</span>
                  <span className="result-row-content"><strong>{r.file_path}</strong><small>Lines {r.start_line}–{r.end_line}</small><span>{r.docstring || r.symbol_name || r.content.split('\n').find((line) => line.trim() && !line.trim().startsWith('#')) || 'Code match in this file.'}</span></span>
                  <span className={`result-score ${r.score >= .8 ? 'strong' : ''}`}>{Math.min(Math.round(r.score * 100), 99)}%</span>
                </button>
              ))}
            </div>
            {results[activeResultIndex] && <CodeCard key={results[activeResultIndex].chunk_id} result={results[activeResultIndex]} rank={activeResultIndex + 1} query={query} onOpenHistory={(res) => setHistoryResult(res)} />}
          </div>
        )}

        {/* No matches after an explicit search */}
        {!loading && hasSearched && results.length === 0 && !error && (
          <div className="py-12 px-8 border border-dashed border-[#30363d] rounded-2xl bg-[#161b22]/40 text-center space-y-4 max-w-3xl mx-auto">
            <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center mx-auto text-amber-400">
              <SearchX className="w-6 h-6" />
            </div>
            <div className="space-y-2">
              <h3 className="font-bold text-lg text-white">No matching code snippets</h3>
              <p className="text-sm text-gray-400 leading-relaxed">
                Nothing in the current index matched this question
                {selectedRepos.length === 0 ? '' : ` for “${currentRepoDisplayName}”`}.
                Index the selected repository first, or try another recommended question.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setIsIndexModalOpen(true)}
              className="inline-flex items-center space-x-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-semibold text-xs px-5 py-2.5 rounded-xl shadow-lg shadow-blue-600/20 transition-all"
            >
              <Database className="w-4 h-4" />
              <span>Index Repository</span>
            </button>
          </div>
        )}

        {/* Initial Empty State / Onboarding */}
        {!loading && !hasSearched && results.length === 0 && !error && (
          <div className="py-14 px-8 border border-dashed border-[#30363d] rounded-2xl bg-[#161b22]/40 text-center space-y-6 max-w-4xl mx-auto">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-blue-600/20 to-indigo-600/20 border border-blue-500/30 flex items-center justify-center mx-auto text-blue-400 shadow-lg shadow-blue-500/10">
              <Lightbulb className="w-7 h-7 text-amber-400" />
            </div>

            <div className="space-y-2 max-w-xl mx-auto">
              <h3 className="font-bold text-xl text-white tracking-tight">
                Search Source Code in Plain English
              </h3>
              <p className="text-sm text-gray-300 leading-relaxed">
                Pick a recommended question below the search bar, or type your own. Make sure the selected codebase is indexed so snippets can be found.
              </p>
            </div>

            <div className="pt-2 flex flex-wrap items-center justify-center gap-3">
              <button
                onClick={() => setIsIndexModalOpen(true)}
                className="inline-flex items-center space-x-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-semibold text-xs px-5 py-2.5 rounded-xl shadow-lg shadow-blue-600/20 transition-all"
              >
                <Database className="w-4 h-4" />
                <span>Index a Repository</span>
              </button>
              <button
                onClick={() => setIsHelpModalOpen(true)}
                className="inline-flex items-center space-x-2 bg-[#21262d] hover:bg-[#30363d] text-gray-200 font-semibold text-xs px-5 py-2.5 rounded-xl border border-[#30363d] transition-all"
              >
                <BookOpen className="w-4 h-4" />
                <span>Open Guide</span>
              </button>
            </div>
          </div>
        )}
      </main>
      </div>
      </div>

      {/* Evolutionary Code History Modal */}
      <EvolutionModal
        result={historyResult}
        onClose={() => setHistoryResult(null)}
      />

      {/* Index Management Modal */}
      <IndexingModal
        isOpen={isIndexModalOpen}
        initialRepoPath={indexTargetPath}
        autoStart={autoStartIndexing}
        onClose={() => {
          setIsIndexModalOpen(false);
          setAutoStartIndexing(false);
        }}
        onIndexingComplete={(repository) => {
          setRepoListRevision((revision) => revision + 1);
          fetchHealthAndVersions();
          // After indexing a new repo, select it automatically and refresh questions
          if (repository?.id && repository.path !== '.') {
            const newPaths = { ...repoPaths, [repository.id]: repository.path };
            setRepoPaths(newPaths);
            setSelectedRepos([repository.id]);
            fetchReadmeAnalysis([repository.id], newPaths);
            if (searchAfterIndex) {
              setSearchAfterIndex(null);
              void handleSearch(searchAfterIndex, repository.id);
            }
          } else {
            fetchReadmeAnalysis(selectedRepos);
          }
          setIndexTargetPath('');
          setAutoStartIndexing(false);
        }}
      />

      {/* Help & Plain English Glossary Modal */}
      <HelpModal
        isOpen={isHelpModalOpen}
        onClose={() => setIsHelpModalOpen(false)}
      />

      <ReadmeViewerModal
        readme={repositoryReadme}
        loading={isRepositoryReadmeLoading}
        error={repositoryReadmeError}
        onClose={() => {
          setRepositoryReadme(null);
          setRepositoryReadmeError(null);
        }}
      />
    </div>
  );
}
