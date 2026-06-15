import { httpClient } from './httpClient';
import type {
  DocumentType,
  KnowledgeChunksResponse,
  KnowledgeDeleteResponse,
  KnowledgeDocumentFilter,
  KnowledgeDocumentListResponse,
  KnowledgeIngestionJobResponse,
  KnowledgeUploadResponse,
} from '@/models/types';

export interface ListKnowledgeDocumentsParams extends KnowledgeDocumentFilter {
  limit?: number;
  offset?: number;
}

export async function listKnowledgeDocuments(
  params: ListKnowledgeDocumentsParams = {}
): Promise<KnowledgeDocumentListResponse> {
  const query: Record<string, string | number> = {};
  if (params.equipmentType) query.equipmentType = params.equipmentType;
  if (params.equipmentId) query.equipmentId = params.equipmentId;
  if (params.documentType) query.documentType = params.documentType;
  if (params.limit != null) query.limit = params.limit;
  if (params.offset != null) query.offset = params.offset;

  const { data } = await httpClient.get<KnowledgeDocumentListResponse>('/knowledge', {
    params: query,
  });
  return data;
}

export interface UploadKnowledgeDocumentParams {
  file: File;
  equipmentId: string;
  documentType: DocumentType;
}

export async function uploadKnowledgeDocument(
  params: UploadKnowledgeDocumentParams
): Promise<KnowledgeUploadResponse> {
  const formData = new FormData();
  formData.append('file', params.file);
  formData.append('equipmentId', params.equipmentId);
  formData.append('documentType', params.documentType);

  const { data } = await httpClient.post<KnowledgeUploadResponse>(
    '/knowledge/upload',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  return data;
}

export interface BulkUploadKnowledgeDocumentsParams {
  folderPath: string;
  documentType: DocumentType;
}

export async function bulkUploadKnowledgeDocuments(
  params: BulkUploadKnowledgeDocumentsParams
): Promise<KnowledgeIngestionJobResponse> {
  const { data } = await httpClient.post<KnowledgeIngestionJobResponse>(
    '/knowledge/bulk-upload',
    {
      folder_path: params.folderPath,
      document_type: params.documentType,
    }
  );
  return data;
}

export interface IngestKnowledgeRecordsParams {
  file: File;
  documentType: DocumentType;
}

export async function ingestKnowledgeRecords(
  params: IngestKnowledgeRecordsParams
): Promise<KnowledgeIngestionJobResponse> {
  const formData = new FormData();
  formData.append('file', params.file);
  formData.append('documentType', params.documentType);

  const { data } = await httpClient.post<KnowledgeIngestionJobResponse>(
    '/knowledge/ingest-records',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  return data;
}

export interface ReplaceKnowledgeDocumentParams {
  file: File;
  equipmentId?: string;
  documentType?: DocumentType;
}

export async function replaceKnowledgeDocument(
  documentId: string,
  params: ReplaceKnowledgeDocumentParams
): Promise<KnowledgeUploadResponse> {
  const formData = new FormData();
  formData.append('file', params.file);
  if (params.equipmentId) formData.append('equipmentId', params.equipmentId);
  if (params.documentType) formData.append('documentType', params.documentType);

  const { data } = await httpClient.put<KnowledgeUploadResponse>(
    `/knowledge/upload/${documentId}`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  return data;
}

export async function getKnowledgeDocumentChunks(
  documentId: string
): Promise<KnowledgeChunksResponse> {
  const { data } = await httpClient.get<KnowledgeChunksResponse>(
    `/knowledge/${documentId}/chunks`
  );
  return data;
}

export async function downloadKnowledgeDocument(
  documentId: string
): Promise<{ blob: Blob; fileName: string }> {
  const response = await httpClient.get<Blob>(`/knowledge/${documentId}/download`, {
    responseType: 'blob',
  });

  const disposition = response.headers['content-disposition'] as string | undefined;
  let fileName = `${documentId}`;
  if (disposition) {
    const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition);
    if (match?.[1]) fileName = decodeURIComponent(match[1]);
  }

  return { blob: response.data, fileName };
}

export async function deleteKnowledgeDocument(
  documentId: string
): Promise<KnowledgeDeleteResponse> {
  const { data } = await httpClient.delete<KnowledgeDeleteResponse>(`/knowledge/${documentId}`);
  return data;
}
