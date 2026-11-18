'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { api } from '@/services/api';
import { Session } from '@/types';
import { CreateSessionModal } from '@/components/CreateSessionModal';
import {
  Mic,
  PlusCircle,
  Clock,
  Sparkles,
  AlertCircle,
  Trash2,
  ExternalLink,
  ShieldCheck,
  Server,
  Layers,
  GraduationCap,
  FileText,
  BookOpen,
  History,
  Sliders,
  Filter,
} from 'lucide-react';

export default function DashboardPage() {
  const [health, setHealth] = useState<{ status: string; version: string; service: string } | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [filterType, setFilterType] = useState<string>('all');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [h, s] = await Promise.all([
        api.getHealth().catch((e) => {
          setHealthError(e.message);
          return null;
        }),
        api.listSessions({
          type: filterType !== 'all' ? filterType : undefined,
          status: filterStatus !== 'all' ? filterStatus : undefined,
        }).catch(() => []),
      ]);
      if (h) setHealth(h);
      setSessions(s);
    } finally {
      setLoading(false);
    }
  }, [filterType, filterStatus]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleDeleteSession = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    if (!confirm('Are you sure you want to delete this session and all its records?')) return;
    setDeletingId(id);
    try {
      await api.deleteSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to delete session';
      alert(msg);
    } finally {
      setDeletingId(null);
    }
  };

  const activeSessionsCount = sessions.filter((s) => s.status === 'active').length;
  const totalDurationMinutes = Math.round(
    sessions.reduce((acc, s) => acc + (s.duration_seconds || 0), 0) / 60
  );

  return (
    <div className="container mx-auto max-w-6xl px-6 py-8 space-y-8">
      {/* Top Banner & Primary Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 p-6 rounded-xl border border-zinc-800 bg-zinc-900/50 backdrop-blur">
        <div>
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-emerald-500/10 text-emerald-400 text-xs font-mono font-medium border border-emerald-500/20 mb-3">
            <Sparkles className="h-3.5 w-3.5" />
            <span>Local Real-Time Architecture</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100">
            Interview Copilot AI
          </h1>
          <p className="text-sm text-zinc-400 mt-1 max-w-xl">
            Live speech transcription, automated question detection, and grounded answer synthesis for your verified interviews.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-medium text-sm transition-all shadow-sm shadow-emerald-500/20 active:scale-95"
          >
            <PlusCircle className="h-4 w-4" />
            <span>Start Interview Session</span>
          </button>
          <Link
            href="/mock"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-medium text-sm border border-zinc-700 transition-colors"
          >
            <GraduationCap className="h-4 w-4 text-emerald-400" />
            <span>Mock Interview</span>
          </Link>
        </div>
      </div>

      {/* Metrics & System Health Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/30 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2.5 rounded-lg ${health ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'}`}>
              <Server className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-zinc-400 font-medium">Backend Health</p>
              <p className="text-sm font-semibold text-zinc-100">
                {health ? `${health.service}` : healthError ? 'Offline' : 'Connecting...'}
              </p>
            </div>
          </div>
          {health ? (
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800">
              v{health.version}
            </span>
          ) : (
            <AlertCircle className="h-4 w-4 text-amber-400 animate-pulse" />
          )}
        </div>

        <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/30 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-blue-500/10 text-blue-400">
              <Layers className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-zinc-400 font-medium">Total Sessions</p>
              <p className="text-lg font-bold text-zinc-100">{sessions.length}</p>
            </div>
          </div>
          <span className="text-xs text-zinc-500">Recorded</span>
        </div>

        <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/30 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-purple-500/10 text-purple-400">
              <Mic className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-zinc-400 font-medium">Active Sessions</p>
              <p className="text-lg font-bold text-zinc-100">{activeSessionsCount}</p>
            </div>
          </div>
          <span className="text-xs text-zinc-500">{activeSessionsCount > 0 ? 'Live now' : 'Idle'}</span>
        </div>

        <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/30 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-amber-500/10 text-amber-400">
              <Clock className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs text-zinc-400 font-medium">Interview Time</p>
              <p className="text-lg font-bold text-zinc-100">{totalDurationMinutes}m</p>
            </div>
          </div>
          <span className="text-xs text-zinc-500">Total</span>
        </div>
      </div>

      {/* Quick Navigation Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Link
          href="/resume"
          className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/20 hover:bg-zinc-800/40 hover:border-zinc-700 transition-all group"
        >
          <FileText className="h-5 w-5 text-emerald-400 mb-2 group-hover:scale-105 transition-transform" />
          <h3 className="text-sm font-semibold text-zinc-200">Resume</h3>
          <p className="text-xs text-zinc-500 mt-0.5">Manage work facts & projects</p>
        </Link>

        <Link
          href="/knowledge-base"
          className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/20 hover:bg-zinc-800/40 hover:border-zinc-700 transition-all group"
        >
          <BookOpen className="h-5 w-5 text-blue-400 mb-2 group-hover:scale-105 transition-transform" />
          <h3 className="text-sm font-semibold text-zinc-200">Knowledge Base</h3>
          <p className="text-xs text-zinc-500 mt-0.5">Study notes & system design</p>
        </Link>

        <Link
          href="/history"
          className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/20 hover:bg-zinc-800/40 hover:border-zinc-700 transition-all group"
        >
          <History className="h-5 w-5 text-purple-400 mb-2 group-hover:scale-105 transition-transform" />
          <h3 className="text-sm font-semibold text-zinc-200">History</h3>
          <p className="text-xs text-zinc-500 mt-0.5">Past questions & answers</p>
        </Link>

        <Link
          href="/settings"
          className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/20 hover:bg-zinc-800/40 hover:border-zinc-700 transition-all group"
        >
          <Sliders className="h-5 w-5 text-amber-400 mb-2 group-hover:scale-105 transition-transform" />
          <h3 className="text-sm font-semibold text-zinc-200">Settings</h3>
          <p className="text-xs text-zinc-500 mt-0.5">LLM & speech config</p>
        </Link>
      </div>

      {/* Compliance / Privacy Callout */}
      <div className="flex items-start gap-3 p-4 rounded-xl border border-zinc-800/80 bg-zinc-900/20 text-xs text-zinc-400">
        <ShieldCheck className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
        <div>
          <span className="font-semibold text-zinc-300">Permitted & Transparent Usage: </span>
          Audio capture operates strictly with explicit browser permissions and visual live meters. No covert recording or anti-proctoring bypass is implemented. Answers are grounded in your actual uploaded materials.
        </div>
      </div>

      {/* Sessions Management Area */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">Interview Sessions</h2>
            <p className="text-xs text-zinc-400">Manage, launch, and review your live and completed sessions</p>
          </div>

          {/* Filters */}
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-zinc-800 bg-zinc-900/60 text-xs text-zinc-300">
              <Filter className="h-3.5 w-3.5 text-zinc-500" />
              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                className="bg-transparent text-xs text-zinc-300 focus:outline-none"
              >
                <option value="all" className="bg-zinc-950">All Types</option>
                <option value="technical" className="bg-zinc-950">Technical</option>
                <option value="hr" className="bg-zinc-950">HR</option>
                <option value="behavioral" className="bg-zinc-950">Behavioral</option>
                <option value="general" className="bg-zinc-950">General</option>
                <option value="mock" className="bg-zinc-950">Mock</option>
                <option value="custom" className="bg-zinc-950">Custom</option>
              </select>
            </div>

            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-zinc-800 bg-zinc-900/60 text-xs text-zinc-300">
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="bg-transparent text-xs text-zinc-300 focus:outline-none"
              >
                <option value="all" className="bg-zinc-950">All Statuses</option>
                <option value="created" className="bg-zinc-950">Created</option>
                <option value="active" className="bg-zinc-950">Active</option>
                <option value="paused" className="bg-zinc-950">Paused</option>
                <option value="ended" className="bg-zinc-950">Ended</option>
              </select>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="p-12 text-center border border-zinc-800 rounded-xl text-sm text-zinc-500">
            Loading sessions...
          </div>
        ) : sessions.length === 0 ? (
          <div className="p-12 text-center border border-dashed border-zinc-800 rounded-xl bg-zinc-900/10 space-y-4">
            <Clock className="h-10 w-10 text-zinc-600 mx-auto" />
            <div>
              <p className="text-sm font-semibold text-zinc-300">No interview sessions found</p>
              <p className="text-xs text-zinc-500 mt-1 max-w-sm mx-auto">
                {filterType !== 'all' || filterStatus !== 'all'
                  ? 'No sessions match your active filters.'
                  : 'Start your first interview session to launch the real-time assistant workspace.'}
              </p>
            </div>
            <button
              onClick={() => setIsModalOpen(true)}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-medium transition-colors"
            >
              <PlusCircle className="h-4 w-4" />
              <span>Create New Session</span>
            </button>
          </div>
        ) : (
          <div className="divide-y divide-zinc-800 border border-zinc-800 rounded-xl overflow-hidden bg-zinc-900/20">
            {sessions.map((session) => {
              const isDeleting = deletingId === session.id;
              const statusColors = {
                created: 'bg-zinc-800 text-zinc-400 border-zinc-700',
                active: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
                paused: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
                ended: 'bg-zinc-900 text-zinc-500 border-zinc-800',
              }[session.status] || 'bg-zinc-800 text-zinc-400 border-zinc-700';

              return (
                <div
                  key={session.id}
                  className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-zinc-800/30 transition-colors"
                >
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        href={`/session/${session.id}`}
                        className="text-sm font-semibold text-zinc-100 hover:text-emerald-400 transition-colors flex items-center gap-1.5"
                      >
                        <span>{session.title}</span>
                        <ExternalLink className="h-3 w-3 text-zinc-500" />
                      </Link>
                      <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700">
                        {session.type}
                      </span>
                      <span className={`text-[10px] uppercase font-mono px-2 py-0.5 rounded border ${statusColors}`}>
                        {session.status}
                      </span>
                    </div>
                    <p className="text-xs text-zinc-500">
                      Created: {new Date(session.created_at).toLocaleString()}
                      {session.duration_seconds !== null && ` • Duration: ${Math.round(session.duration_seconds / 60)} min`}
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <Link
                      href={`/session/${session.id}`}
                      className="px-3 py-1.5 text-xs font-medium rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 transition-colors"
                    >
                      Workspace
                    </Link>
                    <button
                      onClick={(e) => handleDeleteSession(session.id, e)}
                      disabled={isDeleting}
                      title="Delete Session"
                      className="p-1.5 text-zinc-500 hover:text-red-400 rounded-lg hover:bg-red-950/20 transition-colors disabled:opacity-50"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Modal */}
      <CreateSessionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSessionCreated={loadData}
      />
    </div>
  );
}
