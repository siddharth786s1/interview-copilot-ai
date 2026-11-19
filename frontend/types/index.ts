export type SessionType =
  | 'technical'
  | 'hr'
  | 'behavioral'
  | 'general'
  | 'mock'
  | 'custom';

export type SessionStatus = 'created' | 'active' | 'paused' | 'ended';

export interface Session {
  id: string;
  title: string;
  type: SessionType;
  status: SessionStatus;
  created_at: string;
  ended_at: string | null;
  duration_seconds: number | null;
}

export interface SessionCreateInput {
  title: string;
  type: SessionType;
  settings?: Record<string, unknown>;
}

export interface SessionUpdateInput {
  title?: string;
  status?: SessionStatus;
}

export interface FewShotExample {
  question: string;
  ideal_answer: string;
}

export interface AppSettings {
  id: number;
  stt_provider: string;
  llm_provider: string;
  llm_model: string;
  whisper_model_size: string;
  language: string;
  default_answer_style: 'short' | 'detailed' | 'practical' | 'stepbystep';
  default_technical_depth: 'low' | 'medium' | 'high';
  structured_output: boolean;
  conversation_mode: boolean;
  target_role: string;
  custom_instructions: string;
  few_shot_examples: FewShotExample[];
  theme: 'dark' | 'light';
  retention_days: number | null;
  updated_at: string;
}

export interface TranscriptSegment {
  id: string;
  session_id: string;
  source: 'tab' | 'mic' | 'manual';
  speaker_label?: string | null;
  text: string;
  is_final: boolean;
  timestamp: string;
  sequence: number;
}

export interface DetectedQuestion {
  id: string;
  session_id: string;
  question_text: string;
  question_type: 'direct' | 'indirect' | 'technical' | 'followup' | 'manual' | 'screen' | 'conversation';
  detected_at: string;
  answered: boolean;
}

export interface GeneratedAnswer {
  id: string;
  question_id: string;
  style: 'short' | 'detailed' | 'practical' | 'stepbystep';
  answer_text: string;
  model_used: string;
  generated_at: string;
  generation_time_ms: number;
  ttft_ms?: number | null;
  keywords?: string[];
  needs_customization?: boolean;
}

export interface ScreenAnalysisResponse {
  actionable: boolean;
  topic: string;
  screen_summary: string;
  question: DetectedQuestion | null;
  answer: GeneratedAnswer | null;
  analysis_time_ms: number;
}

export interface ResumeDetail {
  id: string;
  filename: string;
  uploaded_at: string;
  extracted_text: string;
  skills: string[];
  experience: string[];
  projects: string[];
  education: string[];
  certifications: string[];
  is_active: boolean;
}

export interface ActiveResumeResponse {
  has_resume: boolean;
  resume: ResumeDetail | null;
}

export interface KBDocumentSummary {
  id: string;
  filename: string;
  category: string;
  uploaded_at: string;
  chunk_count: number;
  char_count: number;
  preview: string;
}

export interface KBDocumentDetail extends KBDocumentSummary {
  extracted_text: string;
}

export interface KBSearchResult {
  document_id: string;
  filename: string;
  category: string;
  excerpt: string;
  score: number;
}

export interface HistorySessionItem {
  id: string;
  title: string;
  type: string;
  status: string;
  created_at: string;
  ended_at: string | null;
  duration_seconds: number | null;
  transcript_count: number;
  question_count: number;
  answer_count: number;
}

export interface HistoryQAItem {
  question_id: string;
  question_text: string;
  question_type: string;
  detected_at: string;
  answers: Array<{
    id: string;
    style: string;
    answer_text: string;
    model_used: string;
    generated_at: string;
    generation_time_ms: number;
  }>;
}

export interface HistorySessionDetail {
  session: HistorySessionItem;
  transcript: Array<{
    id: string;
    source: string;
    speaker_label: string;
    text: string;
    timestamp: string;
    sequence: number;
  }>;
  qa_pairs: HistoryQAItem[];
}

export interface HistorySearchHit {
  session_id: string;
  session_title: string;
  session_type: string;
  session_created_at: string;
  question_id: string;
  question_text: string;
  question_type: string;
  detected_at: string;
  latest_answer: string | null;
}

export interface MockEvaluation {
  score: number;
  feedback: string;
  missing_concepts: string[];
  improved_answer: string;
  evaluation_mode: 'llm' | 'local_rubric';
}

export interface MockExchange {
  id: string;
  mock_session_id: string;
  question_text: string;
  user_answer: string | null;
  evaluation: MockEvaluation | null;
  created_at: string;
}

export interface MockSessionSummary {
  id: string;
  topic: string;
  created_at: string;
  ended_at: string | null;
  question_count: number;
  answered_count: number;
  average_score: number | null;
}

export interface MockSessionDetail {
  session: MockSessionSummary;
  exchanges: MockExchange[];
}

export interface MockPerformanceSummary {
  total_sessions: number;
  total_evaluated: number;
  overall_average_score: number | null;
  by_topic: Array<{ topic: string; sessions: number; average_score: number }>;
  score_trend: Array<{
    mock_session_id: string;
    topic: string;
    date: string;
    average_score: number;
    answered_count: number;
  }>;
}
