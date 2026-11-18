import {
  Session,
  SessionCreateInput,
  SessionUpdateInput,
  AppSettings,
  TranscriptSegment,
  DetectedQuestion,
  GeneratedAnswer,
  ScreenAnalysisResponse,
  ActiveResumeResponse,
  ResumeDetail,
  KBDocumentSummary,
  KBDocumentDetail,
  KBSearchResult,
  HistorySessionItem,
  HistorySessionDetail,
  HistorySearchHit,
  MockSessionSummary,
  MockSessionDetail,
  MockExchange,
  MockPerformanceSummary,
} from '@/types';

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

class ApiClient {
  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    const res = await fetch(url, { ...options, headers });
    if (!res.ok) {
      let errorMsg = `API error (${res.status}): ${res.statusText}`;
      try {
        const errorJson = await res.json();
        if (errorJson.detail) {
          errorMsg = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
        }
      } catch {
        // use default errorMsg
      }
      throw new Error(errorMsg);
    }

    if (res.status === 204) {
      return {} as T;
    }
    return res.json();
  }

  // Health
  async getHealth(): Promise<{ status: string; version: string; timestamp: string; service: string }> {
    return this.request('/health');
  }

  // Sessions
  async createSession(data: SessionCreateInput): Promise<Session> {
    return this.request('/api/sessions/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async listSessions(params?: { type?: string; status?: string }): Promise<Session[]> {
    const query = new URLSearchParams();
    if (params?.type) query.set('type', params.type);
    if (params?.status) query.set('status', params.status);
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request(`/api/sessions/${qs}`);
  }

  async getSession(id: string): Promise<Session> {
    return this.request(`/api/sessions/${id}`);
  }

  async getSessionTranscript(id: string): Promise<TranscriptSegment[]> {
    return this.request(`/api/sessions/${id}/transcript`);
  }

  async getSessionQuestions(id: string): Promise<DetectedQuestion[]> {
    return this.request(`/api/sessions/${id}/questions`);
  }

  async createManualQuestion(
    sessionId: string,
    questionText: string,
    style?: string
  ): Promise<DetectedQuestion> {
    return this.request(`/api/sessions/${sessionId}/questions`, {
      method: 'POST',
      body: JSON.stringify({
        question_text: questionText,
        question_type: 'manual',
        style,
        auto_generate: true,
      }),
    });
  }

  async getSessionAnswers(sessionId: string): Promise<GeneratedAnswer[]> {
    return this.request(`/api/sessions/${sessionId}/answers`);
  }

  async generateAnswer(
    sessionId: string,
    questionId: string,
    options: {
      style?: 'short' | 'detailed' | 'practical' | 'stepbystep';
      technical_depth?: 'low' | 'medium' | 'high';
      expand?: boolean;
    } = {}
  ): Promise<GeneratedAnswer> {
    return this.request(`/api/sessions/${sessionId}/questions/${questionId}/answer`, {
      method: 'POST',
      body: JSON.stringify(options),
    });
  }

  async analyzeScreen(
    sessionId: string,
    imageBlob: Blob,
    options: {
      prompt?: string;
      style?: 'short' | 'detailed' | 'practical' | 'stepbystep';
      autoMode?: boolean;
    } = {}
  ): Promise<ScreenAnalysisResponse> {
    const form = new FormData();
    form.append('image', imageBlob, 'screen-capture.jpg');
    if (options.prompt && options.prompt.trim()) {
      form.append('prompt', options.prompt.trim());
    }
    if (options.style) {
      form.append('style', options.style);
    }
    form.append('auto_mode', String(Boolean(options.autoMode)));

    const res = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/analyze-screen`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      let msg = `Screen analysis failed (${res.status})`;
      try {
        const j = await res.json();
        msg = j.detail?.message || (typeof j.detail === 'string' ? j.detail : msg);
      } catch {
        // fallback
      }
      throw new Error(msg);
    }
    return res.json();
  }

  async updateSession(id: string, data: SessionUpdateInput): Promise<Session> {
    return this.request(`/api/sessions/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async deleteSession(id: string): Promise<void> {
    return this.request(`/api/sessions/${id}`, {
      method: 'DELETE',
    });
  }

  // Settings
  async getSettings(): Promise<AppSettings> {
    return this.request('/api/settings/');
  }

  async updateSettings(data: Partial<AppSettings>): Promise<AppSettings> {
    return this.request('/api/settings/', {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  // Resume Management
  async getActiveResume(): Promise<ActiveResumeResponse> {
    return this.request('/api/resume/');
  }

  async uploadResume(file: File): Promise<ResumeDetail> {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${API_BASE_URL}/api/resume/upload`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      let msg = `Upload failed (${res.status})`;
      try {
        const j = await res.json();
        msg = j.detail?.message || (typeof j.detail === 'string' ? j.detail : msg);
      } catch {
        // fallback
      }
      throw new Error(msg);
    }
    return res.json();
  }

  async deleteResume(id: string): Promise<void> {
    return this.request(`/api/resume/${id}`, { method: 'DELETE' });
  }

  // Knowledge Base
  async getKBCategories(): Promise<string[]> {
    return this.request('/api/knowledge-base/categories');
  }

  async listKBDocuments(category?: string): Promise<KBDocumentSummary[]> {
    const qs = category && category !== 'all' ? `?category=${encodeURIComponent(category)}` : '';
    return this.request(`/api/knowledge-base/${qs}`);
  }

  async getKBDocument(id: string): Promise<KBDocumentDetail> {
    return this.request(`/api/knowledge-base/${id}`);
  }

  async uploadKBDocument(file: File, category: string): Promise<KBDocumentSummary> {
    const form = new FormData();
    form.append('file', file);
    form.append('category', category);
    const res = await fetch(`${API_BASE_URL}/api/knowledge-base/upload`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) {
      let msg = `Upload failed (${res.status})`;
      try {
        const j = await res.json();
        msg = j.detail?.message || (typeof j.detail === 'string' ? j.detail : msg);
      } catch {
        // fallback
      }
      throw new Error(msg);
    }
    return res.json();
  }

  async searchKB(query: string, category?: string): Promise<KBSearchResult[]> {
    const params = new URLSearchParams({ q: query, top_k: '5' });
    if (category && category !== 'all') params.set('category', category);
    return this.request(`/api/knowledge-base/search?${params.toString()}`);
  }

  async deleteKBDocument(id: string): Promise<void> {
    return this.request(`/api/knowledge-base/${id}`, { method: 'DELETE' });
  }

  // Interview History
  async listHistory(type?: string): Promise<HistorySessionItem[]> {
    const qs = type && type !== 'all' ? `?type=${encodeURIComponent(type)}` : '';
    return this.request(`/api/history/${qs}`);
  }

  async getHistoryDetail(sessionId: string): Promise<HistorySessionDetail> {
    return this.request(`/api/history/${sessionId}`);
  }

  async searchHistory(query: string): Promise<HistorySearchHit[]> {
    return this.request(`/api/history/search?q=${encodeURIComponent(query)}`);
  }

  getHistoryExportUrl(sessionId: string, format: 'markdown' | 'json'): string {
    return `${API_BASE_URL}/api/history/${sessionId}/export?format=${format}`;
  }

  async deleteHistorySession(sessionId: string): Promise<void> {
    return this.request(`/api/history/${sessionId}`, { method: 'DELETE' });
  }

  async purgeSessionTranscript(sessionId: string): Promise<void> {
    return this.request(`/api/history/${sessionId}/transcript`, { method: 'DELETE' });
  }

  async purgeRetention(daysOverride?: number): Promise<{
    retention_days: number | null;
    deleted_sessions: number;
    cutoff: string | null;
  }> {
    const qs = daysOverride !== undefined ? `?days_override=${daysOverride}` : '';
    return this.request(`/api/history/purge-retention${qs}`, { method: 'POST' });
  }

  // Mock Interview (Isolated Data Path)
  async getMockPerformance(): Promise<MockPerformanceSummary> {
    return this.request('/api/mock/performance');
  }

  async listMockSessions(): Promise<MockSessionSummary[]> {
    return this.request('/api/mock/sessions');
  }

  async createMockSession(topic: string): Promise<MockSessionDetail> {
    return this.request('/api/mock/sessions', {
      method: 'POST',
      body: JSON.stringify({ topic }),
    });
  }

  async getMockSession(id: string): Promise<MockSessionDetail> {
    return this.request(`/api/mock/sessions/${id}`);
  }

  async nextMockQuestion(mockSessionId: string): Promise<MockExchange> {
    return this.request(`/api/mock/sessions/${mockSessionId}/next-question`, {
      method: 'POST',
    });
  }

  async submitMockAnswer(
    mockSessionId: string,
    exchangeId: string,
    userAnswer: string
  ): Promise<MockExchange> {
    return this.request(`/api/mock/sessions/${mockSessionId}/exchanges/${exchangeId}/answer`, {
      method: 'POST',
      body: JSON.stringify({ user_answer: userAnswer }),
    });
  }

  async endMockSession(mockSessionId: string): Promise<MockSessionSummary> {
    return this.request(`/api/mock/sessions/${mockSessionId}/end`, { method: 'POST' });
  }

  async deleteMockSession(mockSessionId: string): Promise<void> {
    return this.request(`/api/mock/sessions/${mockSessionId}`, { method: 'DELETE' });
  }

  async transcribeMockAudio(pcmBuffer: ArrayBuffer): Promise<{ text: string }> {
    const res = await fetch(`${API_BASE_URL}/api/mock/transcribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/octet-stream' },
      body: pcmBuffer,
    });
    if (!res.ok) {
      throw new Error(`Transcription failed (${res.status})`);
    }
    return res.json();
  }
}

export const api = new ApiClient();
