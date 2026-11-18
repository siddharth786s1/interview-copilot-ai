'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Play, AlertCircle } from 'lucide-react';
import { api } from '@/services/api';
import { SessionType } from '@/types';

export default function NewSessionPage() {
  const router = useRouter();
  const [title, setTitle] = useState('');
  const [type, setType] = useState<SessionType>('technical');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError('Please provide a session title');
      return;
    }
    setCreating(true);
    setError(null);
    try {
      const session = await api.createSession({
        title: title.trim(),
        type,
      });
      router.push(`/session/${session.id}`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create session';
      setError(message);
      setCreating(false);
    }
  };

  return (
    <div className="container mx-auto max-w-xl px-6 py-10 space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/" className="p-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="text-xl font-bold text-zinc-100">Create Interview Session</h1>
          <p className="text-xs text-zinc-400">Initialize a new live interview workspace.</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="p-6 rounded-xl border border-zinc-800 bg-zinc-900/40 space-y-5">
        {error && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-red-950/40 border border-red-800/40 text-xs text-red-400">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div>
          <label className="block text-xs font-medium text-zinc-300 mb-1.5">Session Title</label>
          <input
            type="text"
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Senior Backend Engineer Interview — Google Meet"
            className="w-full px-3.5 py-2.5 text-sm bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-zinc-300 mb-1.5">Interview Type</label>
          <select
            value={type}
            onChange={(e) => setType(e.target.value as SessionType)}
            className="w-full px-3.5 py-2.5 text-sm bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-100 focus:outline-none focus:border-emerald-500"
          >
            <option value="technical">Technical Interview (Architecture, Coding, Systems)</option>
            <option value="hr">HR Interview (Cultural, Background, Compensation)</option>
            <option value="behavioral">Behavioral Interview (STAR format, Scenarios)</option>
            <option value="general">General Interview</option>
            <option value="mock">Mock Interview</option>
            <option value="custom">Custom</option>
          </select>
        </div>

        <div className="pt-2">
          <button
            type="submit"
            disabled={creating}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-medium text-sm transition-all shadow-sm shadow-emerald-500/20 active:scale-95 disabled:opacity-50"
          >
            <Play className="h-4 w-4 fill-zinc-950" />
            <span>{creating ? 'Creating Workspace...' : 'Launch Workspace'}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
