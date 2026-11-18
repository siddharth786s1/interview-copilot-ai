'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  ArrowLeft,
  AlertCircle,
  HelpCircle,
  Radio,
  Cpu,
  Layers,
} from 'lucide-react';
import { useAudioCapture } from '@/hooks/useAudioCapture';

export default function AudioTestPage() {
  const [chunkCount, setChunkCount] = useState(0);

  const {
    micStatus,
    tabStatus,
    micLevel,
    tabLevel,
    micError,
    tabError,
    availableDevices,
    selectedDeviceId,
    setSelectedDeviceId,
    startMic,
    stopMic,
    startTab,
    stopTab,
  } = useAudioCapture({
    onChunk: () => {
      setChunkCount((prev) => prev + 1);
    },
  });

  return (
    <div className="container mx-auto max-w-4xl px-6 py-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="p-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
              <Radio className="h-5 w-5 text-emerald-400" />
              Audio Capture Loopback & Diagnostics
            </h1>
            <p className="text-xs text-zinc-400">
              Verify your microphone and Google Meet tab-audio inputs with real-time level meters.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 font-mono text-xs px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400">
          <Cpu className="h-3.5 w-3.5 text-emerald-400" />
          <span>16kHz 16-bit PCM</span>
        </div>
      </div>

      {/* Grid of Two Sources */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* ======================================================= */}
        {/* SOURCE 1: Microphone (User Voice)                       */}
        {/* ======================================================= */}
        <div className="p-6 rounded-xl border border-zinc-800 bg-zinc-900/40 space-y-5">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <div className="flex items-center gap-2">
              <div className={`p-2 rounded-lg ${micStatus === 'recording' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-zinc-800 text-zinc-400'}`}>
                <Mic className="h-4 w-4" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-zinc-200">Microphone Input</h2>
                <p className="text-[11px] text-zinc-500">Captures your speech via getUserMedia</p>
              </div>
            </div>

            <span className={`text-[10px] uppercase font-mono px-2 py-0.5 rounded border ${
              micStatus === 'recording'
                ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800'
                : micStatus === 'requesting'
                ? 'bg-blue-950/40 text-blue-400 border-blue-800 animate-pulse'
                : micStatus === 'denied' || micStatus === 'error'
                ? 'bg-red-950/40 text-red-400 border-red-800'
                : 'bg-zinc-800 text-zinc-400 border-zinc-700'
            }`}>
              {micStatus}
            </span>
          </div>

          {/* Device Selection */}
          <div className="space-y-1.5">
            <label className="block text-xs font-medium text-zinc-400">Select Microphone Device</label>
            <select
              value={selectedDeviceId}
              onChange={(e) => setSelectedDeviceId(e.target.value)}
              disabled={micStatus === 'recording'}
              className="w-full px-3 py-2 text-xs bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-200 focus:outline-none focus:border-emerald-500 disabled:opacity-50"
            >
              {availableDevices.length === 0 ? (
                <option value="">Default System Microphone</option>
              ) : (
                availableDevices.map((d) => (
                  <option key={d.deviceId} value={d.deviceId}>
                    {d.label || `Microphone (${d.deviceId.slice(0, 8)}...)`}
                  </option>
                ))
              )}
            </select>
          </div>

          {/* Live Level Meter */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs text-zinc-400 font-mono">
              <span>Input Level</span>
              <span>{Math.round(micLevel * 100)}%</span>
            </div>
            <div className="h-3 w-full bg-zinc-950 border border-zinc-800 rounded-full overflow-hidden p-0.5">
              <div
                className="h-full bg-gradient-to-r from-emerald-500 via-teal-400 to-emerald-300 rounded-full transition-all duration-75"
                style={{ width: `${Math.max(2, micLevel * 100)}%` }}
              />
            </div>
          </div>

          {/* Error Message */}
          {micError && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-red-950/40 border border-red-800/40 text-xs text-red-400">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold">Microphone Error: </span>
                {micError}
              </div>
            </div>
          )}

          {/* Controls */}
          <div className="pt-2">
            {micStatus === 'recording' ? (
              <button
                onClick={stopMic}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-red-950/60 hover:bg-red-900/80 text-red-300 border border-red-800/60 text-xs font-medium transition-colors"
              >
                <MicOff className="h-4 w-4" />
                <span>Stop Microphone</span>
              </button>
            ) : (
              <button
                onClick={startMic}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-medium text-xs transition-all shadow-sm shadow-emerald-500/20 active:scale-95"
              >
                <Mic className="h-4 w-4" />
                <span>Test Microphone</span>
              </button>
            )}
          </div>
        </div>

        {/* ======================================================= */}
        {/* SOURCE 2: Tab / System Audio (Interviewer Voice)        */}
        {/* ======================================================= */}
        <div className="p-6 rounded-xl border border-zinc-800 bg-zinc-900/40 space-y-5">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <div className="flex items-center gap-2">
              <div className={`p-2 rounded-lg ${tabStatus === 'recording' ? 'bg-purple-500/20 text-purple-400' : 'bg-zinc-800 text-zinc-400'}`}>
                <Volume2 className="h-4 w-4" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-zinc-200">Google Meet Tab Audio</h2>
                <p className="text-[11px] text-zinc-500">Captures interviewer via getDisplayMedia</p>
              </div>
            </div>

            <span className={`text-[10px] uppercase font-mono px-2 py-0.5 rounded border ${
              tabStatus === 'recording'
                ? 'bg-purple-950/40 text-purple-400 border-purple-800'
                : tabStatus === 'requesting'
                ? 'bg-blue-950/40 text-blue-400 border-blue-800 animate-pulse'
                : tabStatus === 'denied' || tabStatus === 'error'
                ? 'bg-red-950/40 text-red-400 border-red-800'
                : 'bg-zinc-800 text-zinc-400 border-zinc-700'
            }`}>
              {tabStatus}
            </span>
          </div>

          {/* Instructions Box */}
          <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800/80 text-[11px] text-zinc-400 space-y-1">
            <p className="font-semibold text-zinc-300">How to capture interviewer audio:</p>
            <ol className="list-decimal pl-4 space-y-0.5 text-zinc-400">
              <li>Click &quot;Test Tab Audio&quot; below.</li>
              <li>In the browser dialog, select the <strong>Chrome Tab</strong> containing your meeting.</li>
              <li>Make sure <strong className="text-emerald-400">&quot;Also share tab audio&quot;</strong> is checked.</li>
            </ol>
          </div>

          {/* Live Level Meter */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs text-zinc-400 font-mono">
              <span>Input Level</span>
              <span>{Math.round(tabLevel * 100)}%</span>
            </div>
            <div className="h-3 w-full bg-zinc-950 border border-zinc-800 rounded-full overflow-hidden p-0.5">
              <div
                className="h-full bg-gradient-to-r from-purple-500 via-pink-400 to-purple-300 rounded-full transition-all duration-75"
                style={{ width: `${Math.max(2, tabLevel * 100)}%` }}
              />
            </div>
          </div>

          {/* Error Message */}
          {tabError && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-red-950/40 border border-red-800/40 text-xs text-red-400">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold">Tab Audio Error: </span>
                {tabError}
              </div>
            </div>
          )}

          {/* Controls */}
          <div className="pt-2">
            {tabStatus === 'recording' ? (
              <button
                onClick={stopTab}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-red-950/60 hover:bg-red-900/80 text-red-300 border border-red-800/60 text-xs font-medium transition-colors"
              >
                <VolumeX className="h-4 w-4" />
                <span>Stop Tab Audio</span>
              </button>
            ) : (
              <button
                onClick={startTab}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-zinc-100 font-medium text-xs transition-all shadow-sm shadow-purple-600/20 active:scale-95"
              >
                <Volume2 className="h-4 w-4" />
                <span>Test Tab Audio</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Pipeline Status Summary */}
      <div className="p-5 rounded-xl border border-zinc-800 bg-zinc-900/20 space-y-3">
        <h3 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider flex items-center gap-2">
          <Layers className="h-4 w-4 text-emerald-400" />
          Pipeline Diagnostic Summary
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800 space-y-1">
            <span className="text-zinc-500 font-mono text-[10px]">Audio Format</span>
            <p className="font-semibold text-zinc-200">16kHz 16-bit Mono PCM</p>
          </div>
          <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800 space-y-1">
            <span className="text-zinc-500 font-mono text-[10px]">WebSocket Header</span>
            <p className="font-semibold text-zinc-200">0x01 (Mic) / 0x02 (Tab)</p>
          </div>
          <div className="p-3 rounded-lg bg-zinc-950 border border-zinc-800 space-y-1">
            <span className="text-zinc-500 font-mono text-[10px]">PCM Chunks Emitted</span>
            <p className="font-semibold text-emerald-400 font-mono">{chunkCount}</p>
          </div>
        </div>
      </div>

      {/* Known Platform Limitations Reminder */}
      <div className="flex items-start gap-3 p-4 rounded-xl border border-zinc-800/80 bg-zinc-900/20 text-xs text-zinc-400">
        <HelpCircle className="h-4 w-4 text-zinc-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="font-semibold text-zinc-300">Desktop Zoom & Teams Note:</p>
          <p>
            Standalone desktop apps (Zoom, Teams) do not route audio through browser tabs. For interviews conducted in those desktop apps, use Microphone-only capture or type questions directly using the manual question input in the workspace.
          </p>
        </div>
      </div>
    </div>
  );
}
