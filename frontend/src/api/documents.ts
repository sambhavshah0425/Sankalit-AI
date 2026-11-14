import { apiClient } from './client';
import type { DocumentItem } from '../types/document';

export async function fetchDocuments(): Promise<DocumentItem[]> {
  const res = await apiClient<{ documents: DocumentItem[]; count: number }>('/documents', {
    method: 'GET',
  });
  return res.documents;
}

export async function uploadDocument(
  file: File,
  visibility = 'COMPANY',
  confidentialityLevel = 'INTERNAL'
): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('visibility', visibility);
  formData.append('confidentiality_level', confidentialityLevel);

  return apiClient('/documents/upload', {
    method: 'POST',
    body: formData,
  });
}

export async function deleteDocument(documentId: number): Promise<void> {
  await apiClient(`/documents/${documentId}`, {
    method: 'DELETE',
  });
}
