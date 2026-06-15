import { useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  IconButton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
} from '@mui/material';
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import LayersOutlinedIcon from '@mui/icons-material/LayersOutlined';
import type { KnowledgeDocumentSummary } from '@/models/types';
import { formatIngestedAt } from '@/utils/format';
import EmptyState from '@/components/common/EmptyState';

interface KnowledgeDocumentsTableProps {
  documents: KnowledgeDocumentSummary[];
  onView: (doc: KnowledgeDocumentSummary) => void;
  onEdit: (doc: KnowledgeDocumentSummary) => void;
  onDelete: (doc: KnowledgeDocumentSummary) => void;
  onViewChunks: (doc: KnowledgeDocumentSummary) => void;
  downloadingId?: string | null;
  deletingId?: string | null;
}

export default function KnowledgeDocumentsTable({
  documents,
  onView,
  onEdit,
  onDelete,
  onViewChunks,
  downloadingId,
  deletingId,
}: KnowledgeDocumentsTableProps) {
  const [pendingDelete, setPendingDelete] = useState<KnowledgeDocumentSummary | null>(null);

  const confirmDelete = () => {
    if (pendingDelete) onDelete(pendingDelete);
    setPendingDelete(null);
  };

  if (documents.length === 0) {
    return (
      <EmptyState
        title="No documents found"
        description="Adjust your filters or ingest a new document to populate the knowledge base."
      />
    );
  }

  return (
    <>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Actions</TableCell>
              <TableCell>Document Name</TableCell>
              <TableCell>Equipment ID</TableCell>
              <TableCell>Equipment Type</TableCell>
              <TableCell>Document Type</TableCell>
              <TableCell align="right">Chunks</TableCell>
              <TableCell>Ingested At</TableCell>
              <TableCell align="center">More</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {documents.map((doc) => (
              <TableRow key={doc.document_id} hover>
                <TableCell>
                  <Stack direction="row" spacing={0.5}>
                    <Tooltip title="View Document">
                      <span>
                        <IconButton
                          size="small"
                          onClick={() => onView(doc)}
                          disabled={downloadingId === doc.document_id}
                        >
                          {downloadingId === doc.document_id ? (
                            <CircularProgress size={16} />
                          ) : (
                            <VisibilityOutlinedIcon fontSize="small" />
                          )}
                        </IconButton>
                      </span>
                    </Tooltip>
                    <Tooltip title="Update Document">
                      <IconButton size="small" onClick={() => onEdit(doc)}>
                        <EditOutlinedIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete Document">
                      <span>
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => setPendingDelete(doc)}
                          disabled={deletingId === doc.document_id}
                        >
                          {deletingId === doc.document_id ? (
                            <CircularProgress size={16} color="error" />
                          ) : (
                            <DeleteOutlineIcon fontSize="small" />
                          )}
                        </IconButton>
                      </span>
                    </Tooltip>
                  </Stack>
                </TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{doc.document_name ?? '—'}</TableCell>
                <TableCell>{doc.equipment_id ?? '—'}</TableCell>
                <TableCell>{doc.equipment_type ?? '—'}</TableCell>
                <TableCell>
                  {doc.document_type ? (
                    <Chip
                      size="small"
                      label={String(doc.document_type).replace(/_/g, ' ')}
                      sx={{ fontFamily: '"JetBrains Mono", monospace' }}
                    />
                  ) : (
                    '—'
                  )}
                </TableCell>
                <TableCell align="right">{doc.chunk_count}</TableCell>
                <TableCell>{formatIngestedAt(doc.ingested_at)}</TableCell>
                <TableCell align="center">
                  <Tooltip title="View Chunks">
                    <IconButton size="small" onClick={() => onViewChunks(doc)}>
                      <LayersOutlinedIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={Boolean(pendingDelete)} onClose={() => setPendingDelete(null)}>
        <DialogTitle>Delete Document</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete this document and all associated chunks?
          </DialogContentText>
          {pendingDelete?.document_name && (
            <Box sx={{ mt: 1, fontWeight: 600 }}>{pendingDelete.document_name}</Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingDelete(null)}>Cancel</Button>
          <Button color="error" variant="contained" onClick={confirmDelete}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
