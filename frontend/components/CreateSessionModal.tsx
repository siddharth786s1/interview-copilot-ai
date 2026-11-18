'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { X, Play, Volume2, Mic, AlertCircle, Laptop } from 'lucide-react';
import { api } from '@/services/api';
import { SessionType } from '@/types';

interface CreateSessionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSessionCreated?: () => void;
}

export function CreateSessionModal({ isOpen, onClose, onSessionCreated }: CreateSessionModalProps) {
  const router = useRouter();
  const [title, setTitle] = useState('');
  const [type, setType] = useState<SessionType>('technical');
  const [audioSource, setAudioSource] = useState<'both' | 'mic' | 'tab' | 'manual'>('both');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError('Please provide a session title');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const session = await api.createSession({
        title: title.trim(),
        type,
        settings: {
          audioSource,
        },
      });
      if (onSessionCreated) onSessionCreated();
      onClose();
      router.push(`/session/${session.id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create session';
      setError(msg);
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg rounded-xl border border-zinc-800 bg-zinc-950 p-6 shadow-2xl space-y-5">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
          <div>
            <h2 className="text-base font-semibold text-zinc-100">Start Interview Session</h2>
            <p className="text-xs text-zinc-400">Configure your session type and audio input source</p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-red-950/40 border border-red-800/40 text-xs text-red-400">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1.5">Session Title</label>
            <input
              type="text"
              required
              autoFocus
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Senior Backend Engineer — Google Meet"
              className="w-full px-3 py-2 text-sm bg-zinc-900 border border-zinc-800 rounded-lg text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1.5">Session Type</label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value as SessionType)}
              className="w-full px-3 py-2 text-sm bg-zinc-900 border border-zinc-800 rounded-lg text-zinc-100 focus:outline-none focus:border-emerald-500"
            >
              <option value="technical">Technical Interview (Architecture, System Design, Coding)</option>
              <option value="hr">HR Interview (Cultural, Background, Compensation)</option>
              <option value="behavioral">Behavioral Interview (STAR Format, Experience)</option>
              <option value="general">General Interview</option>
              <option value="mock">Mock Interview Practice</option>
              <option value="custom">Custom Interview</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1.5">Audio Capture Setup</label>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <button
                type="button"
                onClick={() => setAudioSource('both')}
                className={`p-2.5 rounded-lg border text-left transition-all ${
                  audioSource === 'both'
                    ? 'border-emerald-500 bg-emerald-950/20 text-zinc-100'
                    : 'border-zinc-800 bg-zinc-900/40 text-zinc-400 hover:border-zinc-700'
                }`}
              >
                <div className="flex items-center gap-1.5 font-medium mb-0.5 text-zinc-200">
                  <Volume2 className="h-3.5 w-3.5 text-emerald-400" />
                  <span>Tab + Mic</span>
                </div>
                <span className="text-[11px] text-zinc-500">Google Meet browser tab + Microphone</span>
              </button>

              <button
                type="button"
                onClick={() => setAudioSource('mic')}
                className={`p-2.5 rounded-lg border text-left transition-all ${
                  audioSource === 'mic'
                    ? 'border-emerald-500 bg-emerald-950/20 text-zinc-100'
                    : 'border-zinc-800 bg-zinc-900/40 text-zinc-400 hover:border-zinc-700'
                }`}
              >
                <div className="flex items-center gap-1.5 font-medium mb-0.5 text-zinc-200">
                  <Mic className="h-3.5 w-3.5 text-blue-400" />
                  <span>Microphone Only</span>
                </div>
                <span className="text-[11px] text-zinc-500">Record only user speaking voice</span>
              </button>

              <button
                type="button"
                onClick={() => setAudioSource('tab')}
                className={`p-2.5 rounded-lg border text-left transition-all ${
                  audioSource === 'tab'
                    ? 'border-emerald-500 bg-emerald-950/20 text-zinc-100'
                    : 'border-zinc-800 bg-zinc-900/40 text-zinc-400 hover:border-zinc-700'
                }`}
              >
                <div className="flex items-center gap-1.5 font-medium mb-0.5 text-zinc-200">
                  <Volume2 className="h-3.5 w-3.5 text-purple-400" />
                  <span>Tab Audio Only</span>
                </div>
                <span className="text-[11px] text-zinc-500">Interviewer voice from browser tab</span>
              </button>

              <button
                type="button"
                onClick={() => setAudioSource('manual')}
                className={`p-2.5 rounded-lg border text-left transition-all ${
                  audioSource === 'manual'
                    ? 'border-emerald-500 bg-emerald-950/20 text-zinc-100'
                    : 'border-zinc-800 bg-zinc-900/40 text-zinc-400 hover:border-zinc-700'
                }`}
              >
                <div className="flex items-center gap-1.5 font-medium mb-0.5 text-zinc-200">
                  <Laptop className="h-3.5 w-3.5 text-amber-400" />
                  <span>Manual Input</span>
                </div>
                <span className="text-[11px] text-zinc-500">Zoom / Teams desktop fallback</span>
              </button>
            </div>
          </div>

          <div className="pt-2 flex items-center justify-end gap-2 border-t border-zinc-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-xs font-medium text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-medium text-xs transition-all shadow-sm shadow-emerald-500/20 active:scale-95 disabled:opacity-50"
            >
              <Play className="h-3.5 w-3.5 fill-zinc-950" />
              <span>{submitting ? 'Creating...' : 'Launch Workspace'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
