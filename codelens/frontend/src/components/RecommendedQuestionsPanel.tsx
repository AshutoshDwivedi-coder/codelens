import React from 'react';
import { Search } from 'lucide-react';

interface RecommendedQuestionsPanelProps {
  questions: string[];
  repoName: string;
  hasReadme: boolean;
  isLoading?: boolean;
  onSelectQuestion: (question: string) => void;
}

export const RecommendedQuestionsPanel: React.FC<RecommendedQuestionsPanelProps> = ({
  questions,
  repoName,
  hasReadme,
  isLoading = false,
  onSelectQuestion,
}) => {
  if (isLoading) {
    return (
      <div className="bg-[#0d1117] border border-[#30363d] rounded-md p-3 animate-pulse">
        <div className="h-4 bg-[#21262d] rounded w-48 mb-3" />
        <div className="flex flex-wrap gap-2">
          {[1, 2, 3, 4].map((n) => (
            <div key={n} className="h-8 bg-[#21262d] rounded-lg w-40" />
          ))}
        </div>
      </div>
    );
  }

  if (!questions.length) return null;

  return (
    <div className="bg-[#0d1117] border border-[#30363d] rounded-md p-0 space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[11px] font-semibold text-gray-200 flex items-center gap-1.5">
          <Search className="w-3 h-3 text-[#d6a85f]" />
          Suggested searches
        </span>
        <span className="text-[10px] text-gray-500">{hasReadme ? repoName : 'Click a question to search code'}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {questions.map((q, idx) => (
          <button
            key={`${idx}-${q.slice(0, 24)}`}
            type="button"
            onClick={() => onSelectQuestion(q)}
            title={q}
            className="group max-w-full inline-flex items-start gap-1.5 text-left px-2.5 py-1.5 rounded-md bg-[#0d0e0e] hover:bg-[#151615] border border-[#242525] hover:border-[#51432d] transition-colors text-[10px] text-gray-200"
          >
            <Search className="w-3 h-3 text-[#d6a85f] shrink-0 mt-0.5" />
            <span className="leading-snug group-hover:text-[#e8c07d] transition-colors line-clamp-2">
              {q}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
};
