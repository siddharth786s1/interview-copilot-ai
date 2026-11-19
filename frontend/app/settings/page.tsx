'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Save, Sliders, CheckCircle2, Trash2, Sparkles, Plus, X } from 'lucide-react';
import { api } from '@/services/api';
import { AppSettings, FewShotExample } from '@/types';

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [purgeMsg, setPurgeMsg] = useState<string | null>(null);

  useEffect(() => {
    api.getSettings().then(setSettings).catch(console.error);
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!settings) return;
    setSaving(true);
    try {
      const cleanedExamples = (settings.few_shot_examples || [])
        .map((ex) => ({
          question: ex.question.trim(),
          ideal_answer: ex.ideal_answer.trim(),
        }))
        .filter((ex) => ex.question.length > 0 && ex.ideal_answer.length > 0);

      const updated = await api.updateSettings({
        ...settings,
        few_shot_examples: cleanedExamples,
      });
      setSettings(updated);
      if (typeof document !== 'undefined') {
        document.documentElement.classList.toggle('dark', updated.theme === 'dark');
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      alert(`Failed to save settings: ${err}`);
    } finally {
      setSaving(false);
    }
  };

  const handleAddExample = () => {
    if (!settings) return;
    const current = settings.few_shot_examples || [];
    if (current.length >= 8) return;
    setSettings({
      ...settings,
      few_shot_examples: [...current, { question: '', ideal_answer: '' }],
    });
  };

  const handleUpdateExample = (index: number, field: keyof FewShotExample, value: string) => {
    if (!settings) return;
    const next = [...(settings.few_shot_examples || [])];
    next[index] = { ...next[index], [field]: value };
    setSettings({ ...settings, few_shot_examples: next });
  };

  const handleRemoveExample = (index: number) => {
    if (!settings) return;
    const next = (settings.few_shot_examples || []).filter((_, i) => i !== index);
    setSettings({ ...settings, few_shot_examples: next });
  };

  const handleApplyRetention = async () => {
    if (!settings) return;
    setPurgeMsg(null);
    try {
      await api.updateSettings({ retention_days: settings.retention_days });
      const res = await api.purgeRetention();
      setPurgeMsg(
        res.retention_days === null
          ? 'Retention is set to Forever — 0 sessions deleted.'
          : `Retention policy (${res.retention_days} days) applied: deleted ${res.deleted_sessions} expired session(s).`
      );
    } catch (err) {
      alert(`Retention purge failed: ${err}`);
    }
  };

  if (!settings) {
    return (
      <div className="container mx-auto max-w-3xl px-6 py-8 text-zinc-500 text-sm">
        Loading settings...
      </div>
    );
  }

  return (
    <div className="container mx-auto max-w-3xl px-6 py-8 space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/" className="p-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <Sliders className="h-5 w-5 text-emerald-400" />
            Application Settings
          </h1>
          <p className="text-xs text-zinc-400">Configure speech recognition, AI answer engine, and display preferences.</p>
        </div>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* STT Configuration */}
        <div className="p-6 rounded-xl border border-zinc-800 bg-zinc-900/40 space-y-4">
          <h2 className="text-sm font-semibold text-zinc-200 border-b border-zinc-800 pb-2">
            Speech Recognition (STT)
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">STT Provider</label>
              <select
                value={settings.stt_provider}
                onChange={(e) => setSettings({ ...settings, stt_provider: e.target.value })}
                className="w-full px-3 py-2 text-sm bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-200 focus:outline-none focus:border-emerald-500"
              >
                <option value="whisper">faster-whisper (Local, $0)</option>
                <option value="deepgram">Deepgram Nova-2 (Cloud, Low Latency)</option>
                <option value="openai_whisper">OpenAI Whisper API</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">Whisper Model Size</label>
              <select
                value={settings.whisper_model_size}
                onChange={(e) => setSettings({ ...settings, whisper_model_size: e.target.value })}
                className="w-full px-3 py-2 text-sm bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-200 focus:outline-none focus:border-emerald-500"
              >
                <option value="tiny">tiny (fastest, lowest accuracy)</option>
                <option value="base">base (recommended CPU balance)</option>
                <option value="small">small</option>
                <option value="medium">medium</option>
                <option value="large-v3">large-v3</option>
              </select>
            </div>
          </div>
        </div>

        {/* LLM Configuration */}
        <div className="p-6 rounded-xl border border-zinc-800 bg-zinc-900/40 space-y-4">
          <h2 className="text-sm font-semibold text-zinc-200 border-b border-zinc-800 pb-2">
            AI Answer Generation (LLM)
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">LLM Provider</label>
              <select
                value={settings.llm_provider}
                onChange={(e) => setSettings({ ...settings, llm_provider: e.target.value })}
                className="w-full px-3 py-2 text-sm bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-200 focus:outline-none focus:border-emerald-500"
              >
                <option value="gemini">Google Gemini (Default, Free Tier)</option>
                <option value="openai">OpenAI</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">Default Model</label>
              <input
                type="text"
                value={settings.llm_model}
                onChange={(e) => setSettings({ ...settings, llm_model: e.target.value })}
                className="w-full px-3 py-2 text-sm bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-200 focus:outline-none focus:border-emerald-500"
                placeholder="gemini-3.5-flash-lite or gpt-4o-mini"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">Default Answer Style</label>
              <select
                value={settings.default_answer_style}
                onChange={(e) => setSettings({ ...settings, default_answer_style: e.target.value as AppSettings['default_answer_style'] })}
                className="w-full px-3 py-2 text-sm bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-200 focus:outline-none focus:border-emerald-500"
              >
                <option value="short">SHORT (2–4 concise sentences)</option>
                <option value="detailed">DETAILED (Full technical explanation)</option>
                <option value="practical">PRACTICAL (Worked example)</option>
                <option value="stepbystep">STEP-BY-STEP (Sequential process)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">Technical Depth</label>
              <select
                value={settings.default_technical_depth}
                onChange={(e) => setSettings({ ...settings, default_technical_depth: e.target.value as AppSettings['default_technical_depth'] })}
                className="w-full px-3 py-2 text-sm bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-200 focus:outline-none focus:border-emerald-500"
              >
                <option value="low">Low (High-level overview)</option>
                <option value="medium">Medium (Standard engineering)</option>
                <option value="high">High (Deep architectural & internals)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Gemini Structured Output & Personal Coaching / Training Profile */}
        <div className="p-6 rounded-xl border border-emerald-900/40 bg-zinc-900/40 space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 pb-2">
            <div>
              <h2 className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-emerald-400" />
                <span>Gemini Conversational Co-pilot & Coaching Profile</span>
              </h2>
              <p className="text-[11px] text-zinc-400 mt-0.5">
                Train Gemini to listen continuously, responding to scenarios and discussion points with structured, role-tailored answers.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <label className="inline-flex items-center gap-2 cursor-pointer text-xs text-zinc-200 bg-zinc-950 px-3 py-1.5 rounded-lg border border-zinc-800 hover:border-zinc-700">
                <input
                  type="checkbox"
                  checked={settings.conversation_mode ?? true}
                  onChange={(e) => setSettings({ ...settings, conversation_mode: e.target.checked })}
                  className="accent-indigo-500 h-3.5 w-3.5"
                />
                <span className="font-medium text-indigo-300">Conversational Mode</span>
              </label>
              <label className="inline-flex items-center gap-2 cursor-pointer text-xs text-zinc-200 bg-zinc-950 px-3 py-1.5 rounded-lg border border-zinc-800 hover:border-zinc-700">
                <input
                  type="checkbox"
                  checked={settings.structured_output ?? true}
                  onChange={(e) => setSettings({ ...settings, structured_output: e.target.checked })}
                  className="accent-emerald-500 h-3.5 w-3.5"
                />
                <span className="font-medium">Structured Format</span>
              </label>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">
                Target Interview Role
              </label>
              <input
                type="text"
                value={settings.target_role || ''}
                onChange={(e) => setSettings({ ...settings, target_role: e.target.value })}
                placeholder="e.g., Senior Application Security / SAP Security Engineer"
                className="w-full px-3 py-2 text-sm bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">
                Custom Coaching Instructions
              </label>
              <textarea
                rows={3}
                value={settings.custom_instructions || ''}
                onChange={(e) => setSettings({ ...settings, custom_instructions: e.target.value })}
                placeholder="e.g., Always lead with a 1-sentence Direct Answer, use STAR format for behavioral questions, highlight OWASP / SAP T-codes where relevant, keep bullets under 15 words."
                className="w-full px-3 py-2 text-sm bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500 resize-y"
              />
            </div>

            {/* Few-Shot Example Q&A Pairs */}
            <div className="space-y-3 pt-1">
              <div className="flex items-center justify-between">
                <div>
                  <label className="block text-xs font-medium text-zinc-300">
                    Few-Shot Training Examples (Sample Q&amp;A Pairs)
                  </label>
                  <p className="text-[11px] text-zinc-500">
                    Show Gemini 1–3 examples of how you like answers structured. Injected automatically into every prompt.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleAddExample}
                  disabled={(settings.few_shot_examples || []).length >= 8}
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-emerald-300 border border-zinc-700 text-xs font-medium disabled:opacity-40"
                >
                  <Plus className="h-3.5 w-3.5" />
                  <span>Add Example</span>
                </button>
              </div>

              {(settings.few_shot_examples || []).length === 0 ? (
                <div className="p-4 rounded-lg border border-dashed border-zinc-800 bg-zinc-950/40 text-xs text-zinc-500 text-center">
                  No custom examples added yet. Built-in structured headings (<strong>Direct Answer</strong>, <strong>Key Points</strong>, <strong>Practical Example</strong>, <strong>Follow-up Tip</strong>) are active by default.
                </div>
              ) : (
                <div className="space-y-3">
                  {(settings.few_shot_examples || []).map((ex, idx) => (
                    <div
                      key={idx}
                      className="p-3.5 rounded-lg border border-zinc-800 bg-zinc-950/60 space-y-2.5"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-mono uppercase text-emerald-400">
                          Example #{idx + 1}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleRemoveExample(idx)}
                          className="text-zinc-500 hover:text-red-400 p-0.5"
                          title="Remove example"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                      <input
                        type="text"
                        value={ex.question}
                        onChange={(e) => handleUpdateExample(idx, 'question', e.target.value)}
                        placeholder="Sample Interview Question (e.g., How do you prevent SQL injection?)"
                        className="w-full px-3 py-1.5 text-xs bg-zinc-900 border border-zinc-800 rounded-md text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500"
                      />
                      <textarea
                        rows={3}
                        value={ex.ideal_answer}
                        onChange={(e) => handleUpdateExample(idx, 'ideal_answer', e.target.value)}
                        placeholder="**Direct Answer**: Use parameterized queries...&#10;**Key Points**:&#10;- Separate SQL code from user data&#10;- Apply least-privilege DB roles"
                        className="w-full px-3 py-1.5 text-xs bg-zinc-900 border border-zinc-800 rounded-md text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500 resize-y"
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Appearance, Language & Data Retention */}
        <div className="p-6 rounded-xl border border-zinc-800 bg-zinc-900/40 space-y-4">
          <h2 className="text-sm font-semibold text-zinc-200 border-b border-zinc-800 pb-2">
            Appearance, Language & Local Data Retention
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">Default Language</label>
              <select
                value={settings.language}
                onChange={(e) => setSettings({ ...settings, language: e.target.value })}
                className="w-full px-3 py-2 text-sm bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-200 focus:outline-none focus:border-emerald-500"
              >
                <option value="en">English (en)</option>
                <option value="auto">Auto-detect</option>
                <option value="es">Spanish (es)</option>
                <option value="fr">French (fr)</option>
                <option value="de">German (de)</option>
                <option value="hi">Hindi (hi)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">Theme</label>
              <select
                value={settings.theme}
                onChange={(e) => setSettings({ ...settings, theme: e.target.value as 'dark' | 'light' })}
                className="w-full px-3 py-2 text-sm bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-200 focus:outline-none focus:border-emerald-500"
              >
                <option value="dark">Dark (Default)</option>
                <option value="light">Light</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">Session Retention</label>
              <select
                value={settings.retention_days === null ? 'forever' : String(settings.retention_days)}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    retention_days: e.target.value === 'forever' ? null : Number(e.target.value),
                  })
                }
                className="w-full px-3 py-2 text-sm bg-zinc-950 border border-zinc-800 rounded-lg text-zinc-200 focus:outline-none focus:border-emerald-500"
              >
                <option value="forever">Keep Forever</option>
                <option value="7">Delete after 7 days</option>
                <option value="30">Delete after 30 days</option>
                <option value="90">Delete after 90 days</option>
              </select>
            </div>
          </div>

          <div className="pt-2 flex flex-wrap items-center justify-between gap-3 border-t border-zinc-800/80">
            <span className="text-xs text-zinc-400">
              {purgeMsg || 'Manually enforce retention policy to delete expired local sessions and transcripts.'}
            </span>
            <button
              type="button"
              onClick={handleApplyRetention}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 text-xs font-medium"
            >
              <Trash2 className="h-3.5 w-3.5 text-amber-400" />
              <span>Apply Retention Policy Now</span>
            </button>
          </div>
        </div>

        {/* Save button */}
        <div className="flex items-center justify-between pt-2">
          {saved ? (
            <div className="flex items-center gap-2 text-xs font-medium text-emerald-400">
              <CheckCircle2 className="h-4 w-4" />
              <span>Settings saved successfully</span>
            </div>
          ) : (
            <span className="text-xs text-zinc-500">API keys must be placed in .env file</span>
          )}

          <button
            type="submit"
            disabled={saving}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-medium text-sm transition-all shadow-sm shadow-emerald-500/20 active:scale-95 disabled:opacity-50"
          >
            <Save className="h-4 w-4" />
            <span>{saving ? 'Saving...' : 'Save Settings'}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
