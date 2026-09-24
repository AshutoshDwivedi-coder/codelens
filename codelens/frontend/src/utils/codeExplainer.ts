// Utility to translate code snippets into plain-English explanations for non-technical users

import { SearchResult } from '../api';

export interface CodeExplanation {
  headline: string;
  purpose: string;
  steps: string[];
  role: string;
  complexity: 'Simple' | 'Moderate' | 'Advanced';
}

export function explainCodeSnippet(result: SearchResult): CodeExplanation {
  const code = result.content || result.code || '';
  const filePath = (result.file_path || '').toLowerCase();
  const symbolName = result.symbol_name || '';
  const docstring = (result.docstring || '').trim();
  const signature = result.signature || '';

  let headline = symbolName ? `Function/Class: ${symbolName}` : `Code Block in ${result.file_path}`;
  let purpose = '';
  let steps: string[] = [];
  let role = '';
  let complexity: 'Simple' | 'Moderate' | 'Advanced' = 'Moderate';

  // Extract from docstring if available
  if (docstring) {
    purpose = docstring.split('\n')[0].replace(/^["'\s]+|["'\s]+$/g, '');
  }

  // Heuristic analysis based on file path and code content
  if (filePath.includes('search') || filePath.includes('query')) {
    if (!purpose) purpose = 'Handles code search requests by comparing your query against indexed source code.';
    role = 'Core Search Functionality';
    steps = [
      'Receives and validates user search parameters.',
      'Executes lexical (word-based) and semantic (meaning-based) algorithms.',
      'Ranks code snippets by relevance and returns sorted results.',
    ];
    complexity = 'Advanced';
  } else if (filePath.includes('bm25')) {
    if (!purpose) purpose = 'Performs fast exact-keyword matching across the codebase (like a smart Ctrl+F).';
    role = 'Keyword Matching Engine';
    steps = [
      'Tokenizes query terms into individual keywords.',
      'Calculates word frequency and inverse document frequencies.',
      'Scores code files based on exact term occurrences.',
    ];
    complexity = 'Moderate';
  } else if (filePath.includes('embed') || filePath.includes('encoder')) {
    if (!purpose) purpose = 'Converts code text into mathematical vector representations to understand meaning.';
    role = 'AI Embedding & Neural Vectorizer';
    steps = [
      'Loads a deep learning sentence-transformer model on CPU.',
      'Encodes code blocks into dense numerical vectors.',
      'Enables searching by concept and intent, even with different wording.',
    ];
    complexity = 'Advanced';
  } else if (filePath.includes('cache')) {
    if (!purpose) purpose = 'Stores recent search queries in memory so repeat searches load instantly.';
    role = 'Performance & Latency Optimization';
    steps = [
      'Checks if a search query was already performed recently.',
      'Returns cached results in under 1ms if available.',
      'Saves CPU compute time and reduces server load.',
    ];
    complexity = 'Simple';
  } else if (filePath.includes('lineage') || filePath.includes('version')) {
    if (!purpose) purpose = 'Tracks how functions and files evolve across git commits over time.';
    role = 'Version History & AST Lineage';
    steps = [
      'Analyzes structural similarity between code snippets across commits.',
      'Detects code modifications, renames, and refactoring history.',
      'Allows viewing past snapshots of functions.',
    ];
    complexity = 'Moderate';
  } else if (filePath.includes('chunk') || filePath.includes('normalize')) {
    if (!purpose) purpose = 'Breaks down raw code files into clean, readable functions and classes.';
    role = 'Code Parsing & Structure Analysis';
    steps = [
      'Uses AST (Abstract Syntax Tree) parsers to read code grammar.',
      'Extracts functions, classes, docstrings, and line ranges.',
      'Normalizes text so search indexing is accurate.',
    ];
    complexity = 'Moderate';
  } else if (filePath.includes('main') || filePath.includes('api')) {
    if (!purpose) purpose = 'Serves as the main HTTP API server connector for the web application.';
    role = 'Backend API Entry Point';
    steps = [
      'Receives incoming HTTP requests from the web browser.',
      'Applies CORS security, logging, and performance timing headers.',
      'Routes search requests to retrieval services.',
    ];
    complexity = 'Simple';
  } else {
    if (!purpose) purpose = `Executes specialized operations in ${result.file_path}.`;
    role = 'Code Infrastructure';
    steps = [
      'Processes inputs and validates data state.',
      'Performs underlying business logic computations.',
      'Returns processed results to calling components.',
    ];
  }

  // Refine steps from code keywords if code contains specific operations
  if (code.includes('try:') && code.includes('except')) {
    steps.push('Includes safety error handling to handle unexpected failures smoothly.');
  }

  return { headline, purpose, steps, role, complexity };
}
