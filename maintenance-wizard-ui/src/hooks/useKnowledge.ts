import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  bulkUploadKnowledgeDocuments,
  deleteKnowledgeDocument,
  getKnowledgeDocumentChunks,
  ingestKnowledgeRecords,
  listKnowledgeDocuments,
  replaceKnowledgeDocument,
  uploadKnowledgeDocument,
  type BulkUploadKnowledgeDocumentsParams,
  type IngestKnowledgeRecordsParams,
  type ListKnowledgeDocumentsParams,
  type ReplaceKnowledgeDocumentParams,
  type UploadKnowledgeDocumentParams,
} from '@/api/knowledgeApi';

export function useKnowledgeDocuments(params: ListKnowledgeDocumentsParams = {}) {
  return useQuery({
    queryKey: ['knowledge-documents', params],
    queryFn: () => listKnowledgeDocuments(params),
    staleTime: 30_000,
  });
}

export function useKnowledgeDocumentChunks(documentId: string | undefined) {
  return useQuery({
    queryKey: ['knowledge-chunks', documentId],
    queryFn: () => getKnowledgeDocumentChunks(documentId as string),
    enabled: Boolean(documentId),
  });
}

export function useUploadKnowledgeDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: UploadKnowledgeDocumentParams) => uploadKnowledgeDocument(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-documents'] });
    },
  });
}

export function useBulkUploadKnowledgeDocuments() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: BulkUploadKnowledgeDocumentsParams) =>
      bulkUploadKnowledgeDocuments(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-documents'] });
    },
  });
}

export function useIngestKnowledgeRecords() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: IngestKnowledgeRecordsParams) => ingestKnowledgeRecords(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-documents'] });
    },
  });
}

export function useReplaceKnowledgeDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      documentId,
      params,
    }: {
      documentId: string;
      params: ReplaceKnowledgeDocumentParams;
    }) => replaceKnowledgeDocument(documentId, params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-documents'] });
    },
  });
}

export function useDeleteKnowledgeDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) => deleteKnowledgeDocument(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-documents'] });
    },
  });
}
