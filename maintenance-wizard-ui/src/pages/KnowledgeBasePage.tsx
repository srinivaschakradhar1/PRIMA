import { useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  MenuItem,
  Snackbar,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import UploadFileOutlinedIcon from '@mui/icons-material/UploadFileOutlined';
import type { KnowledgeDocumentFilter, KnowledgeDocumentSummary } from '@/models/types';
import { downloadKnowledgeDocument } from '@/api/knowledgeApi';
import { useDeleteKnowledgeDocument, useKnowledgeDocuments } from '@/hooks/useKnowledge';
import KnowledgeFilterBar from '@/components/knowledge/KnowledgeFilterBar';
import KnowledgeDocumentsTable from '@/components/knowledge/KnowledgeDocumentsTable';
import DocumentIngestionDialog from '@/components/knowledge/DocumentIngestionDialog';
import ChunkViewerDialog from '@/components/knowledge/ChunkViewerDialog';
import LoadingState from '@/components/common/LoadingState';
import ErrorState from '@/components/common/ErrorState';

const PAGE_SIZES = [10, 25, 50, 100];

interface Toast {
  message: string;
  severity: 'success' | 'error' | 'info';
}

export default function KnowledgeBasePage() {
  const [filters, setFilters] = useState<KnowledgeDocumentFilter>({});
  const [pageSize, setPageSize] = useState(50);
  const [offset, setOffset] = useState(0);

  const [ingestionMode, setIngestionMode] = useState<'create' | 'update' | null>(null);
  const [editDoc, setEditDoc] = useState<KnowledgeDocumentSummary | null>(null);
  const [chunksDoc, setChunksDoc] = useState<KnowledgeDocumentSummary | null>(null);

  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);

  const { data, isLoading, isError, error, refetch, isFetching } = useKnowledgeDocuments({
    ...filters,
    limit: pageSize,
    offset,
  });
  const deleteMutation = useDeleteKnowledgeDocument();

  const total = data?.total ?? 0;
  const documents = data?.documents ?? [];
  const rangeStart = total === 0 ? 0 : offset + 1;
  const rangeEnd = Math.min(offset + pageSize, total);
  const canPrev = offset > 0;
  const canNext = offset + pageSize < total;

  const handleSearch = (next: KnowledgeDocumentFilter) => {
    setFilters(next);
    setOffset(0);
  };

  const handleReset = () => {
    setFilters({});
    setOffset(0);
  };

  const handleView = async (doc: KnowledgeDocumentSummary) => {
    setDownloadingId(doc.document_id);
    try {
      const { blob, fileName } = await downloadKnowledgeDocument(doc.document_id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = fileName || doc.document_name || doc.document_id;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : 'Failed to download document.',
        severity: 'error',
      });
    } finally {
      setDownloadingId(null);
    }
  };

  const handleDelete = (doc: KnowledgeDocumentSummary) => {
    deleteMutation.mutate(doc.document_id, {
      onSuccess: () => {
        setToast({ message: 'Document deleted.', severity: 'success' });
        // Step back a page if we just emptied the current one.
        if (documents.length === 1 && offset > 0) {
          setOffset((prev) => Math.max(0, prev - pageSize));
        }
      },
      onError: (err) => {
        setToast({
          message: err instanceof Error ? err.message : 'Failed to delete document.',
          severity: 'error',
        });
      },
    });
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box>
        <Typography variant="h4" gutterBottom>
          Knowledge Base
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Manage equipment manuals, SOPs, and maintenance records that power the AI
          assistant's retrieval.
        </Typography>
      </Box>

      {/* Summary + primary action */}
      <Stack
        direction={{ xs: 'column', sm: 'row' }}
        spacing={2}
        alignItems={{ sm: 'center' }}
        justifyContent="space-between"
      >
        <Typography variant="subtitle1">
          Documents Ingested:{' '}
          <Box component="span" sx={{ fontWeight: 700 }}>
            {total}
          </Box>
        </Typography>
        <Button
          variant="contained"
          startIcon={<UploadFileOutlinedIcon />}
          onClick={() => {
            setEditDoc(null);
            setIngestionMode('create');
          }}
        >
          Ingest New Document
        </Button>
      </Stack>

      <KnowledgeFilterBar
        onSearch={handleSearch}
        onReset={handleReset}
        disabled={isFetching}
      />

      <Card variant="outlined">
        <CardContent>
          {isLoading && <LoadingState label="Loading documents…" />}
          {isError && <ErrorState message={error?.message} onRetry={() => refetch()} />}

          {data && (
            <>
              <KnowledgeDocumentsTable
                documents={documents}
                onView={handleView}
                onEdit={(doc) => {
                  setEditDoc(doc);
                  setIngestionMode('update');
                }}
                onDelete={handleDelete}
                onViewChunks={setChunksDoc}
                downloadingId={downloadingId}
                deletingId={deleteMutation.isPending ? deleteMutation.variables : null}
              />

              {/* Pagination */}
              <Stack
                direction={{ xs: 'column', sm: 'row' }}
                spacing={2}
                alignItems={{ sm: 'center' }}
                justifyContent="space-between"
                sx={{ mt: 2 }}
              >
                <Typography variant="caption" color="text.secondary">
                  Showing {rangeStart}-{rangeEnd} of {total}
                </Typography>
                <Stack direction="row" spacing={2} alignItems="center">
                  <TextField
                    select
                    size="small"
                    label="Page Size"
                    value={pageSize}
                    onChange={(e) => {
                      setPageSize(Number(e.target.value));
                      setOffset(0);
                    }}
                    sx={{ width: 110 }}
                  >
                    {PAGE_SIZES.map((size) => (
                      <MenuItem key={size} value={size}>
                        {size}
                      </MenuItem>
                    ))}
                  </TextField>
                  <Button
                    size="small"
                    variant="outlined"
                    disabled={!canPrev || isFetching}
                    onClick={() => setOffset((prev) => Math.max(0, prev - pageSize))}
                  >
                    Previous
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    disabled={!canNext || isFetching}
                    onClick={() => setOffset((prev) => prev + pageSize)}
                  >
                    Next
                  </Button>
                </Stack>
              </Stack>
            </>
          )}
        </CardContent>
      </Card>

      <DocumentIngestionDialog
        open={ingestionMode !== null}
        mode={ingestionMode ?? 'create'}
        document={editDoc}
        onClose={() => setIngestionMode(null)}
        onSuccess={(message) => setToast({ message, severity: 'success' })}
      />

      <ChunkViewerDialog document={chunksDoc} onClose={() => setChunksDoc(null)} />

      <Snackbar
        open={Boolean(toast)}
        autoHideDuration={5000}
        onClose={() => setToast(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        {toast ? (
          <Alert
            severity={toast.severity}
            variant="filled"
            onClose={() => setToast(null)}
            sx={{ width: '100%' }}
          >
            {toast.message}
          </Alert>
        ) : undefined}
      </Snackbar>
    </Box>
  );
}
