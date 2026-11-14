export interface SourceCitation {
  filename: string;
  chunk_index: number;
  similarity: number;
  document_title?: string;
  domain_slug?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources?: SourceCitation[];
  detected_domain?: string;
  retrieval_status?: 'success' | 'insufficient_context' | 'error';
  isError?: boolean;
}

export interface ConversationSession {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: Message[];
}

export interface RAGQueryResponse {
  answer: string;
  query?: string;
  question?: string;
  normalized_query?: string;
  classification?: string;
  detected_domain?: string;
  sources?: SourceCitation[];
  citations?: Array<{ filename: string; chunk_index: number }>;
  retrieval_status?: 'success' | 'insufficient_context' | 'error';
  model?: string;
}

