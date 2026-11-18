'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { DetectedQuestion, GeneratedAnswer, TranscriptSegment } from '@/types';

function resolveWsBaseUrl(): string {
  const explicit = process.env.NEXT_PUBLIC_WS_URL?.trim();
  if (explicit) return explicit.replace(/\/+$/, '');
  if (process.env.NEXT_PUBLIC_SAME_ORIGIN === 'true') {
    if (typeof window !== 'undefined') {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${proto}//${window.location.host}`;
    }
    return '';
  }
  const apiUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (apiUrl) {
    return apiUrl
      .replace(/^https:\/\//i, 'wss://')
      .replace(/^http:\/\//i, 'ws://')
      .replace(/\/+$/, '');
  }
  return 'ws://localhost:8000';
}

export type WsConnectionStatus = 'connecting' | 'connected' | 'reconnecting' | 'disconnected';

export interface LiveTranscriptEvent {
  type: 'transcript';
  session_id: string;
  source: 'tab' | 'mic' | 'manual';
  speaker_label?: string | null;
  text: string;
  is_final: boolean;
  timestamp: string;
  sequence: number;
  language?: string;
  confidence?: number;
  latency_ms?: number;
}

export interface UseSessionWebSocketOptions {
  sessionId: string;
  enabled: boolean;
  initialLanguage?: string;
  onFinalTranscript?: (segment: TranscriptSegment) => void;
  onQuestionDetected?: (question: DetectedQuestion) => void;
  onAnswerStart?: (payload: { questionId: string; style: string; needsCustomization: boolean }) => void;
  onAnswerChunk?: (payload: { questionId: string; text: string }) => void;
  onAnswerComplete?: (answer: GeneratedAnswer) => void;
  onAnswerError?: (payload: { questionId?: string; code: string; message: string }) => void;
  onServerStatus?: (status: { session_status?: string; language?: string }) => void;
}

export function useSessionWebSocket({
  sessionId,
  enabled,
  initialLanguage = 'en',
  onFinalTranscript,
  onQuestionDetected,
  onAnswerStart,
  onAnswerChunk,
  onAnswerComplete,
  onAnswerError,
  onServerStatus,
}: UseSessionWebSocketOptions) {
  const [wsStatus, setWsStatus] = useState<WsConnectionStatus>('disconnected');
  const [audioWsStatus, setAudioWsStatus] = useState<WsConnectionStatus>('disconnected');
  const [wsError, setWsError] = useState<string | null>(null);
  const [lastLatencyMs, setLastLatencyMs] = useState<number | null>(null);
  const [partialSegments, setPartialSegments] = useState<Record<string, TranscriptSegment | null>>({
    mic: null,
    tab: null,
  });

  const sessionWsRef = useRef<WebSocket | null>(null);
  const audioWsRef = useRef<WebSocket | null>(null);
  const onFinalRef = useRef(onFinalTranscript);
  const onQuestionRef = useRef(onQuestionDetected);
  const onAnswerStartRef = useRef(onAnswerStart);
  const onAnswerChunkRef = useRef(onAnswerChunk);
  const onAnswerCompleteRef = useRef(onAnswerComplete);
  const onAnswerErrorRef = useRef(onAnswerError);
  const onStatusRef = useRef(onServerStatus);
  const languageRef = useRef(initialLanguage);

  useEffect(() => {
    onFinalRef.current = onFinalTranscript;
  }, [onFinalTranscript]);

  useEffect(() => {
    onQuestionRef.current = onQuestionDetected;
  }, [onQuestionDetected]);

  useEffect(() => {
    onAnswerStartRef.current = onAnswerStart;
  }, [onAnswerStart]);

  useEffect(() => {
    onAnswerChunkRef.current = onAnswerChunk;
  }, [onAnswerChunk]);

  useEffect(() => {
    onAnswerCompleteRef.current = onAnswerComplete;
  }, [onAnswerComplete]);

  useEffect(() => {
    onAnswerErrorRef.current = onAnswerError;
  }, [onAnswerError]);

  useEffect(() => {
    onStatusRef.current = onServerStatus;
  }, [onServerStatus]);

  // Connect & maintain /ws/session/{sessionId} with exponential backoff reconnect
  useEffect(() => {
    if (!enabled || !sessionId) {
      setWsStatus('disconnected');
      return;
    }

    let cancelled = false;
    let reconnectAttempt = 0;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let pingTimer: ReturnType<typeof setInterval> | null = null;

    const connectSession = () => {
      if (cancelled) return;
      setWsStatus(reconnectAttempt > 0 ? 'reconnecting' : 'connecting');

      const ws = new WebSocket(`${resolveWsBaseUrl()}/ws/session/${sessionId}`);
      sessionWsRef.current = ws;

      ws.onopen = () => {
        if (cancelled) return;
        reconnectAttempt = 0;
        setWsStatus('connected');
        setWsError(null);

        pingTimer = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 15000);
      };

      ws.onmessage = (event) => {
        if (cancelled) return;
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'transcript') {
            const ev = data as LiveTranscriptEvent;
            const seg: TranscriptSegment = {
              id: `ws-${ev.session_id}-${ev.sequence}`,
              session_id: ev.session_id,
              source: ev.source,
              speaker_label: ev.speaker_label,
              text: ev.text,
              is_final: ev.is_final,
              timestamp: ev.timestamp,
              sequence: ev.sequence,
            };

            if (typeof ev.latency_ms === 'number') {
              setLastLatencyMs(ev.latency_ms);
            }

            if (ev.is_final) {
              setPartialSegments((prev) => ({ ...prev, [ev.source]: null }));
              onFinalRef.current?.(seg);
            } else {
              setPartialSegments((prev) => ({ ...prev, [ev.source]: seg }));
            }
          } else if (data.type === 'question') {
            const q: DetectedQuestion = {
              id: data.question_id,
              session_id: data.session_id || sessionId,
              question_text: data.text,
              question_type: data.question_type || 'direct',
              detected_at: data.detected_at || new Date().toISOString(),
              answered: false,
            };
            onQuestionRef.current?.(q);
          } else if (data.type === 'answer_start') {
            onAnswerStartRef.current?.({
              questionId: data.question_id,
              style: data.style || 'short',
              needsCustomization: Boolean(data.needs_customization),
            });
          } else if (data.type === 'answer_chunk') {
            onAnswerChunkRef.current?.({
              questionId: data.question_id,
              text: data.text || '',
            });
          } else if (data.type === 'answer_complete') {
            const ans: GeneratedAnswer = {
              id: data.answer_id || `ans-${Date.now()}`,
              question_id: data.question_id,
              style: data.style || 'short',
              answer_text: data.full_text || '',
              model_used: data.model_used || '',
              generated_at: data.generated_at || new Date().toISOString(),
              generation_time_ms: data.generation_ms || 0,
              ttft_ms: data.ttft_ms ?? null,
              keywords: Array.isArray(data.keywords) ? data.keywords : [],
              needs_customization: Boolean(data.needs_customization),
            };
            onAnswerCompleteRef.current?.(ans);
          } else if (data.type === 'status') {
            onStatusRef.current?.({
              session_status: data.session_status,
              language: data.language,
            });
          } else if (data.type === 'error') {
            const msg = data.message || data.code || 'Streaming error';
            setWsError(msg);
            if (data.question_id || String(data.code || '').startsWith('LLM_')) {
              onAnswerErrorRef.current?.({
                questionId: data.question_id,
                code: data.code || 'LLM_ERROR',
                message: msg,
              });
            }
          }
        } catch {
          // ignore malformed messages
        }
      };

      ws.onerror = () => {
        if (!cancelled) {
          setWsError('Session WebSocket connection interrupted — attempting reconnect...');
        }
      };

      ws.onclose = () => {
        if (pingTimer) {
          clearInterval(pingTimer);
          pingTimer = null;
        }
        if (cancelled) return;
        setWsStatus('reconnecting');
        const delay = Math.min(10000, 1000 * Math.pow(2, reconnectAttempt));
        reconnectAttempt += 1;
        reconnectTimer = setTimeout(connectSession, delay);
      };
    };

    connectSession();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (pingTimer) clearInterval(pingTimer);
      if (sessionWsRef.current) {
        sessionWsRef.current.close();
        sessionWsRef.current = null;
      }
      setWsStatus('disconnected');
    };
  }, [sessionId, enabled]);

  // Connect & maintain /ws/audio/{sessionId} with exponential backoff reconnect
  useEffect(() => {
    if (!enabled || !sessionId) {
      setAudioWsStatus('disconnected');
      return;
    }

    let cancelled = false;
    let reconnectAttempt = 0;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    const connectAudio = () => {
      if (cancelled) return;
      setAudioWsStatus(reconnectAttempt > 0 ? 'reconnecting' : 'connecting');

      const ws = new WebSocket(`${resolveWsBaseUrl()}/ws/audio/${sessionId}`);
      ws.binaryType = 'arraybuffer';
      audioWsRef.current = ws;

      ws.onopen = () => {
        if (cancelled) return;
        reconnectAttempt = 0;
        setAudioWsStatus('connected');
        // Sync current language setting upon (re)connect
        ws.send(JSON.stringify({ type: 'config', language: languageRef.current }));
      };

      ws.onclose = () => {
        if (cancelled) return;
        setAudioWsStatus('reconnecting');
        const delay = Math.min(10000, 1000 * Math.pow(2, reconnectAttempt));
        reconnectAttempt += 1;
        reconnectTimer = setTimeout(connectAudio, delay);
      };
    };

    connectAudio();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (audioWsRef.current) {
        audioWsRef.current.close();
        audioWsRef.current = null;
      }
      setAudioWsStatus('disconnected');
    };
  }, [sessionId, enabled]);

  const sendAudioChunk = useCallback((chunk: ArrayBuffer) => {
    const ws = audioWsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(chunk);
    }
  }, []);

  const sendControl = useCallback((action: 'pause' | 'resume' | 'flush' | 'end') => {
    const ws = audioWsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'control', action }));
    }
  }, []);

  const sendLanguageConfig = useCallback((language: string) => {
    languageRef.current = language;
    const ws = audioWsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'config', language }));
    }
  }, []);

  return {
    wsStatus,
    audioWsStatus,
    wsError,
    lastLatencyMs,
    partialSegments,
    sendAudioChunk,
    sendControl,
    sendLanguageConfig,
  };
}
