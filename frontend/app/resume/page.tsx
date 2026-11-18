'use client';

import React, { useEffect, useState, useRef } from 'react';
import Link from 'next/link';
import {
  FileText,
  Upload,
  ArrowLeft,
  Trash2,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Briefcase,
  Code2,
  GraduationCap,
  Award,
  FolderKanban,
  Eye,
  EyeOff,
} from 'lucide-react';
import { api } from '@/services/api';
import { ResumeDetail } from '@/types';

export default function ResumePage() {
  const [resume, setResume] = useState<ResumeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [showRawText, setShowRawText] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadResume = async () => {
    try {
      const res = await api.getActiveResume();
      setResume(res.resume);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load resume');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadResume();
  }, []);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const uploaded = await api.uploadResume(file);
      setResume(uploaded);
      setSuccessMsg(`Extracted ${uploaded.skills.length} skills and ${uploaded.projects.length} project lines from ${uploaded.filename}.`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Resume upload failed');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDelete = async () => {
    if (!resume) return;
    if (!confirm('Delete your active resume from local storage and database?')) return;
    setError(null);
    setSuccessMsg(null);
    try {
      await api.deleteResume(resume.id);
      setResume(null);
      setSuccessMsg('Resume deleted permanently.');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete resume');
    }
  };

  return (
    <div className="container mx-auto max-w-5xl px-6 py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link href="/" className="p-2 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-zinc-200">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
              <FileText className="h-5 w-5 text-emerald-400" />
              Resume Management
            </h1>
            <p className="text-xs text-zinc-400">
              AI answers use your verified resume facts strictly — never inventing experience or skills.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx"
            onChange={handleFileChange}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-medium text-xs transition-colors disabled:opacity-50"
          >
            {resume ? <RefreshCw className="h-3.5 w-3.5" /> : <Upload className="h-3.5 w-3.5" />}
            <span>{uploading ? 'Extracting...' : resume ? 'Replace Resume' : 'Upload Resume (PDF/DOCX)'}</span>
          </button>

          {resume && (
            <button
              onClick={handleDelete}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-red-950/50 hover:bg-red-900/70 text-red-300 border border-red-800/50 text-xs font-medium transition-colors"
            >
              <Trash2 className="h-3.5 w-3.5" />
              <span>Delete</span>
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3.5 rounded-lg bg-red-950/50 border border-red-800/50 text-xs text-red-300">
          <AlertCircle className="h-4 w-4 text-red-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {successMsg && (
        <div className="flex items-center gap-2 p-3.5 rounded-lg bg-emerald-950/40 border border-emerald-800/50 text-xs text-emerald-300">
          <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {loading ? (
        <div className="p-12 text-center text-sm text-zinc-500 border border-zinc-800 rounded-xl">
          Loading resume data...
        </div>
      ) : !resume ? (
        <div className="p-12 border border-dashed border-zinc-800 rounded-xl bg-zinc-900/20 text-center space-y-4">
          <div className="p-3 bg-zinc-800/60 rounded-full w-fit mx-auto text-emerald-400">
            <Upload className="h-6 w-6" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-200">No Resume Uploaded Yet</h3>
            <p className="text-xs text-zinc-500 max-w-md mx-auto mt-1">
              Upload your PDF or DOCX resume (max 10 MB). Skills, projects, experience, education, and certifications are extracted locally and injected into live interview answers.
            </p>
          </div>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 text-xs font-medium"
          >
            <Upload className="h-3.5 w-3.5" />
            <span>Select PDF or DOCX</span>
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Active File Banner */}
          <div className="p-4 rounded-xl border border-emerald-900/50 bg-emerald-950/15 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />
              <div>
                <p className="text-sm font-semibold text-zinc-100">{resume.filename}</p>
                <p className="text-xs text-zinc-400">
                  Active context • Uploaded {new Date(resume.uploaded_at).toLocaleString()} • {resume.extracted_text.length.toLocaleString()} characters
                </p>
              </div>
            </div>
            <button
              onClick={() => setShowRawText(!showRawText)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-xs text-zinc-300 hover:text-zinc-100"
            >
              {showRawText ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              <span>{showRawText ? 'Hide Raw Text' : 'Preview Raw Text'}</span>
            </button>
          </div>

          {/* Skills */}
          <div className="p-5 rounded-xl border border-zinc-800 bg-zinc-900/40 space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
              <Code2 className="h-4 w-4 text-emerald-400" />
              Identified Skills ({resume.skills.length})
            </h2>
            {resume.skills.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {resume.skills.map((skill) => (
                  <span
                    key={skill}
                    className="px-2.5 py-1 rounded-full text-xs bg-zinc-950 border border-zinc-800 text-emerald-300 font-mono"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-zinc-500">No explicit skills section parsed.</p>
            )}
          </div>

          {/* Grid for Experience, Projects, Education, Certifications */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div className="p-5 rounded-xl border border-zinc-800 bg-zinc-900/40 space-y-2.5">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                <Briefcase className="h-4 w-4 text-blue-400" />
                Work Experience ({resume.experience.length})
              </h2>
              {resume.experience.length > 0 ? (
                <ul className="space-y-1.5 text-xs text-zinc-300 list-disc pl-4">
                  {resume.experience.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-zinc-500">No work experience lines parsed.</p>
              )}
            </div>

            <div className="p-5 rounded-xl border border-zinc-800 bg-zinc-900/40 space-y-2.5">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                <FolderKanban className="h-4 w-4 text-purple-400" />
                Projects ({resume.projects.length})
              </h2>
              {resume.projects.length > 0 ? (
                <ul className="space-y-1.5 text-xs text-zinc-300 list-disc pl-4">
                  {resume.projects.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-zinc-500">No projects section parsed.</p>
              )}
            </div>

            <div className="p-5 rounded-xl border border-zinc-800 bg-zinc-900/40 space-y-2.5">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                <GraduationCap className="h-4 w-4 text-amber-400" />
                Education ({resume.education.length})
              </h2>
              {resume.education.length > 0 ? (
                <ul className="space-y-1.5 text-xs text-zinc-300 list-disc pl-4">
                  {resume.education.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-zinc-500">No education section parsed.</p>
              )}
            </div>

            <div className="p-5 rounded-xl border border-zinc-800 bg-zinc-900/40 space-y-2.5">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
                <Award className="h-4 w-4 text-teal-400" />
                Certifications ({resume.certifications.length})
              </h2>
              {resume.certifications.length > 0 ? (
                <ul className="space-y-1.5 text-xs text-zinc-300 list-disc pl-4">
                  {resume.certifications.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-zinc-500">No certifications section parsed.</p>
              )}
            </div>
          </div>

          {showRawText && (
            <div className="p-5 rounded-xl border border-zinc-800 bg-zinc-950 space-y-2">
              <h3 className="text-xs font-mono uppercase text-zinc-400">Extracted Text Preview</h3>
              <pre className="text-xs text-zinc-300 whitespace-pre-wrap font-mono max-h-96 overflow-y-auto leading-relaxed">
                {resume.extracted_text}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
