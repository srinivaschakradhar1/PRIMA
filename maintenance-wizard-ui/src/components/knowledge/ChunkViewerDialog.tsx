import { useState } from 'react';
import {
  Box,
  Chip,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import type { KnowledgeChunk, KnowledgeDocumentSummary } from '@/models/types';
import { useKnowledgeDocumentChunks } from '@/hooks/useKnowledge';
import LoadingState from '@/components/common/LoadingState';
import ErrorState from '@/components/common/ErrorState';
import EmptyState from '@/components/common/EmptyState';
import FullChunkContentDialog from './FullChunkContentDialog';

interface ChunkViewerDialogProps {
  document: KnowledgeDocumentSummary | null;
  onClose: () => void;
}

export default function ChunkViewerDialog({ document, onClose }: ChunkViewerDialogProps) {
  const [selectedChunk, setSelectedChunk] = useState<KnowledgeChunk | null>(null);
  const { data, isLoading, isError, error, refetch } = useKnowledgeDocumentChunks(
    document?.document_id
  );

  return (
    <>
      <Dialog
        open={Boolean(document)}
        onClose={onClose}
        maxWidth={false}
        fullWidth
        PaperProps={{
          sx: { width: '90vw', maxWidth: '90vw', height: '85vh' },
        }}
      >
        <DialogTitle
          sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}
        >
          <Box>
            <Typography variant="h6">
              {data?.document_name ?? document?.document_name ?? 'Document Chunks'}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Document ID: {document?.document_id}
            </Typography>
          </Box>
          <IconButton onClick={onClose} size="small">
            <CloseIcon fontSize="small" />
          </IconButton>
        </DialogTitle>

        <DialogContent dividers sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {isLoading && <LoadingState label="Loading chunks…" />}
          {isError && <ErrorState message={error?.message} onRetry={() => refetch()} />}

          {data && (
            <>
              <Stack
                direction="row"
                spacing={1.5}
                flexWrap="wrap"
                useFlexGap
                alignItems="center"
              >
                <Chip label={`Total Chunks: ${data.total_chunks}`} size="small" />
                <Chip
                  label={`Indexed Chunks: ${data.indexed_chunks}`}
                  size="small"
                  color="primary"
                  variant="outlined"
                />
                <Divider orientation="vertical" flexItem />
                {Object.entries(data.counts_by_index).length === 0 ? (
                  <Typography variant="caption" color="text.secondary">
                    No indexed chunks
                  </Typography>
                ) : (
                  Object.entries(data.counts_by_index).map(([index, count]) => (
                    <Chip
                      key={index}
                      size="small"
                      variant="outlined"
                      label={`${index}: ${count}`}
                      sx={{ fontFamily: '"JetBrains Mono", monospace' }}
                    />
                  ))
                )}
              </Stack>

              <Divider />

              {data.chunks.length === 0 ? (
                <EmptyState
                  title="No chunks found"
                  description="This document has not produced any stored chunks."
                />
              ) : (
                <TableContainer sx={{ flex: 1, overflow: 'auto' }}>
                  <Table size="small" stickyHeader>
                    <TableHead>
                      <TableRow>
                        <TableCell>Chunk ID</TableCell>
                        <TableCell>Page</TableCell>
                        <TableCell>Concept</TableCell>
                        <TableCell>Semantic Type</TableCell>
                        <TableCell>Parent</TableCell>
                        <TableCell>Index</TableCell>
                        <TableCell align="right">Tokens</TableCell>
                        <TableCell>Content</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {data.chunks.map((chunk) => (
                        <TableRow
                          key={chunk.chunk_id}
                          hover
                          onClick={() => setSelectedChunk(chunk)}
                          sx={{ cursor: 'pointer' }}
                        >
                          <TableCell sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
                            {chunk.chunk_id}
                          </TableCell>
                          <TableCell>{chunk.page ?? '—'}</TableCell>
                          <TableCell>{chunk.concept ?? '—'}</TableCell>
                          <TableCell>{chunk.semantic_type ?? '—'}</TableCell>
                          <TableCell>
                            {chunk.is_parent ? (
                              <Chip label="Parent" size="small" color="secondary" />
                            ) : (
                              chunk.parent_chunk_id ?? '—'
                            )}
                          </TableCell>
                          <TableCell>{chunk.index_name ?? '—'}</TableCell>
                          <TableCell align="right">{chunk.token_count ?? '—'}</TableCell>
                          <TableCell sx={{ maxWidth: 360 }}>
                            <Tooltip title="Click row to view full content">
                              <Typography
                                variant="body2"
                                sx={{
                                  display: '-webkit-box',
                                  WebkitLineClamp: 3,
                                  WebkitBoxOrient: 'vertical',
                                  overflow: 'hidden',
                                  whiteSpace: 'pre-wrap',
                                  wordBreak: 'break-word',
                                }}
                              >
                                {chunk.text}
                              </Typography>
                            </Tooltip>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>

      <FullChunkContentDialog chunk={selectedChunk} onClose={() => setSelectedChunk(null)} />
    </>
  );
}
