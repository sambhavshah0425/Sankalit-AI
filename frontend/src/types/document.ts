export interface DocumentItem {
  id: number;
  filename: string;
  document_title?: string;
  file_type: string;
  character_count: number;
  total_chunks?: number;
  created_at: string;
  visibility: string;
  confidentiality_level: string;
  classification_status: string;
  domain_id?: number;
  category_id?: number;
  project_name?: string;
}

export interface RAGStats {
  total_indexed_documents: number;
  total_stored_chunks: number;
  total_registered_users: number;
  total_departments: number;
  database_path: string;
  embedding_model: string;
  embedding_dimensions: number;
  chat_model: string;
}

export interface HealthStatus {
  status: 'connected' | 'unavailable' | 'checking';
  model?: string;
  detail?: string;
}

