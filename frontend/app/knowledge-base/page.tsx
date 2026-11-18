'use client';

import React, { useEffect, useState, useRef, useCallback } from 'react';
import Link from 'next/link';
import {
  BookOpen,
  ArrowLeft,
  Upload,
  Search,
  Trash2,
  FileText,
  AlertCircle,
  CheckCircle2,
  Eye,
  X,
} from 'lucide-react';
import { api } from '@/services/api';
import { KBDocumentDetail, KBDocumentSummary, KBSearchResult } from '@/types';

export default function KnowledgeBasePage() {
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [uploadCategory, setUploadCategory] = useState<string>('Cybersecurity');
  const [documents, setDocuments] = useState<KBDocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // BM25 Search test
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<KBSearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);

  // Document preview modal
  const [previewDoc, setPreviewDoc] = useState<KBDocumentDetail | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadDocuments = useCallback(async () => {
    try {
      const docs = await api.listKBDocuments(selectedCategory);
      setDocuments(docs);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load knowledge base');
    } finally {
      setLoading(false);
    }
  }, [selectedCategory]);

  useEffect(() => {
    api.getKBCategories()
      .then((cats) => {
        setCategories(cats);
        if (cats.length > 0) setUploadCategory(cats[0]);
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const uploaded = await api.uploadKBDocument(file, uploadCategory);
      setSuccessMsg(`Uploaded "${uploaded.filename}" into ${uploaded.category} (${uploaded.chunk_count} chunks indexed).`);
      await loadDocuments();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDelete = async (id: string, filename: string) => {
    if (!confirm(`Delete "${filename}" from your Knowledge Base?`)) return;
    setError(null);
    try {
      await api.deleteKBDocument(id);
      setDocuments((prev) => prev.filter((d) => d.id !== id));
      if (previewDoc?.id === id) setPreviewDoc(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Delete failed');
    }
  };

  const handlePreview = async (id: string) => {
    try {
      const detail = await api.getKBDocument(id);
      setPreviewDoc(detail);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load preview');
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }
    setSearching(true);
    setError(null);
    try {
      const hits = await api.searchKB(searchQuery.trim(), selectedCategory);
      setSearchResults(hits);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="container mx-auto max-w-6xl px-6 py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link href="/" className="p-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-emerald-400" />
              Personal Knowledge Base
            </h1>
            <p className="text-xs text-zinc-400">
              Upload study notes & project docs (PDF, DOCX, TXT, MD). Indexed locally via BM25 for live answer retrieval.
            </p>
          </div>
        </div>
      </div>

      {/* Upload Bar */}
      <div className="p-5 rounded-xl border border-zinc-800 bg-zinc-900/40 flex flex-wrap items-end gap-4">
        <div className="flex-1 min-w-[220px]">
          <label className="block text-xs font-medium text-zinc-400 mb-1.5">Target Category</label>
          <select
            value={uploadCategory}
            onChange={(e) => setUploadCategory(e.target.value)}
            className="w-full px-3 py-2 text-xs bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-200 focus:outline-none focus:border-emerald-500"
          >
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt,.md"
          onChange={handleUpload}
          className="hidden"
        />

        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-medium text-xs transition-colors disabled:opacity-50"
        >
          <Upload className="h-3.5 w-3.5" />
          <span>{uploading ? 'Indexing...' : 'Upload Document (PDF/DOCX/TXT/MD)'}</span>
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3.5 rounded-lg bg-red-950/50 border border-red-800/50 text-xs text-red-300">
          <AlertCircle className="h-4 w-4 text-red-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {successMsg && (
        <div className="flex items-center gap-2 p-3.5 rounded-lg bg-emerald-950/40 border border-emerald-800/50 text-xs text-emerald-300">
          <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* BM25 Retrieval Test Bar */}
      <form onSubmit={handleSearch} className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="h-4 w-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Test BM25 retrieval (e.g. 'SAP authorization PFCG' or 'OTBI vs BI Publisher')..."
            className="w-full pl-9 pr-3 py-2 text-xs bg-zinc-900/60 border border-zinc-800 rounded-lg text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-emerald-500"
          />
        </div>
        <button
          type="submit"
          disabled={searching}
          className="px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 text-xs font-medium"
        >
          {searching ? 'Searching...' : 'Search KB'}
        </button>
        {searchResults !== null && (
          <button
            type="button"
            onClick={() => {
              setSearchQuery('');
              setSearchResults(null);
            }}
            className="px-3 py-2 rounded-lg text-xs text-zinc-400 hover:text-zinc-200"
          >
            Clear
          </button>
        )}
      </form>

      {/* Search Results */}
      {searchResults !== null && (
        <div className="p-4 rounded-xl border border-emerald-900/40 bg-emerald-950/10 space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
            BM25 Retrieval Results ({searchResults.length})
          </h2>
          {searchResults.length === 0 ? (
            <p className="text-xs text-zinc-400">No matching excerpts found for &quot;{searchQuery}&quot;.</p>
          ) : (
            <div className="space-y-2">
              {searchResults.map((hit, idx) => (
                <div key={`${hit.document_id}-${idx}`} className="p-3 rounded-lg bg-zinc-950/80 border border-zinc-800 space-y-1">
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="text-zinc-300 font-semibold">
                      {hit.filename} <span className="text-emerald-400">[{hit.category}]</span>
                    </span>
                    <span className="text-zinc-500">score: {hit.score}</span>
                  </div>
                  <p className="text-xs text-zinc-300 leading-relaxed">{hit.excerpt}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Category Filter Pills */}
      <div className="flex flex-wrap items-center gap-1.5">
        <button
          onClick={() => setSelectedCategory('all')}
          className={`px-2.5 py-1 rounded-full text-[11px] font-medium border transition-colors ${
            selectedCategory === 'all'
              ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
              : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200'
          }`}
        >
          All Categories
        </button>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => setSelectedCategory(cat)}
            className={`px-2.5 py-1 rounded-full text-[11px] font-medium border transition-colors ${
              selectedCategory === cat
                ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
                : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Document List */}
      {loading ? (
        <div className="p-10 text-center text-xs text-zinc-500 border border-zinc-800 rounded-xl">
          Loading knowledge base...
        </div>
      ) : documents.length === 0 ? (
        <div className="p-12 text-center border border-dashed border-zinc-800 rounded-xl bg-zinc-900/10 space-y-2">
          <FileText className="h-8 w-8 text-zinc-600 mx-auto" />
          <p className="text-sm font-medium text-zinc-300">No documents in this category</p>
          <p className="text-xs text-zinc-500">
            Upload your study guides, architecture notes, or interview prep docs above.
          </p>
        </div>
      ) : (
        <div className="divide-y divide-zinc-800 border border-zinc-800 rounded-xl overflow-hidden bg-zinc-900/20">
          {documents.map((doc) => (
            <div key={doc.id} className="p-4 flex items-start justify-between gap-4 hover:bg-zinc-800/30 transition-colors">
              <div className="space-y-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-zinc-100">{doc.filename}</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-emerald-300 border border-zinc-700">
                    {doc.category}
                  </span>
                  <span className="text-[10px] font-mono text-zinc-500">
                    {doc.chunk_count} chunk{doc.chunk_count === 1 ? '' : 's'} • {doc.char_count.toLocaleString()} chars
                  </span>
                </div>
                <p className="text-xs text-zinc-400 line-clamp-2">{doc.preview}</p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <button
                  onClick={() => handlePreview(doc.id)}
                  className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700"
                  title="Preview Document"
                >
                  <Eye className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={() => handleDelete(doc.id, doc.filename)}
                  className="p-1.5 rounded-lg text-zinc-500 hover:text-red-400 hover:bg-red-950/20"
                  title="Delete Document"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Preview Modal */}
      {previewDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
          <div className="w-full max-w-2xl rounded-xl border border-zinc-800 bg-zinc-950 p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div>
                <h3 className="text-sm font-semibold text-zinc-100">{previewDoc.filename}</h3>
                <p className="text-xs text-zinc-400">{previewDoc.category} • {previewDoc.chunk_count} chunks</p>
              </div>
              <button onClick={() => setPreviewDoc(null)} className="p-1 text-zinc-400 hover:text-zinc-200">
                <X className="h-4 w-4" />
              </button>
            </div>
            <pre className="text-xs text-zinc-300 whitespace-pre-wrap font-mono max-h-[60vh] overflow-y-auto leading-relaxed">
              {previewDoc.extracted_text}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
