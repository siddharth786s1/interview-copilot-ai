'use client';

import React, { useEffect, useState, useRef, useCallback } from 'react';
import Link from 'next/link';
import {
  GraduationCap,
  ArrowLeft,
  Play,
  Send,
  Mic,
  MicOff,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
  Sparkles,
  Trash2,
  ArrowRight,
  StopCircle,
  ShieldCheck,
} from 'lucide-react';
import { api } from '@/services/api';
import { useAudioCapture } from '@/hooks/useAudioCapture';
import {
  MockPerformanceSummary,
  MockSessionDetail,
  MockSessionSummary,
} from '@/types';

const MOCK_TOPICS = [
  'Application Security',
  'SAP Security',
  'Oracle Fusion HCM / OTBI',
  'Python & Backend',
  'System Design',
  'SQL & Databases',
  'HR & Behavioral',
];

export default function MockInterviewPage() {
  const [topic, setTopic] = useState(MOCK_TOPICS[0]);
  const [customTopic, setCustomTopic] = useState('');
  const [activeDetail, setActiveDetail] = useState<MockSessionDetail | null>(null);
  const [pastSessions, setPastSessions] = useState<MockSessionSummary[]>([]);
  const [performance, setPerformance] = useState<MockPerformanceSummary | null>(null);

  const [answerDraft, setAnswerDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Spoken answer PCM accumulator
  const pcmChunksRef = useRef<Uint8Array[]>([]);
  const { micStatus, micLevel, startMic, stopMic } = useAudioCapture({
    onChunk: (_source, chunk) => {
      // Strip 1-byte source header (0x01) to keep raw 16kHz 16-bit mono PCM
      const view = new Uint8Array(chunk);
      if (view.byteLength > 1) {
        pcmChunksRef.current.push(view.slice(1));
      }
    },
  });

  const loadSidebar = useCallback(async () => {
    try {
      const [sessions, perf] = await Promise.all([
        api.listMockSessions(),
        api.getMockPerformance(),
      ]);
      setPastSessions(sessions);
      setPerformance(perf);
    } catch (err) {
      console.error(err);
    }
  }, []);

  useEffect(() => {
    loadSidebar();
  }, [loadSidebar]);

  const handleStartMock = async () => {
    const chosenTopic = customTopic.trim() || topic;
    setBusy(true);
    setError(null);
    setAnswerDraft('');
    try {
      const detail = await api.createMockSession(chosenTopic);
      setActiveDetail(detail);
      await loadSidebar();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to start mock interview');
    } finally {
      setBusy(false);
    }
  };

  const handleToggleSpokenAnswer = async () => {
    if (micStatus === 'recording') {
      stopMic();
      const chunks = pcmChunksRef.current;
      pcmChunksRef.current = [];
      const totalLen = chunks.reduce((acc, c) => acc + c.byteLength, 0);
      if (totalLen < 3200) return;

      const merged = new Uint8Array(totalLen);
      let offset = 0;
      for (const c of chunks) {
        merged.set(c, offset);
        offset += c.byteLength;
      }

      setTranscribing(true);
      setError(null);
      try {
        const res = await api.transcribeMockAudio(merged.buffer);
        if (res.text) {
          setAnswerDraft((prev) => (prev ? `${prev} ${res.text}` : res.text));
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to transcribe spoken answer');
      } finally {
        setTranscribing(false);
      }
    } else {
      pcmChunksRef.current = [];
      await startMic();
    }
  };

  const currentExchange =
    activeDetail && activeDetail.exchanges.length > 0
      ? activeDetail.exchanges[activeDetail.exchanges.length - 1]
      : null;

  const handleSubmitAnswer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeDetail || !currentExchange || !answerDraft.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api.submitMockAnswer(
        activeDetail.session.id,
        currentExchange.id,
        answerDraft.trim()
      );
      setActiveDetail((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          exchanges: prev.exchanges.map((ex) => (ex.id === updated.id ? updated : ex)),
        };
      });
      await loadSidebar();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Evaluation failed');
    } finally {
      setBusy(false);
    }
  };

  const handleNextQuestion = async () => {
    if (!activeDetail) return;
    setBusy(true);
    setError(null);
    setAnswerDraft('');
    try {
      const nextEx = await api.nextMockQuestion(activeDetail.session.id);
      setActiveDetail((prev) =>
        prev ? { ...prev, exchanges: [...prev.exchanges, nextEx] } : prev
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to generate next question');
    } finally {
      setBusy(false);
    }
  };

  const handleEndMock = async () => {
    if (!activeDetail) return;
    stopMic();
    await api.endMockSession(activeDetail.session.id);
    setActiveDetail(null);
    await loadSidebar();
  };

  const handleDeleteMock = async (id: string) => {
    if (!confirm('Delete this mock interview session?')) return;
    await api.deleteMockSession(id);
    if (activeDetail?.session.id === id) setActiveDetail(null);
    await loadSidebar();
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
              <GraduationCap className="h-5 w-5 text-emerald-400" />
              Mock Interview Practice
            </h1>
            <p className="text-xs text-zinc-400">
              One question at a time • Typed or spoken answers • Structured evaluation & missing concepts
            </p>
          </div>
        </div>

        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-[11px] text-zinc-400">
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
          <span>Isolated from Live Interview History</span>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-red-950/50 border border-red-800/50 text-xs text-red-300">
          <AlertCircle className="h-4 w-4 text-red-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Main Practice Area */}
        <div className="lg:col-span-8 space-y-5">
          {!activeDetail ? (
            <div className="p-6 rounded-xl border border-zinc-800 bg-zinc-900/40 space-y-5">
              <div>
                <h2 className="text-sm font-semibold text-zinc-100">Start a New Mock Interview</h2>
                <p className="text-xs text-zinc-400 mt-0.5">
                  Choose a focus topic or enter a custom one. You will be asked one question at a time.
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                {MOCK_TOPICS.map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => {
                      setTopic(t);
                      setCustomTopic('');
                    }}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                      topic === t && !customTopic
                        ? 'bg-emerald-500/15 border-emerald-500/50 text-emerald-300'
                        : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>

              <div>
                <label className="block text-xs text-zinc-400 mb-1">Or Custom Topic</label>
                <input
                  type="text"
                  value={customTopic}
                  onChange={(e) => setCustomTopic(e.target.value)}
                  placeholder="e.g. Kubernetes RBAC, OWASP API Top 10..."
                  className="w-full px-3 py-2 text-xs bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <button
                onClick={handleStartMock}
                disabled={busy}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-medium text-xs transition-colors disabled:opacity-50"
              >
                <Play className="h-3.5 w-3.5 fill-zinc-950" />
                <span>{busy ? 'Preparing Question...' : 'Start Mock Session'}</span>
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Active Session Banner */}
              <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/50 flex items-center justify-between">
                <div>
                  <span className="text-[10px] font-mono uppercase text-emerald-400">
                    Active Mock • Question {activeDetail.exchanges.length}
                  </span>
                  <h2 className="text-sm font-semibold text-zinc-100">{activeDetail.session.topic}</h2>
                </div>
                <button
                  onClick={handleEndMock}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-950/60 hover:bg-red-900/80 text-red-300 border border-red-800/60 text-xs"
                >
                  <StopCircle className="h-3.5 w-3.5" />
                  <span>End Mock</span>
                </button>
              </div>

              {/* Current Question Card */}
              {currentExchange && (
                <div className="p-5 rounded-xl border border-zinc-800 bg-zinc-900/40 space-y-4">
                  <div className="space-y-1">
                    <span className="text-[10px] font-mono uppercase text-zinc-400">Interviewer Question</span>
                    <p className="text-base font-semibold text-zinc-100">{currentExchange.question_text}</p>
                  </div>

                  {!currentExchange.evaluation ? (
                    <form onSubmit={handleSubmitAnswer} className="space-y-3">
                      <textarea
                        rows={5}
                        value={answerDraft}
                        onChange={(e) => setAnswerDraft(e.target.value)}
                        placeholder="Type your response here, or click 'Speak Answer' to dictate with your microphone..."
                        className="w-full p-3 text-xs bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500"
                      />

                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={handleToggleSpokenAnswer}
                            disabled={transcribing}
                            className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border text-xs font-medium transition-colors ${
                              micStatus === 'recording'
                                ? 'bg-red-950/60 border-red-800 text-red-300 animate-pulse'
                                : 'bg-zinc-900 border-zinc-700 text-zinc-300 hover:text-zinc-100'
                            }`}
                          >
                            {micStatus === 'recording' ? <MicOff className="h-3.5 w-3.5" /> : <Mic className="h-3.5 w-3.5" />}
                            <span>
                              {transcribing
                                ? 'Transcribing...'
                                : micStatus === 'recording'
                                ? 'Stop & Transcribe'
                                : 'Speak Answer'}
                            </span>
                          </button>
                          {micStatus === 'recording' && (
                            <div className="w-20 h-2 bg-zinc-950 border border-zinc-800 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-emerald-400 transition-all duration-75"
                                style={{ width: `${Math.max(8, micLevel * 100)}%` }}
                              />
                            </div>
                          )}
                        </div>

                        <button
                          type="submit"
                          disabled={busy || !answerDraft.trim()}
                          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-medium text-xs disabled:opacity-40"
                        >
                          <Send className="h-3.5 w-3.5" />
                          <span>{busy ? 'Evaluating...' : 'Submit Answer'}</span>
                        </button>
                      </div>
                    </form>
                  ) : (
                    <div className="space-y-4 pt-2 border-t border-zinc-800">
                      <div className="p-3 rounded-lg bg-zinc-950/60 border border-zinc-800 text-xs text-zinc-300">
                        <span className="block text-[10px] font-mono uppercase text-zinc-500 mb-1">Your Answer</span>
                        {currentExchange.user_answer}
                      </div>

                      {/* Score + Feedback */}
                      <div className="p-4 rounded-xl border border-emerald-900/40 bg-emerald-950/15 space-y-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                            <span className="text-xs font-semibold text-zinc-200">Evaluation & Coaching</span>
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
                              {currentExchange.evaluation.evaluation_mode}
                            </span>
                          </div>
                          <span className="text-sm font-bold font-mono text-emerald-400">
                            {currentExchange.evaluation.score} / 100
                          </span>
                        </div>

                        <p className="text-xs text-zinc-200 leading-relaxed">
                          {currentExchange.evaluation.feedback}
                        </p>

                        {currentExchange.evaluation.missing_concepts.length > 0 && (
                          <div className="space-y-1.5">
                            <span className="text-[10px] font-mono uppercase text-amber-400">
                              Missing Technical Concepts
                            </span>
                            <div className="flex flex-wrap gap-1.5">
                              {currentExchange.evaluation.missing_concepts.map((c) => (
                                <span
                                  key={c}
                                  className="px-2 py-0.5 rounded-full text-[11px] bg-amber-950/40 border border-amber-800/50 text-amber-300 font-mono"
                                >
                                  {c}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        <div className="p-3 rounded-lg bg-zinc-950/80 border border-zinc-800 space-y-1">
                          <span className="text-[10px] font-mono uppercase text-emerald-400 flex items-center gap-1">
                            <Sparkles className="h-3 w-3" />
                            Suggested Improved Answer
                          </span>
                          <p className="text-xs text-zinc-200 leading-relaxed whitespace-pre-wrap">
                            {currentExchange.evaluation.improved_answer}
                          </p>
                        </div>
                      </div>

                      <div className="flex justify-end">
                        <button
                          onClick={handleNextQuestion}
                          disabled={busy}
                          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-medium text-xs"
                        >
                          <span>{busy ? 'Loading...' : 'Next Question'}</span>
                          <ArrowRight className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Performance & Past Mock Sessions Sidebar */}
        <div className="lg:col-span-4 space-y-5">
          {/* Performance Card */}
          <div className="p-5 rounded-xl border border-zinc-800 bg-zinc-900/40 space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-emerald-400" />
              Performance Tracking
            </h2>

            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800">
                <span className="text-[10px] font-mono text-zinc-500">Avg Score</span>
                <p className="text-lg font-bold text-emerald-400 font-mono">
                  {performance?.overall_average_score != null ? `${performance.overall_average_score}%` : '—'}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800">
                <span className="text-[10px] font-mono text-zinc-500">Evaluated Qs</span>
                <p className="text-lg font-bold text-zinc-100 font-mono">
                  {performance?.total_evaluated ?? 0}
                </p>
              </div>
            </div>

            {performance && performance.by_topic.length > 0 && (
              <div className="space-y-1.5 pt-2 border-t border-zinc-800">
                <span className="text-[10px] font-mono uppercase text-zinc-500">Average by Topic</span>
                {performance.by_topic.map((t) => (
                  <div key={t.topic} className="flex items-center justify-between text-xs">
                    <span className="text-zinc-300 truncate">{t.topic}</span>
                    <span className="font-mono text-emerald-400">{t.average_score}%</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Past Mock Sessions */}
          <div className="p-5 rounded-xl border border-zinc-800 bg-zinc-900/30 space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
              Mock Sessions ({pastSessions.length})
            </h2>
            {pastSessions.length === 0 ? (
              <p className="text-xs text-zinc-500">No mock sessions yet.</p>
            ) : (
              <div className="space-y-2 max-h-72 overflow-y-auto">
                {pastSessions.map((s) => (
                  <div
                    key={s.id}
                    className="p-3 rounded-lg bg-zinc-950/60 border border-zinc-800 flex items-center justify-between gap-2"
                  >
                    <button
                      onClick={async () => {
                        const d = await api.getMockSession(s.id);
                        setActiveDetail(d);
                      }}
                      className="text-left min-w-0 flex-1"
                    >
                      <p className="text-xs font-semibold text-zinc-200 truncate hover:text-emerald-400">
                        {s.topic}
                      </p>
                      <p className="text-[10px] font-mono text-zinc-500">
                        {s.answered_count}/{s.question_count} answered
                        {s.average_score != null ? ` • ${s.average_score}%` : ''}
                      </p>
                    </button>
                    <button
                      onClick={() => handleDeleteMock(s.id)}
                      className="p-1 text-zinc-500 hover:text-red-400"
                      title="Delete Mock Session"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
