import { apiClient } from './client';
import type { RAGQueryResponse } from '../types/chat';
import type { HealthStatus, RAGStats } from '../types/document';

export async function askKnowledgeBase(
  query: string,
  top_k = 10,
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
