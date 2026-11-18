'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import {
  History,
  ArrowLeft,
  Search,
  Download,
  Trash2,
  MessageSquare,
  FileText,
  Clock,
  AlertCircle,
  ExternalLink,
  Eraser,
} from 'lucide-react';
import { api } from '@/services/api';
import { HistorySearchHit, HistorySessionDetail, HistorySessionItem } from '@/types';

export default function HistoryPage() {
  const [sessions, setSessions] = useState<HistorySessionItem[]>([]);
  const [selectedDetail, setSelectedDetail] = useState<HistorySessionDetail | null>(null);
  const [activeTab, setActiveTab] = useState<'qa' | 'transcript'>('qa');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Search past questions
  const [query, setQuery] = useState('');
  const [searchHits, setSearchHits] = useState<HistorySearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);

  const loadHistory = useCallback(async () => {
    try {
      const items = await api.listHistory();
      setSessions(items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load history');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const handleSelectSession = async (sessionId: string) => {
    setError(null);
    try {
      const detail = await api.getHistoryDetail(sessionId);
      setSelectedDetail(detail);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to open session');
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) {
      setSearchHits(null);
      return;
    }
    setSearching(true);
    setError(null);
    try {
      const hits = await api.searchHistory(query.trim());
      setSearchHits(hits);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setSearching(false);
    }
  };

  const handleDeleteSession = async (id: string, title: string) => {
    if (!confirm(`Permanently delete session "${title}" and all its transcript & Q&A records?`)) return;
    try {
      await api.deleteHistorySession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (selectedDetail?.session.id === id) setSelectedDetail(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Delete failed');
    }
  };

  const handlePurgeTranscript = async (sessionId: string) => {
    if (!confirm('Delete raw transcript segments for this session while keeping Q&A notes?')) return;
    try {
      await api.purgeSessionTranscript(sessionId);
      await handleSelectSession(sessionId);
      await loadHistory();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to purge transcript');
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
              <History className="h-5 w-5 text-emerald-400" />
              Interview History
            </h1>
            <p className="text-xs text-zinc-400">
              Review saved live sessions, search past questions, export notes, or delete transcripts.
            </p>
          </div>
        </div>

        <Link
          href="/settings"
          className="text-xs px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-emerald-400 transition-colors"
        >
          Manage Retention Policy
        </Link>
      </div>

      {/* Search Bar */}
      <form onSubmit={handleSearch} className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="h-4 w-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search past questions or answers across all interview sessions..."
            className="w-full pl-9 pr-3 py-2 text-xs bg-zinc-900/60 border border-zinc-800 rounded-lg text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-emerald-500"
          />
        </div>
        <button
          type="submit"
          disabled={searching}
          className="px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-medium text-xs"
        >
          {searching ? 'Searching...' : 'Search'}
        </button>
        {searchHits !== null && (
          <button
            type="button"
            onClick={() => {
              setQuery('');
              setSearchHits(null);
            }}
            className="px-3 py-2 text-xs text-zinc-400 hover:text-zinc-200"
          >
            Clear
          </button>
        )}
      </form>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-red-950/50 border border-red-800/50 text-xs text-red-300">
          <AlertCircle className="h-4 w-4 text-red-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Search Results */}
      {searchHits !== null && (
        <div className="p-4 rounded-xl border border-emerald-900/40 bg-emerald-950/10 space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
            Matching Past Questions ({searchHits.length})
          </h2>
          {searchHits.length === 0 ? (
            <p className="text-xs text-zinc-400">No matching questions found for &quot;{query}&quot;.</p>
          ) : (
            <div className="space-y-2">
              {searchHits.map((hit) => (
                <div
                  key={hit.question_id}
                  className="p-3 rounded-lg bg-zinc-950/80 border border-zinc-800 space-y-1.5"
                >
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <button
                      onClick={() => handleSelectSession(hit.session_id)}
                      className="text-emerald-400 hover:underline font-semibold"
                    >
                      {hit.session_title} ({hit.session_type})
                    </button>
                    <span className="text-zinc-500">{new Date(hit.detected_at).toLocaleString()}</span>
                  </div>
                  <p className="text-xs font-semibold text-zinc-100">{hit.question_text}</p>
                  {hit.latest_answer && (
                    <p className="text-xs text-zinc-400 line-clamp-2">{hit.latest_answer}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Master-Detail Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Session List */}
        <div className="lg:col-span-5 space-y-2">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
            Saved Sessions ({sessions.length})
          </h2>

          {loading ? (
            <div className="p-8 text-center text-xs text-zinc-500 border border-zinc-800 rounded-xl">
              Loading sessions...
            </div>
          ) : sessions.length === 0 ? (
            <div className="p-10 text-center border border-dashed border-zinc-800 rounded-xl text-xs text-zinc-500">
              No saved interview sessions yet.
            </div>
          ) : (
            <div className="space-y-2 max-h-[65vh] overflow-y-auto pr-1">
              {sessions.map((s) => {
                const isSelected = selectedDetail?.session.id === s.id;
                return (
                  <div
                    key={s.id}
                    onClick={() => handleSelectSession(s.id)}
                    className={`p-3.5 rounded-xl border cursor-pointer transition-all space-y-1.5 ${
                      isSelected
                        ? 'border-emerald-500 bg-emerald-950/15'
                        : 'border-zinc-800 bg-zinc-900/30 hover:border-zinc-700'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-sm font-semibold text-zinc-100 leading-snug">{s.title}</span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteSession(s.id, s.title);
                        }}
                        className="p-1 text-zinc-500 hover:text-red-400 rounded"
                        title="Delete Session"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 text-[10px] font-mono text-zinc-400">
                      <span className="uppercase px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300">{s.type}</span>
                      <span>{s.question_count} Q</span>
                      <span>•</span>
                      <span>{s.answer_count} A</span>
                      <span>•</span>
                      <span>{s.transcript_count} lines</span>
                    </div>
                    <div className="flex items-center gap-2 text-[11px] text-zinc-500">
                      <Clock className="h-3 w-3" />
                      <span>{new Date(s.created_at).toLocaleString()}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Session Detail Viewer */}
        <div className="lg:col-span-7">
          {!selectedDetail ? (
            <div className="h-full min-h-[320px] flex flex-col items-center justify-center p-10 border border-dashed border-zinc-800 rounded-xl text-center space-y-2 text-zinc-500">
              <FileText className="h-8 w-8 text-zinc-700" />
              <p className="text-xs font-medium text-zinc-400">Select a session to inspect notes</p>
              <p className="text-[11px] text-zinc-600">
                Review detected questions, AI answers, full transcripts, and export to Markdown or JSON.
              </p>
            </div>
          ) : (
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 overflow-hidden flex flex-col">
              {/* Detail Header */}
              <div className="p-4 border-b border-zinc-800 bg-zinc-900/60 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-zinc-100">{selectedDetail.session.title}</h3>
                  <p className="text-[11px] text-zinc-400">
                    {new Date(selectedDetail.session.created_at).toLocaleString()} • Duration:{' '}
                    {selectedDetail.session.duration_seconds
                      ? `${Math.round(selectedDetail.session.duration_seconds / 60)}m`
                      : 'N/A'}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-1.5">
                  <a
                    href={api.getHistoryExportUrl(selectedDetail.session.id, 'markdown')}
                    download
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 text-xs"
                  >
                    <Download className="h-3 w-3" />
                    <span>Markdown</span>
                  </a>
                  <a
                    href={api.getHistoryExportUrl(selectedDetail.session.id, 'json')}
                    download
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 text-xs"
                  >
                    <Download className="h-3 w-3" />
                    <span>JSON</span>
                  </a>
                  <Link
                    href={`/session/${selectedDetail.session.id}`}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs"
                  >
                    <ExternalLink className="h-3 w-3" />
                    <span>Open</span>
                  </Link>
                </div>
              </div>

              {/* Tabs */}
              <div className="px-4 pt-3 border-b border-zinc-800 flex items-center justify-between">
                <div className="flex items-center gap-4 text-xs">
                  <button
                    onClick={() => setActiveTab('qa')}
                    className={`pb-2.5 border-b-2 font-medium transition-colors ${
                      activeTab === 'qa'
                        ? 'border-emerald-400 text-emerald-400'
                        : 'border-transparent text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    Questions & Answers ({selectedDetail.qa_pairs.length})
                  </button>
                  <button
                    onClick={() => setActiveTab('transcript')}
                    className={`pb-2.5 border-b-2 font-medium transition-colors ${
                      activeTab === 'transcript'
                        ? 'border-emerald-400 text-emerald-400'
                        : 'border-transparent text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    Transcript ({selectedDetail.transcript.length})
                  </button>
                </div>

                {activeTab === 'transcript' && selectedDetail.transcript.length > 0 && (
                  <button
                    onClick={() => handlePurgeTranscript(selectedDetail.session.id)}
                    className="mb-2 inline-flex items-center gap-1 text-[11px] text-amber-400 hover:text-amber-300"
                  >
                    <Eraser className="h-3 w-3" />
                    <span>Delete Transcript Only</span>
                  </button>
                )}
              </div>

              {/* Body */}
              <div className="p-4 space-y-3 max-h-[55vh] overflow-y-auto">
                {activeTab === 'qa' ? (
                  selectedDetail.qa_pairs.length === 0 ? (
                    <p className="text-xs text-zinc-500 text-center py-6">No detected questions in this session.</p>
                  ) : (
                    selectedDetail.qa_pairs.map((qa, idx) => (
                      <div key={qa.question_id} className="p-4 rounded-lg bg-zinc-950/70 border border-zinc-800 space-y-2">
                        <div className="flex items-center justify-between text-[10px] font-mono text-zinc-500">
                          <span className="uppercase text-emerald-400">
                            Q{idx + 1} • {qa.question_type}
                          </span>
                          <span>{new Date(qa.detected_at).toLocaleTimeString()}</span>
                        </div>
                        <p className="text-xs font-semibold text-zinc-100">{qa.question_text}</p>
                        {qa.answers.length > 0 ? (
                          <div className="pt-2 border-t border-zinc-800/70 space-y-1">
                            <p className="text-xs text-zinc-300 whitespace-pre-wrap leading-relaxed">
                              {qa.answers[qa.answers.length - 1].answer_text}
                            </p>
                            <p className="text-[10px] font-mono text-zinc-500">
                              Style: {qa.answers[qa.answers.length - 1].style} • Model: {qa.answers[qa.answers.length - 1].model_used}
                            </p>
                          </div>
                        ) : (
                          <p className="text-[11px] text-zinc-500 italic">No generated answer saved.</p>
                        )}
                      </div>
                    ))
                  )
                ) : selectedDetail.transcript.length === 0 ? (
                  <p className="text-xs text-zinc-500 text-center py-6">No transcript segments stored.</p>
                ) : (
                  selectedDetail.transcript.map((seg) => (
                    <div key={seg.id} className="p-3 rounded-lg bg-zinc-950/60 border border-zinc-800 text-xs">
                      <div className="flex items-center justify-between text-[10px] font-mono text-zinc-500 mb-1">
                        <span className="font-semibold text-zinc-300 uppercase flex items-center gap-1">
                          <MessageSquare className="h-3 w-3" />
                          {seg.speaker_label}
                        </span>
                        <span>{new Date(seg.timestamp).toLocaleTimeString()}</span>
                      </div>
                      <p className="text-zinc-200">{seg.text}</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
