import React, { useEffect, useState } from 'react';
import {
  ArrowLeft,
  FileText,
  Trash,
  UploadSimple,
  CheckCircle,
  WarningCircle,
  Database,
} from '@phosphor-icons/react';
import { deleteDocument, fetchDocuments, uploadDocument } from '../../api/documents';
import { getRAGStats } from '../../api/rag';
import type { DocumentItem, RAGStats } from '../../types/document';
import { useAuth } from '../../context/AuthContext';

interface KnowledgeAdminProps {
  onBackToChat: () => void;
}

export const KnowledgeAdmin: React.FC<KnowledgeAdminProps> = ({ onBackToChat }) => {
  const { hasPermission } = useAuth();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [stats, setStats] = useState<RAGStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const canUpload = hasPermission('document:upload');
  const canDelete = hasPermission('document:delete');

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [docs, ragStats] = await Promise.all([
        fetchDocuments().catch(() => []),
        getRAGStats().catch(() => null),
      ]);
      setDocuments(docs);
      setStats(ragStats);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadStatus(null);
    try {
      await uploadDocument(file);
      setUploadStatus({
        type: 'success',
        message: `Successfully ingested and embedded "${file.name}" into local SQLite.`,
      });
      loadData();
    } catch (err: any) {
      setUploadStatus({
        type: 'error',
        message: err.message || 'Document ingestion failed.',
      });
    } finally {
      setIsUploading(false);
      e.target.value = '';
    }
  };

  const handleDelete = async (docId: number, filename: string) => {
    if (!window.confirm(`Permanently remove "${filename}" and all its chunk embeddings?`)) return;
    try {
      await deleteDocument(docId);
      loadData();
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-6 max-w-5xl w-full mx-auto animate-message-in">
      {/* Top Header */}
      <div className="flex items-center justify-between pb-4 mb-6 border-b border-[#383838]">
        <div className="flex items-center gap-3">
          <button
            onClick={onBackToChat}
            className="p-2 rounded-lg text-[#9E9E9E] hover:text-[#FFFFFF] hover:bg-[#333333] transition-colors"
            title="Return to Chat"
          >
            <ArrowLeft size={18} />
          </button>
          <div>
            <h1 className="text-xl font-bold text-[#FFFFFF]">Knowledge Base Administration</h1>
            <p className="text-xs text-[#C8C8C8] mt-0.5">
              Manage indexed engineering documentation, access policies, and vector embeddings
            </p>
          </div>
        </div>

        <button
          onClick={loadData}
          className="btn-charcoal text-xs px-3.5 py-1.5"
          disabled={isLoading}
        >
          Refresh
        </button>
      </div>

      {/* RAG Platform Statistics Banner */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          <div className="p-4 rounded-xl bg-[#222222] border border-[#383838]">
            <div className="text-[10px] uppercase font-bold text-[#888888] mb-1 tracking-wider">Indexed Documents</div>
            <div className="text-xl font-bold text-[#FFFFFF]">{stats.total_indexed_documents}</div>
          </div>
          <div className="p-4 rounded-xl bg-[#222222] border border-[#383838]">
            <div className="text-[10px] uppercase font-bold text-[#888888] mb-1 tracking-wider">Stored Chunks</div>
            <div className="text-xl font-bold text-[#F5A623]">{stats.total_stored_chunks}</div>
          </div>
          <div className="p-4 rounded-xl bg-[#222222] border border-[#383838]">
            <div className="text-[10px] uppercase font-bold text-[#888888] mb-1 tracking-wider">Embedding Dimensions</div>
            <div className="text-xl font-bold text-[#FFFFFF] font-technical">{stats.embedding_dimensions}d</div>
          </div>
          <div className="p-4 rounded-xl bg-[#222222] border border-[#383838]">
            <div className="text-[10px] uppercase font-bold text-[#888888] mb-1 tracking-wider">Embedding Model</div>
            <div className="text-sm font-semibold text-[#D4D4D4] truncate font-technical">{stats.embedding_model}</div>
          </div>
        </div>
      )}

      {/* Upload Document Box */}
      {canUpload && (
        <div className="mb-8 p-6 rounded-xl bg-[#222222] border border-[#383838]">
          <h2 className="text-base font-bold text-[#FFFFFF] mb-1 flex items-center gap-2">
            <UploadSimple size={18} className="text-[#F5A623]" weight="bold" />
            Ingest New Document
          </h2>
          <p className="text-xs text-[#C8C8C8] mb-4">
            Upload PDF or DOCX files. Documents are extracted, chunked, and embedded locally into SQLite via nomic-embed-text.
          </p>

          <label className="flex flex-col items-center justify-center p-6 border-2 border-dashed border-[#3D3D3D] hover:border-[#F5A623] rounded-xl cursor-pointer bg-[#1E1E1E] transition-colors">
            <Database size={28} className="text-[#888888] mb-2" />
            <span className="text-sm font-medium text-[#FFFFFF]">
              {isUploading ? 'Extracting, chunking and embedding...' : 'Click to select document'}
            </span>
            <span className="text-xs text-[#888888] mt-1 font-technical">PDF or DOCX up to 50 MB</span>
            <input
              type="file"
              accept=".pdf,.docx"
              disabled={isUploading}
              onChange={handleFileUpload}
              className="hidden"
            />
          </label>

          {uploadStatus && (
            <div
              className={`mt-4 p-3 rounded-lg text-xs flex items-center gap-2 ${
                uploadStatus.type === 'success'
                  ? 'bg-[#70B875]/15 border border-[#70B875]/40 text-[#70B875]'
                  : 'bg-[#E56857]/15 border border-[#E56857]/40 text-[#E56857]'
              }`}
            >
              {uploadStatus.type === 'success' ? (
                <CheckCircle size={16} weight="bold" />
              ) : (
                <WarningCircle size={16} weight="bold" />
              )}
              <span>{uploadStatus.message}</span>
            </div>
          )}
        </div>
      )}

      {/* Documents Table */}
      <div className="rounded-xl bg-[#222222] border border-[#383838] overflow-hidden">
        <div className="px-5 py-3.5 border-b border-[#383838] flex items-center justify-between">
          <h3 className="text-sm font-bold text-[#FFFFFF]">Authorized Company Documents</h3>
          <span className="text-[10px] font-bold uppercase text-[#888888] tracking-wider">
            {documents.length} Available
          </span>
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-xs text-[#888888]">Loading documents...</div>
        ) : documents.length === 0 ? (
          <div className="p-8 text-center text-xs text-[#888888]">
            No authorized documents found in this account&apos;s scope.
          </div>
        ) : (
          <div className="divide-y divide-[#383838]">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="p-4 flex items-center justify-between hover:bg-[#2A2A2A] transition-colors"
              >
                <div className="flex items-start gap-3 min-w-0 pr-4">
                  <div className="p-2 rounded-lg bg-[#2E2E2E] text-[#F5A623] flex-shrink-0 mt-0.5 border border-[#3D3D3D]">
                    <FileText size={18} />
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-[#FFFFFF] truncate">
                      {doc.document_title || doc.filename}
                    </div>
                    <div className="text-xs text-[#9E9E9E] mt-0.5 flex flex-wrap items-center gap-2">
                      <span className="font-technical text-[11px] text-[#C8C8C8]">{doc.filename}</span>
                      <span>•</span>
                      <span className="text-[#C8C8C8] font-technical">{doc.character_count.toLocaleString()} chars</span>
                      <span>•</span>
                      <span className="px-1.5 py-0.5 rounded bg-[#2E2E2E] text-[#D4D4D4] text-[10px] uppercase font-technical border border-[#3D3D3D]">
                        {doc.visibility}
                      </span>
                      <span className="px-1.5 py-0.5 rounded bg-[#F5A623]/10 text-[#F7C05A] text-[10px] font-technical border border-[#F5A623]/25">
                        {doc.confidentiality_level}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-[#888888] font-technical hidden sm:inline">
                    {new Date(doc.created_at).toLocaleDateString()}
                  </span>
                  {canDelete && (
                    <button
                      onClick={() => handleDelete(doc.id, doc.filename)}
                      className="p-1.5 rounded text-[#888888] hover:text-[#E56857] hover:bg-[#333333] transition-colors"
                      title="Delete document"
                    >
                      <Trash size={15} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
