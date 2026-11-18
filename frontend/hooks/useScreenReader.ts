'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '@/services/api';
import { ScreenCaptureProvider } from '@/services/screenCapture';
import { DetectedQuestion, GeneratedAnswer, ScreenAnalysisResponse } from '@/types';

export type ScreenShareStatus = 'idle' | 'requesting' | 'sharing' | 'denied' | 'ended' | 'error';

interface UseScreenReaderOptions {
  sessionId: string;
  enabled?: boolean;
  style?: 'short' | 'detailed' | 'practical' | 'stepbystep';
  autoIntervalMs?: number;
  diffThreshold?: number;
  onAnalysisResult?: (result: ScreenAnalysisResponse) => void;
  onQuestionDetected?: (question: DetectedQuestion) => void;
  onAnswerComplete?: (answer: GeneratedAnswer) => void;
}

export function useScreenReader({
  sessionId,
  enabled = true,
  style = 'short',
  autoIntervalMs = 8000,
  diffThreshold = 0.035,
  onAnalysisResult,
  onQuestionDetected,
  onAnswerComplete,
}: UseScreenReaderOptions) {
  const [screenStatus, setScreenStatus] = useState<ScreenShareStatus>('idle');
  const [screenError, setScreenError] = useState<string | null>(null);
  const [autoWatch, setAutoWatch] = useState<boolean>(false);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [lastPreviewUrl, setLastPreviewUrl] = useState<string | null>(null);
  const [lastStatusNote, setLastStatusNote] = useState<string | null>(null);

  const providerRef = useRef<ScreenCaptureProvider | null>(null);
  const analyzingRef = useRef<boolean>(false);
  const styleRef = useRef(style);
  const callbacksRef = useRef({ onAnalysisResult, onQuestionDetected, onAnswerComplete });

  useEffect(() => {
    styleRef.current = style;
  }, [style]);

  useEffect(() => {
    callbacksRef.current = { onAnalysisResult, onQuestionDetected, onAnswerComplete };
  }, [onAnalysisResult, onQuestionDetected, onAnswerComplete]);

  const stopScreenShare = useCallback(() => {
    providerRef.current?.stop();
    providerRef.current = null;
    setAutoWatch(false);
    setScreenStatus('idle');
    setLastStatusNote(null);
  }, []);

  const startScreenShare = useCallback(async () => {
    if (!enabled) return;
    setScreenError(null);
    setScreenStatus('requesting');

    const provider = new ScreenCaptureProvider({
      onTrackEnded: () => {
        providerRef.current = null;
        setAutoWatch(false);
        setScreenStatus('ended');
        setLastStatusNote('Screen sharing stopped.');
      },
      onError: (msg) => {
        setScreenError(msg);
      },
    });

    try {
      await provider.start();
      providerRef.current = provider;
      setScreenStatus('sharing');
      setLastStatusNote('Screen shared — click Analyze Screen or enable Auto-Watch.');

      // Capture an initial preview thumbnail immediately (without calling LLM yet)
      try {
        const frame = await provider.captureFrame(640, 0.6, false);
        setLastPreviewUrl(frame.dataUrl);
      } catch {
        // Preview will populate on next capture
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Screen sharing permission denied.';
      setScreenError(msg);
      setScreenStatus(msg.toLowerCase().includes('denied') || msg.toLowerCase().includes('cancelled') ? 'denied' : 'error');
    }
  }, [enabled]);

  const runAnalysis = useCallback(
    async (opts: { prompt?: string; autoMode?: boolean; overrideStyle?: 'short' | 'detailed' | 'practical' | 'stepbystep' }) => {
      const provider = providerRef.current;
      if (!provider || !provider.isActive || !sessionId || analyzingRef.current) {
        return null;
      }

      analyzingRef.current = true;
      setIsAnalyzing(true);
      setScreenError(null);

      try {
        const frame = await provider.captureFrame(1280, 0.78, false);
        setLastPreviewUrl(frame.dataUrl);

        if (opts.autoMode && frame.diffScore < diffThreshold) {
          setLastStatusNote(`Screen unchanged (${Math.round(frame.diffScore * 100)}% delta) — skipped`);
          return null;
        }

        // Commit the diff baseline now that we're analyzing this frame
        await provider.captureFrame(640, 0.5, true).catch(() => {});

        setLastStatusNote(opts.autoMode ? 'Auto-Watch scanning screen...' : 'Analyzing screen with Gemini...');

        const result = await api.analyzeScreen(sessionId, frame.blob, {
          prompt: opts.prompt,
          style: opts.overrideStyle || styleRef.current,
          autoMode: Boolean(opts.autoMode),
        });

        callbacksRef.current.onAnalysisResult?.(result);

        if (result.actionable) {
          if (result.question) {
            callbacksRef.current.onQuestionDetected?.(result.question);
          }
          if (result.answer) {
            callbacksRef.current.onAnswerComplete?.(result.answer);
          }
          setLastStatusNote(`Answered screen topic: "${result.topic}" (${result.analysis_time_ms}ms)`);
        } else {
          setLastStatusNote(`Watched screen — no reply needed (${result.screen_summary.slice(0, 70)})`);
        }

        return result;
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Screen analysis failed.';
        setScreenError(msg);
        setLastStatusNote(`Error: ${msg}`);
        return null;
      } finally {
        analyzingRef.current = false;
        setIsAnalyzing(false);
      }
    },
    [sessionId, diffThreshold]
  );

  const analyzeNow = useCallback(
    async (prompt?: string, overrideStyle?: 'short' | 'detailed' | 'practical' | 'stepbystep') => {
      return runAnalysis({ prompt, autoMode: false, overrideStyle });
    },
    [runAnalysis]
  );

  // Auto-Watch periodic interval (only runs when sharing AND user explicitly enables autoWatch)
  useEffect(() => {
    if (!enabled || screenStatus !== 'sharing' || !autoWatch) return;

    // Reset baseline when enabling Auto-Watch so the first tick evaluates the current view
    providerRef.current?.resetDiffBaseline();

    const timer = setInterval(() => {
      void runAnalysis({ autoMode: true });
    }, autoIntervalMs);

    return () => clearInterval(timer);
  }, [enabled, screenStatus, autoWatch, autoIntervalMs, runAnalysis]);

  // Cleanup on unmount or when session is disabled/ended
  useEffect(() => {
    if (!enabled) {
      stopScreenShare();
    }
  }, [enabled, stopScreenShare]);

  useEffect(() => {
    return () => {
      providerRef.current?.stop();
      providerRef.current = null;
    };
  }, []);

  return {
    screenStatus,
    screenError,
    autoWatch,
    setAutoWatch,
    isAnalyzing,
    lastPreviewUrl,
    lastStatusNote,
    startScreenShare,
    stopScreenShare,
    analyzeNow,
  };
}
