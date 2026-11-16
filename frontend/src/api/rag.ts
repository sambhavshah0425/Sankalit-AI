import { apiClient } from './client';
import type { RAGQueryResponse } from '../types/chat';
import type { HealthStatus, RAGStats } from '../types/document';

export interface StreamCallbacks {
  onMetadata?: (meta: {
    sources?: any[];
    detected_domain?: string;
    classification?: string;
    retrieval_status?: 'success' | 'insufficient_context' | 'error' | 'generating';
  }) => void;
  onDelta?: (delta: string) => void;
  onDone?: (data?: any) => void;
  onError?: (err: Error) => void;
}

export async function askKnowledgeBase(
  query: string,
  top_k = 3,
  min_score = 0.25
): Promise<RAGQueryResponse> {
  return apiClient<RAGQueryResponse>('/rag/query', {
    method: 'POST',
    body: JSON.stringify({
      query,
      top_k,
      min_score,
      detailed: true, // Request citation metadata for UI drawer
    }),
  });
}

export async function askKnowledgeBaseStream(
  query: string,
  callbacks: StreamCallbacks,
  top_k = 3,
  min_score = 0.25
): Promise<void> {
  const token = localStorage.getItem('sankalit_token');
  const response = await fetch('/rag/query/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      query,
      top_k,
      min_score,
      detailed: true,
    }),
  });

  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem('sankalit_token');
      throw new Error('Authentication expired. Please log in.');
    }
    const errText = await response.text();
    throw new Error(errText || `Server error: ${response.status}`);
  }

  if (!response.body) {
    throw new Error('No readable stream available in response.');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n\n');
    buffer = lines.pop() || '';

    for (const chunk of lines) {
      if (!chunk.trim()) continue;
      const eventMatch = chunk.match(/^event:\s*(\w+)/m);
      const dataMatch = chunk.match(/^data:\s*(.+)$/m);
      if (!eventMatch || !dataMatch) continue;

      const eventType = eventMatch[1];
      try {
        const payload = JSON.parse(dataMatch[1]);
        if (eventType === 'metadata') {
          callbacks.onMetadata?.(payload);
        } else if (eventType === 'delta') {
          callbacks.onDelta?.(payload.text || '');
        } else if (eventType === 'done') {
          callbacks.onDone?.(payload);
        } else if (eventType === 'error') {
          callbacks.onError?.(new Error(payload.error || 'Stream error'));
        }
      } catch (e) {
        console.error('Failed to parse SSE payload', e);
      }
    }
  }

  if (buffer.trim()) {
    const eventMatch = buffer.match(/^event:\s*(\w+)/m);
    const dataMatch = buffer.match(/^data:\s*(.+)$/m);
    if (eventMatch && dataMatch) {
      try {
        const payload = JSON.parse(dataMatch[1]);
        if (eventMatch[1] === 'delta') {
          callbacks.onDelta?.(payload.text || '');
        } else if (eventMatch[1] === 'done') {
          callbacks.onDone?.(payload);
        }
      } catch (e) {
        // ignore
      }
    }
  }
}

export async function checkOllamaHealth(): Promise<HealthStatus> {
  try {
    const res = await apiClient<{ status: string; model: string }>('/health/ollama', {
      method: 'GET',
    });
    return {
      status: res.status === 'connected' ? 'connected' : 'unavailable',
      model: res.model,
    };
  } catch (err: any) {
    return {
      status: 'unavailable',
      detail: err.message || 'Ollama unavailable',
    };
  }
}

export async function getRAGStats(): Promise<RAGStats> {
  return apiClient<RAGStats>('/rag/stats', {
    method: 'GET',
  });
}
