'use client';

import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Play,
  Pause,
  StopCircle,
  Sparkles,
  MessageSquare,
  Copy,
  Check,
  Send,
  HelpCircle,
  CheckCircle2,
  Clock,
  SlidersHorizontal,
  AlertCircle,
  RotateCw,
  Maximize2,
  AlertTriangle,
  Monitor,
  MonitorOff,
  Eye,
  ScanEye,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { api } from '@/services/api';
import { useAudioCapture } from '@/hooks/useAudioCapture';
import { useScreenReader } from '@/hooks/useScreenReader';
import { useSessionWebSocket } from '@/hooks/useSessionWebSocket';
import { StructuredAnswerView } from '@/components/StructuredAnswerView';
import { Session, TranscriptSegment, DetectedQuestion, GeneratedAnswer } from '@/types';

type AnswerStyle = 'short' | 'detailed' | 'practical' | 'stepbystep';

export default function SessionWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.id as string;

  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [language, setLanguage] = useState<string>('en');

  // Workspace items
  const [transcript, setTranscript] = useState<TranscriptSegment[]>([]);
  const [questions, setQuestions] = useState<DetectedQuestion[]>([]);
  const [activeQuestion, setActiveQuestion] = useState<DetectedQuestion | null>(null);
  const [selectedStyle, setSelectedStyle] = useState<AnswerStyle>('short');
  const [answersByQuestion, setAnswersByQuestion] = useState<Record<string, GeneratedAnswer>>({});
  const [streamingByQuestion, setStreamingByQuestion] = useState<
    Record<string, { text: string; style: string; needsCustomization: boolean }>
  >({});
  const [generatingQuestionId, setGeneratingQuestionId] = useState<string | null>(null);
  const [answerError, setAnswerError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [manualInput, setManualInput] = useState('');
  const [screenPrompt, setScreenPrompt] = useState('');
  const [screenStripOpen, setScreenStripOpen] = useState(true);

  const handleFinalTranscript = useCallback((seg: TranscriptSegment) => {
    setTranscript((prev) => {
      if (prev.some((existing) => existing.id === seg.id)) return prev;
      return [...prev, seg];
    });
  }, []);

  const handleQuestionDetected = useCallback((q: DetectedQuestion) => {
    setQuestions((prev) => {
      if (prev.some((existing) => existing.id === q.id)) return prev;
      return [...prev, q];
    });
    setActiveQuestion(q);
    setAnswerError(null);
  }, []);

  const handleAnswerStart = useCallback(
    ({ questionId, style, needsCustomization }: { questionId: string; style: string; needsCustomization: boolean }) => {
      setGeneratingQuestionId(questionId);
      setAnswerError(null);
      setStreamingByQuestion((prev) => ({
        ...prev,
        [questionId]: { text: '', style, needsCustomization },
      }));
    },
    []
  );

  const handleAnswerChunk = useCallback(({ questionId, text }: { questionId: string; text: string }) => {
    setStreamingByQuestion((prev) => {
      const current = prev[questionId] || { text: '', style: 'short', needsCustomization: false };
      return {
        ...prev,
        [questionId]: { ...current, text: current.text + text },
      };
    });
  }, []);

  const handleAnswerComplete = useCallback((answer: GeneratedAnswer) => {
    setAnswersByQuestion((prev) => ({ ...prev, [answer.question_id]: answer }));
    setStreamingByQuestion((prev) => {
      const next = { ...prev };
      delete next[answer.question_id];
      return next;
    });
    setGeneratingQuestionId((curr) => (curr === answer.question_id ? null : curr));
  }, []);

  const handleAnswerError = useCallback(
    ({ questionId, message }: { questionId?: string; code: string; message: string }) => {
      setAnswerError(message);
      if (questionId) {
        setStreamingByQuestion((prev) => {
          const next = { ...prev };
          delete next[questionId];
          return next;
        });
        setGeneratingQuestionId((curr) => (curr === questionId ? null : curr));
      } else {
        setGeneratingQuestionId(null);
      }
    },
    []
  );

  // Real-time WebSocket streaming (audio upstream + transcript/events downstream)
  const {
    wsStatus,
    audioWsStatus,
    wsError,
    lastLatencyMs,
    partialSegments,
    sendAudioChunk,
    sendControl,
    sendLanguageConfig,
  } = useSessionWebSocket({
    sessionId,
    enabled: !!session && session.status !== 'ended',
    initialLanguage: language,
    onFinalTranscript: handleFinalTranscript,
    onQuestionDetected: handleQuestionDetected,
    onAnswerStart: handleAnswerStart,
    onAnswerChunk: handleAnswerChunk,
    onAnswerComplete: handleAnswerComplete,
    onAnswerError: handleAnswerError,
  });

  // Real browser audio capture engine wired directly to /ws/audio/{sessionId}
  const {
    micStatus,
    tabStatus,
    micLevel,
    tabLevel,
    micError,
    tabError,
    startMic,
    stopMic,
    startTab,
    stopTab,
    stopAll,
  } = useAudioCapture({
    onChunk: (_source, chunk) => {
      sendAudioChunk(chunk);
    },
  });

  // Permitted visual screen reader / Auto-Watch (explicit user getDisplayMedia consent)
  const {
    screenStatus,
    screenError,
    autoWatch,
    setAutoWatch,
    isAnalyzing: isAnalyzingScreen,
    lastPreviewUrl,
    lastStatusNote,
    startScreenShare,
    stopScreenShare,
    analyzeNow,
  } = useScreenReader({
    sessionId,
    enabled: !!session && session.status !== 'ended',
    style: selectedStyle,
    onQuestionDetected: handleQuestionDetected,
    onAnswerComplete: handleAnswerComplete,
  });

  const transcriptEndRef = useRef<HTMLDivElement>(null);

  const loadSession = useCallback(async () => {
    if (!sessionId) return;
    try {
      const [s, t, q, answers, cfg] = await Promise.all([
        api.getSession(sessionId),
        api.getSessionTranscript(sessionId).catch(() => []),
        api.getSessionQuestions(sessionId).catch(() => []),
        api.getSessionAnswers(sessionId).catch(() => []),
        api.getSettings().catch(() => null),
      ]);
      setSession(s);
      setTranscript(t);
      setQuestions(q);
      const ansMap: Record<string, GeneratedAnswer> = {};
      for (const a of answers) {
        ansMap[a.question_id] = a;
      }
      setAnswersByQuestion(ansMap);
      if (cfg) {
        setSelectedStyle(cfg.default_answer_style);
        setLanguage(cfg.language || 'en');
      }
      if (q.length > 0) {
        setActiveQuestion(q[q.length - 1]);
      }
      if (s.duration_seconds) {
        setElapsedSeconds(s.duration_seconds);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    loadSession();
  }, [loadSession]);

  // Elapsed time counter
  useEffect(() => {
    if (!session || session.status !== 'active') return;
    const interval = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [session]);

  // Scroll transcript to bottom on new finalized or partial segments
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript, partialSegments]);

  // Session status controls
  const handleStatusChange = async (newStatus: 'active' | 'paused' | 'ended') => {
    if (!session) return;
    if (newStatus === 'ended' && !confirm('Are you sure you want to end this interview session?')) {
      return;
    }
    if (newStatus === 'ended') {
      sendControl('end');
      stopAll();
      stopScreenShare();
    } else if (newStatus === 'paused') {
      sendControl('pause');
    } else if (newStatus === 'active') {
      sendControl('resume');
    }
    try {
      const updated = await api.updateSession(session.id, { status: newStatus });
      setSession(updated);
      if (newStatus === 'ended') {
        router.push('/');
      }
    } catch (err: unknown) {
      alert(`Status update failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const handleLanguageChange = (newLang: string) => {
    setLanguage(newLang);
    sendLanguageConfig(newLang);
  };

  const requestAnswerGeneration = async (
    question: DetectedQuestion,
    opts: { style?: AnswerStyle; expand?: boolean } = {}
  ) => {
    const targetStyle = opts.style || selectedStyle;
    setGeneratingQuestionId(question.id);
    setAnswerError(null);
    try {
      const generated = await api.generateAnswer(sessionId, question.id, {
        style: targetStyle,
        expand: Boolean(opts.expand),
      });
      handleAnswerComplete(generated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Answer generation failed';
      setAnswerError(msg);
      setGeneratingQuestionId((curr) => (curr === question.id ? null : curr));
    }
  };

  const handleStyleChange = (style: AnswerStyle) => {
    setSelectedStyle(style);
    if (activeQuestion && generatingQuestionId !== activeQuestion.id) {
      requestAnswerGeneration(activeQuestion, { style });
    }
  };

  // Manual Question Submission fallback — persists via real backend API & auto-streams answer
  const handleManualQuestionSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = manualInput.trim();
    if (!text) return;

    setManualInput('');
    setAnswerError(null);
    try {
      const savedQuestion = await api.createManualQuestion(sessionId, text, selectedStyle);
      handleQuestionDetected(savedQuestion);
    } catch (err: unknown) {
      setAnswerError(err instanceof Error ? err.message : 'Failed to submit question');
    }
  };

  const handleScreenPromptSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (screenStatus !== 'sharing' || isAnalyzingScreen) return;
    const prompt = screenPrompt.trim();
    setScreenPrompt('');
    setAnswerError(null);
    await analyzeNow(prompt || undefined, selectedStyle);
  };

  const activeAnswer = activeQuestion ? answersByQuestion[activeQuestion.id] || null : null;
  const activeStream = activeQuestion ? streamingByQuestion[activeQuestion.id] || null : null;
  const isGeneratingActive = Boolean(activeQuestion && generatingQuestionId === activeQuestion.id);

  const handleCopyAnswer = () => {
    const textToCopy = activeStream?.text || activeAnswer?.answer_text;
    if (!textToCopy) return;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formatTimer = (totalSec: number) => {
    const mins = Math.floor(totalSec / 60);
    const secs = totalSec % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  if (loading) {
    return (
      <div className="h-[calc(100vh-4rem)] flex items-center justify-center text-zinc-500 text-sm">
        Loading interview workspace...
      </div>
    );
  }

  if (!session) {
    return (
      <div className="container mx-auto px-6 py-12 space-y-4">
        <p className="text-sm text-red-400">Session not found.</p>
        <Link href="/" className="text-xs text-emerald-400 underline">Return to Dashboard</Link>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col bg-zinc-950 select-none">
      {/* Top Workspace Control Bar */}
      <div className="h-14 border-b border-zinc-800 px-6 flex items-center justify-between bg-zinc-900/60 backdrop-blur shrink-0">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            title="Return to Dashboard"
            className="p-1.5 rounded-lg bg-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>

          <div className="flex items-center gap-2.5">
            <h1 className="font-semibold text-sm text-zinc-100 max-w-sm truncate">{session.title}</h1>
            <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700">
              {session.type}
            </span>
            <div className={`flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono border ${
              session.status === 'active'
                ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/60'
                : session.status === 'paused'
                ? 'bg-amber-950/40 text-amber-400 border-amber-800/60'
                : 'bg-zinc-900 text-zinc-400 border-zinc-800'
            }`}>
              <span className={`h-1.5 w-1.5 rounded-full ${
                session.status === 'active' ? 'bg-emerald-400 animate-pulse' : session.status === 'paused' ? 'bg-amber-400' : 'bg-zinc-500'
              }`} />
              <span className="capitalize">{session.status}</span>
            </div>
          </div>
        </div>

        {/* Center Timer */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 font-mono text-xs">
          <Clock className="h-3.5 w-3.5 text-zinc-500" />
          <span>{formatTimer(elapsedSeconds)}</span>
        </div>

        {/* Session Action Controls */}
        <div className="flex items-center gap-2">
          {session.status === 'created' && (
            <button
              onClick={() => handleStatusChange('active')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-medium text-xs transition-all shadow-sm shadow-emerald-500/20 active:scale-95"
            >
              <Play className="h-3.5 w-3.5 fill-zinc-950" />
              <span>Start Session</span>
            </button>
          )}

          {session.status === 'active' && (
            <button
              onClick={() => handleStatusChange('paused')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 text-xs font-medium transition-colors"
            >
              <Pause className="h-3.5 w-3.5" />
              <span>Pause</span>
            </button>
          )}

          {session.status === 'paused' && (
            <button
              onClick={() => handleStatusChange('active')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-medium text-xs transition-all shadow-sm shadow-emerald-500/20 active:scale-95"
            >
              <Play className="h-3.5 w-3.5 fill-zinc-950" />
              <span>Resume</span>
            </button>
          )}

          {session.status !== 'ended' && (
            <button
              onClick={() => handleStatusChange('ended')}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-950/60 hover:bg-red-900/80 text-red-300 border border-red-800/60 text-xs font-medium transition-colors"
            >
              <StopCircle className="h-3.5 w-3.5" />
              <span>End Session</span>
            </button>
          )}
        </div>
      </div>

      {/* Audio Capture Status Ribbon */}
      <div className="border-b border-zinc-800/80 px-6 py-2 bg-zinc-950 flex flex-wrap items-center justify-between gap-3 text-xs shrink-0">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-zinc-500 font-medium text-[11px]">Audio Sources:</span>

          {/* Microphone Toggle & Meter */}
          <div className="flex items-center gap-2">
            <button
              onClick={micStatus === 'recording' ? stopMic : startMic}
              disabled={session.status === 'ended'}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md border text-xs font-medium transition-colors disabled:opacity-50 ${
                micStatus === 'recording'
                  ? 'bg-emerald-950/50 border-emerald-800 text-emerald-400'
                  : micStatus === 'requesting'
                  ? 'bg-blue-950/40 border-blue-800 text-blue-400 animate-pulse'
                  : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {micStatus === 'recording' ? <Mic className="h-3.5 w-3.5 text-emerald-400 animate-pulse" /> : <MicOff className="h-3.5 w-3.5" />}
              <span>{micStatus === 'recording' ? 'Mic Active' : 'Start Mic'}</span>
            </button>

            {micStatus === 'recording' && (
              <div className="w-16 h-2 bg-zinc-900 border border-zinc-800 rounded-full overflow-hidden p-0.5" title="Mic Volume">
                <div
                  className="h-full bg-emerald-400 rounded-full transition-all duration-75"
                  style={{ width: `${Math.max(5, micLevel * 100)}%` }}
                />
              </div>
            )}
          </div>

          {/* Tab Audio Toggle & Meter */}
          <div className="flex items-center gap-2">
            <button
              onClick={tabStatus === 'recording' ? stopTab : startTab}
              disabled={session.status === 'ended'}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md border text-xs font-medium transition-colors disabled:opacity-50 ${
                tabStatus === 'recording'
                  ? 'bg-purple-950/50 border-purple-800 text-purple-400'
                  : tabStatus === 'requesting'
                  ? 'bg-blue-950/40 border-blue-800 text-blue-400 animate-pulse'
                  : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {tabStatus === 'recording' ? <Volume2 className="h-3.5 w-3.5 text-purple-400 animate-pulse" /> : <VolumeX className="h-3.5 w-3.5" />}
              <span>{tabStatus === 'recording' ? 'Tab Active' : 'Share Tab Audio'}</span>
            </button>

            {tabStatus === 'recording' && (
              <div className="w-16 h-2 bg-zinc-900 border border-zinc-800 rounded-full overflow-hidden p-0.5" title="Tab Volume">
                <div
                  className="h-full bg-purple-400 rounded-full transition-all duration-75"
                  style={{ width: `${Math.max(5, tabLevel * 100)}%` }}
                />
              </div>
            )}
          </div>

          <span className="text-zinc-700">|</span>

          {/* Permitted Screen Reader Controls */}
          <div className="flex items-center gap-2">
            <button
              onClick={screenStatus === 'sharing' ? stopScreenShare : startScreenShare}
              disabled={session.status === 'ended'}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md border text-xs font-medium transition-colors disabled:opacity-50 ${
                screenStatus === 'sharing'
                  ? 'bg-cyan-950/50 border-cyan-700 text-cyan-300'
                  : screenStatus === 'requesting'
                  ? 'bg-blue-950/40 border-blue-800 text-blue-400 animate-pulse'
                  : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200'
              }`}
              title="Explicitly share a screen, window, or tab so Gemini can read visible code, diagrams, or questions"
            >
              {screenStatus === 'sharing' ? (
                <Monitor className="h-3.5 w-3.5 text-cyan-400 animate-pulse" />
              ) : (
                <MonitorOff className="h-3.5 w-3.5" />
              )}
              <span>{screenStatus === 'sharing' ? 'Screen Active' : 'Share Screen'}</span>
            </button>

            {screenStatus === 'sharing' && (
              <>
                <button
                  onClick={() => analyzeNow(undefined, selectedStyle)}
                  disabled={isAnalyzingScreen || session.status === 'ended'}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-cyan-800/70 bg-cyan-950/40 hover:bg-cyan-900/50 text-cyan-200 text-xs font-medium transition-colors disabled:opacity-50"
                  title="Capture the shared screen right now and generate a structured answer"
                >
                  <ScanEye className={`h-3.5 w-3.5 ${isAnalyzingScreen ? 'animate-spin text-emerald-400' : 'text-cyan-400'}`} />
                  <span>{isAnalyzingScreen ? 'Reading...' : 'Analyze Screen'}</span>
                </button>

                <button
                  onClick={() => setAutoWatch((prev) => !prev)}
                  disabled={session.status === 'ended'}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs font-medium transition-colors disabled:opacity-50 ${
                    autoWatch
                      ? 'bg-emerald-950/50 border-emerald-700 text-emerald-300'
                      : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200'
                  }`}
                  title="Automatically scan screen changes every 8s and reply only when actionable interview content appears"
                >
                  <Eye className={`h-3.5 w-3.5 ${autoWatch ? 'text-emerald-400 animate-pulse' : ''}`} />
                  <span>{autoWatch ? 'Auto-Watch: ON' : 'Auto-Watch'}</span>
                </button>
              </>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-[11px] text-zinc-500">
          {/* Language Selector */}
          <div className="flex items-center gap-1.5">
            <span className="text-zinc-500">Lang:</span>
            <select
              value={language}
              onChange={(e) => handleLanguageChange(e.target.value)}
              className="bg-zinc-900 border border-zinc-800 rounded px-2 py-0.5 text-[11px] text-zinc-300 focus:outline-none focus:border-emerald-500"
            >
              <option value="en">English (en)</option>
              <option value="auto">Auto-detect</option>
              <option value="es">Spanish (es)</option>
              <option value="fr">French (fr)</option>
              <option value="de">German (de)</option>
              <option value="hi">Hindi (hi)</option>
            </select>
          </div>

          <span>•</span>

          {/* WebSocket Connection Indicator */}
          <span
            className={`inline-flex items-center gap-1.5 font-mono px-2 py-0.5 rounded border text-[10px] ${
              wsStatus === 'connected' && audioWsStatus === 'connected'
                ? 'bg-emerald-950/40 border-emerald-800/60 text-emerald-400'
                : wsStatus === 'reconnecting' || audioWsStatus === 'reconnecting'
                ? 'bg-amber-950/40 border-amber-800/60 text-amber-400 animate-pulse'
                : 'bg-zinc-900 border-zinc-800 text-zinc-500'
            }`}
            title={`Session WS: ${wsStatus}, Audio WS: ${audioWsStatus}`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                wsStatus === 'connected' && audioWsStatus === 'connected'
                  ? 'bg-emerald-400'
                  : wsStatus === 'reconnecting' || audioWsStatus === 'reconnecting'
                  ? 'bg-amber-400'
                  : 'bg-zinc-500'
              }`}
            />
            <span>
              {wsStatus === 'connected' && audioWsStatus === 'connected'
                ? 'STT Stream Connected'
                : wsStatus === 'reconnecting' || audioWsStatus === 'reconnecting'
                ? 'Reconnecting WS...'
                : 'WS Disconnected'}
            </span>
          </span>

          <span>•</span>

          <Link
            href="/audio-test"
            className="flex items-center gap-1 text-zinc-400 hover:text-emerald-400 transition-colors"
          >
            <SlidersHorizontal className="h-3 w-3" />
            <span>Diagnostics</span>
          </Link>
        </div>
      </div>

      {/* Permission / Track / WebSocket Error Banners */}
      {(micError || tabError || screenError || wsError) && (
        <div className="px-6 py-2 bg-red-950/60 border-b border-red-800/40 text-xs text-red-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />
            <span>
              {micError && `Microphone: ${micError}. `}
              {tabError && `Tab Audio: ${tabError}. `}
              {screenError && `Screen Reader: ${screenError}. `}
              {wsError && `Stream: ${wsError}`}
            </span>
          </div>
          <Link href="/audio-test" className="underline font-medium hover:text-red-200">
            Run Diagnostics
          </Link>
        </div>
      )}

      {/* Main Two-Panel Workspace */}
      <div className="flex-1 grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-zinc-800 overflow-hidden">
        {/* ======================================================== */}
        {/* LEFT PANEL: Live Transcript & Detected Questions          */}
        {/* ======================================================== */}
        <div className="flex flex-col h-full bg-zinc-950/30 overflow-hidden">
          {/* Panel Tab Header */}
          <div className="p-3 border-b border-zinc-800/80 bg-zinc-900/40 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-zinc-400" />
              <span className="text-xs font-semibold text-zinc-200">Live Transcript & Questions</span>
            </div>
            <div className="flex items-center gap-3 text-[10px] font-mono text-zinc-500">
              {lastLatencyMs !== null && (
                <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-emerald-400" title="Last STT latency">
                  STT: {lastLatencyMs}ms
                </span>
              )}
              <span>
                {questions.length} question{questions.length === 1 ? '' : 's'} detected
              </span>
            </div>
          </div>

          {/* Collapsible Live Screen Reader Strip (visible only while user is actively sharing screen) */}
          {screenStatus === 'sharing' && (
            <div className="border-b border-cyan-900/50 bg-cyan-950/20 px-3 py-2 shrink-0 space-y-2">
              <div className="flex items-center justify-between gap-2 text-[11px]">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-cyan-950/80 border border-cyan-800/70 text-cyan-300 font-mono text-[10px] shrink-0">
                    <Monitor className="h-3 w-3" />
                    SCREEN WATCH
                  </span>
                  <span className="text-zinc-400 truncate">
                    {lastStatusNote || 'Visible screen context is active for voice & visual answers.'}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setScreenStripOpen((prev) => !prev)}
                  className="text-zinc-400 hover:text-zinc-200 p-0.5 shrink-0"
                  title={screenStripOpen ? 'Collapse screen preview' : 'Expand screen preview'}
                >
                  {screenStripOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                </button>
              </div>

              {screenStripOpen && (
                <div className="flex items-center gap-3">
                  {lastPreviewUrl && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={lastPreviewUrl}
                      alt="Shared screen preview"
                      className="h-14 w-24 object-cover rounded border border-cyan-800/60 bg-zinc-950 shrink-0"
                    />
                  )}
                  <form onSubmit={handleScreenPromptSubmit} className="flex-1 flex items-center gap-1.5">
                    <input
                      type="text"
                      value={screenPrompt}
                      onChange={(e) => setScreenPrompt(e.target.value)}
                      placeholder="Ask about what's on screen (optional)..."
                      className="flex-1 px-2.5 py-1.5 bg-zinc-950 border border-zinc-800 rounded-md text-xs text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-cyan-500"
                    />
                    <button
                      type="submit"
                      disabled={isAnalyzingScreen}
                      className="px-2.5 py-1.5 rounded-md bg-cyan-500 hover:bg-cyan-400 text-zinc-950 font-medium text-xs transition-colors disabled:opacity-50 shrink-0"
                    >
                      {isAnalyzingScreen ? 'Reading...' : 'Ask Screen'}
                    </button>
                  </form>
                </div>
              )}
            </div>
          )}

          {/* Transcript Scroll Area */}
          <div className="flex-1 p-4 overflow-y-auto space-y-3 font-sans text-xs">
            {transcript.length === 0 && !partialSegments.mic && !partialSegments.tab && questions.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-3 text-zinc-600">
                <Mic className="h-8 w-8 text-zinc-700" />
                <div>
                  <p className="text-xs font-medium text-zinc-400">Waiting for live audio input</p>
                  <p className="text-[11px] text-zinc-600 max-w-xs mt-1">
                    Click &quot;Start Mic&quot; or &quot;Share Tab Audio&quot; above. Spoken words will stream here in real time with partial and finalized segments.
                  </p>
                </div>
                <p className="text-[10px] text-zinc-600 max-w-xs">
                  Speaker labels (Interviewer / Me) are best-effort based on audio capture source.
                </p>
              </div>
            ) : (
              <>
                {/* Finalized Transcript Segments */}
                {transcript.map((seg) => (
                  <div
                    key={seg.id}
                    className={`p-3 rounded-lg border ${
                      seg.source === 'tab'
                        ? 'bg-purple-950/20 border-purple-900/40 text-purple-100'
                        : 'bg-zinc-900/50 border-zinc-800 text-zinc-100'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1 text-[10px] text-zinc-500 font-mono">
                      <div className="flex items-center gap-1.5">
                        <span className={`font-semibold uppercase ${seg.source === 'tab' ? 'text-purple-300' : 'text-emerald-400'}`}>
                          {seg.speaker_label || (seg.source === 'tab' ? 'Interviewer' : 'Me')}
                        </span>
                        <span className="text-[9px] text-zinc-600">(final)</span>
                      </div>
                      <span>{new Date(seg.timestamp).toLocaleTimeString()}</span>
                    </div>
                    <p className="text-xs leading-relaxed">{seg.text}</p>
                  </div>
                ))}

                {/* Live Partial Transcript Segments (distinctly styled) */}
                {(['tab', 'mic'] as const).map((src) => {
                  const partial = partialSegments[src];
                  if (!partial) return null;
                  return (
                    <div
                      key={`partial-${src}`}
                      className={`p-3 rounded-lg border border-dashed animate-pulse ${
                        src === 'tab'
                          ? 'bg-purple-950/10 border-purple-800/50 text-purple-300/80'
                          : 'bg-zinc-900/30 border-zinc-700/70 text-zinc-400'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1 text-[10px] font-mono">
                        <div className="flex items-center gap-1.5">
                          <span className="font-semibold uppercase">
                            {partial.speaker_label || (src === 'tab' ? 'Interviewer' : 'Me')}
                          </span>
                          <span className="px-1.5 py-0.2 rounded bg-zinc-800 text-amber-400 text-[9px]">
                            LIVE PARTIAL
                          </span>
                        </div>
                        <span className="text-zinc-500">{new Date(partial.timestamp).toLocaleTimeString()}</span>
                      </div>
                      <p className="text-xs italic leading-relaxed">{partial.text}...</p>
                    </div>
                  );
                })}
              </>
            )}

            {/* Questions Section */}
            {questions.length > 0 && (
              <div className="pt-4 border-t border-zinc-800/80 space-y-2">
                <div className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                  Detected Questions
                </div>
                {questions.map((q) => (
                  <button
                    key={q.id}
                    onClick={() => setActiveQuestion(q)}
                    className={`w-full p-2.5 rounded-lg border text-left transition-all ${
                      activeQuestion?.id === q.id
                        ? 'border-emerald-500 bg-emerald-950/20 text-zinc-100 shadow-sm'
                        : 'border-zinc-800 bg-zinc-900/40 text-zinc-300 hover:border-zinc-700'
                    }`}
                  >
                    <div className="flex items-center justify-between text-[10px] mb-1">
                      <span
                        className={`px-1.5 py-0.5 rounded font-mono uppercase ${
                          q.question_type === 'screen'
                            ? 'bg-cyan-950/70 text-cyan-300 border border-cyan-800/60'
                            : 'bg-zinc-800 text-zinc-400'
                        }`}
                      >
                        {q.question_type}
                      </span>
                      <span className="text-zinc-500 font-mono">{new Date(q.detected_at).toLocaleTimeString()}</span>
                    </div>
                    <p className="text-xs font-medium">{q.question_text}</p>
                  </button>
                ))}
              </div>
            )}

            <div ref={transcriptEndRef} />
          </div>

          {/* Manual Question Input Fallback */}
          <form
            onSubmit={handleManualQuestionSubmit}
            className="p-3 border-t border-zinc-800 bg-zinc-900/40 flex items-center gap-2 shrink-0"
          >
            <input
              type="text"
              value={manualInput}
              onChange={(e) => setManualInput(e.target.value)}
              placeholder="Ask or type question manually (e.g. for Zoom/Teams)..."
              className="flex-1 px-3 py-2 bg-zinc-950 border border-zinc-800 rounded-lg text-xs text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500"
            />
            <button
              type="submit"
              disabled={!manualInput.trim()}
              className="p-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 transition-colors disabled:opacity-40"
              title="Submit Question"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
        </div>

        {/* ======================================================== */}
        {/* RIGHT PANEL: AI Answer Workspace                          */}
        {/* ======================================================== */}
        <div className="flex flex-col h-full bg-zinc-950/20 overflow-hidden">
          {/* Panel Header & Style Switcher */}
          <div className="p-3 border-b border-zinc-800/80 bg-zinc-900/40 flex flex-wrap items-center justify-between gap-2 shrink-0">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-emerald-400" />
              <span className="text-xs font-semibold text-zinc-200">AI Suggested Answer</span>
            </div>

            {/* Answer Style Selector */}
            <div className="flex items-center gap-1 p-0.5 bg-zinc-950 rounded-lg border border-zinc-800 text-[11px]">
              {(['short', 'detailed', 'practical', 'stepbystep'] as AnswerStyle[]).map((style) => (
                <button
                  key={style}
                  onClick={() => handleStyleChange(style)}
                  disabled={isGeneratingActive}
                  className={`px-2.5 py-1 rounded-md capitalize font-medium transition-colors disabled:opacity-50 ${
                    selectedStyle === style
                      ? 'bg-zinc-800 text-emerald-400 shadow-sm'
                      : 'text-zinc-400 hover:text-zinc-200'
                  }`}
                >
                  {style === 'stepbystep' ? 'Step-by-Step' : style}
                </button>
              ))}
            </div>
          </div>

          {/* Main Answer Content Area */}
          <div className="flex-1 p-6 overflow-y-auto space-y-5">
            {activeQuestion ? (
              <div className="space-y-4">
                {/* Active Question Box */}
                <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/50 space-y-1.5">
                  <div className="flex items-center justify-between text-[11px] text-zinc-400">
                    <span className="font-semibold text-zinc-300 uppercase tracking-wide font-mono">
                      Detected Question
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 border border-zinc-700">
                      {activeQuestion.question_type}
                    </span>
                  </div>
                  <h2 className="text-base font-semibold text-zinc-100">
                    {activeQuestion.question_text}
                  </h2>
                </div>

                {/* LLM Error Display */}
                {answerError && (
                  <div className="p-3.5 rounded-xl border border-red-800/50 bg-red-950/40 text-xs text-red-300 flex items-start justify-between gap-3">
                    <div className="flex items-start gap-2">
                      <AlertCircle className="h-4 w-4 shrink-0 text-red-400 mt-0.5" />
                      <div>
                        <p className="font-semibold text-red-200">Answer Generation Error</p>
                        <p className="mt-0.5">{answerError}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => requestAnswerGeneration(activeQuestion)}
                      className="px-2.5 py-1 rounded-md bg-red-900/50 hover:bg-red-800/60 text-red-100 text-[11px] font-medium shrink-0"
                    >
                      Retry
                    </button>
                  </div>
                )}

                {/* Grounding / Customization Warning */}
                {(activeStream?.needsCustomization || activeAnswer?.needs_customization) && (
                  <div className="p-3 rounded-lg border border-amber-800/50 bg-amber-950/30 text-xs text-amber-300 flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
                      <span>
                        No resume uploaded — personal details are marked with placeholders rather than fabricated.
                      </span>
                    </div>
                    <Link href="/resume" className="underline text-amber-200 font-medium shrink-0">
                      Upload Resume
                    </Link>
                  </div>
                )}

                {/* Streaming or Finalized Answer Display */}
                {isGeneratingActive && (!activeStream || !activeStream.text) ? (
                  <div className="p-8 rounded-xl border border-zinc-800 bg-zinc-900/30 text-center space-y-3">
                    <div className="flex items-center justify-center gap-2 text-emerald-400 text-xs font-medium">
                      <Sparkles className="h-4 w-4 animate-spin" />
                      <span>Streaming grounded answer ({selectedStyle})...</span>
                    </div>
                    <p className="text-[11px] text-zinc-500 max-w-sm mx-auto">
                      Transcript remains live and unblocked while the AI generates your response.
                    </p>
                  </div>
                ) : activeStream?.text || activeAnswer ? (
                  <div className="p-5 rounded-xl border border-emerald-900/40 bg-zinc-900/50 space-y-4 shadow-lg">
                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs pb-3 border-b border-zinc-800">
                      <div className="flex items-center gap-2">
                        {isGeneratingActive ? (
                          <Sparkles className="h-4 w-4 text-emerald-400 animate-spin" />
                        ) : (
                          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                        )}
                        <span className="font-medium text-zinc-200">
                          {isGeneratingActive ? 'Streaming Response...' : 'Grounded Response'}
                        </span>
                        {activeAnswer?.model_used && !isGeneratingActive && (
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
                            {activeAnswer.model_used}
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => requestAnswerGeneration(activeQuestion, { expand: true })}
                          disabled={isGeneratingActive}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs transition-colors border border-zinc-700 disabled:opacity-40"
                          title="Expand with deeper detail and examples"
                        >
                          <Maximize2 className="h-3 w-3" />
                          <span>Expand</span>
                        </button>
                        <button
                          onClick={() => requestAnswerGeneration(activeQuestion)}
                          disabled={isGeneratingActive}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs transition-colors border border-zinc-700 disabled:opacity-40"
                          title="Regenerate answer"
                        >
                          <RotateCw className="h-3 w-3" />
                          <span>Regenerate</span>
                        </button>
                        <button
                          onClick={handleCopyAnswer}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs transition-colors border border-zinc-700"
                        >
                          {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                          <span>{copied ? 'Copied' : 'Copy'}</span>
                        </button>
                      </div>
                    </div>

                    {/* Important Keywords Chips */}
                    {activeAnswer?.keywords && activeAnswer.keywords.length > 0 && !isGeneratingActive && (
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-[10px] uppercase font-mono text-zinc-500 mr-1">Keywords:</span>
                        {activeAnswer.keywords.map((kw) => (
                          <span
                            key={kw}
                            className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-950/40 text-emerald-300 border border-emerald-800/50"
                          >
                            {kw}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Structured Answer Text Body */}
                    <StructuredAnswerView
                      text={
                        isGeneratingActive && activeStream
                          ? activeStream.text
                          : activeAnswer?.answer_text || ''
                      }
                      streaming={Boolean(isGeneratingActive && activeStream)}
                    />

                    {/* Latency & Style Footer */}
                    {!isGeneratingActive && activeAnswer && (
                      <div className="pt-3 border-t border-zinc-800/80 flex flex-wrap items-center justify-between gap-2 text-[11px] text-zinc-500 font-mono">
                        <span>Style: {activeAnswer.style.toUpperCase()}</span>
                        <span>
                          {activeAnswer.ttft_ms != null ? `TTFT: ${activeAnswer.ttft_ms}ms • ` : ''}
                          Total: {activeAnswer.generation_time_ms}ms
                        </span>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-6 rounded-xl border border-dashed border-zinc-800 bg-zinc-900/20 text-center space-y-2">
                    <p className="text-xs text-zinc-400">Ready to synthesize answer for this question.</p>
                    <button
                      onClick={() => requestAnswerGeneration(activeQuestion)}
                      className="px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs font-medium hover:bg-emerald-500/20"
                    >
                      Generate Suggested Answer
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-3 text-zinc-600">
                <HelpCircle className="h-10 w-10 text-zinc-700" />
                <div>
                  <p className="text-xs font-medium text-zinc-400">No question selected</p>
                  <p className="text-[11px] text-zinc-600 max-w-sm mt-1">
                    When the interviewer asks a question, it will be automatically detected and displayed here with AI suggestions.
                    You can also type questions manually in the left box.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
