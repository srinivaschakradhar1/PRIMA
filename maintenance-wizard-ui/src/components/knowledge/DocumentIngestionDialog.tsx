import { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  MenuItem,
  Radio,
  RadioGroup,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import UploadFileOutlinedIcon from '@mui/icons-material/UploadFileOutlined';
import type { DocumentType, KnowledgeDocumentSummary } from '@/models/types';
import {
  useBulkUploadKnowledgeDocuments,
  useIngestKnowledgeRecords,
  useReplaceKnowledgeDocument,
  useUploadKnowledgeDocument,
} from '@/hooks/useKnowledge';
import EquipmentSelect from './EquipmentSelect';

interface DocumentIngestionDialogProps {
  open: boolean;
  mode: 'create' | 'update';
  document?: KnowledgeDocumentSummary | null;
  onClose: () => void;
  onSuccess: (message: string) => void;
}

// The way a user supplies documents on create. Update (replace) always uses
// the single-document flow and never shows the method selector.
type IngestionMethod = 'single' | 'folder' | 'records';

const documentTypes: DocumentType[] = [
  'MANUAL',
  'SOP',
  'FAILURE_REPORT',
  'MAINTENANCE_LOG',
  'SPARE_PART',
];

// Record-based ingestion (single JSON/CSV with many records) is only supported
// for these document types on the backend.
const recordDocumentTypes: DocumentType[] = ['FAILURE_REPORT', 'MAINTENANCE_LOG'];

const ACCEPTED_SINGLE = '.pdf,.docx,.txt';
const ACCEPTED_RECORDS = '.json,.csv';

const formatType = (type: DocumentType) => type.replace(/_/g, ' ');

export default function DocumentIngestionDialog({
  open,
  mode,
  document,
  onClose,
  onSuccess,
}: DocumentIngestionDialogProps) {
  const [method, setMethod] = useState<IngestionMethod>('single');
  const [file, setFile] = useState<File | null>(null);
  const [folderPath, setFolderPath] = useState('');
  const [equipmentId, setEquipmentId] = useState('');
  const [documentType, setDocumentType] = useState<DocumentType>('MANUAL');

  const uploadMutation = useUploadKnowledgeDocument();
  const bulkUploadMutation = useBulkUploadKnowledgeDocuments();
  const ingestRecordsMutation = useIngestKnowledgeRecords();
  const replaceMutation = useReplaceKnowledgeDocument();

  const isUpdate = mode === 'update';

  const activeMutation = isUpdate
    ? replaceMutation
    : method === 'folder'
      ? bulkUploadMutation
      : method === 'records'
        ? ingestRecordsMutation
        : uploadMutation;

  // Reset / prefill whenever the dialog is (re)opened.
  useEffect(() => {
    if (!open) return;
    setMethod('single');
    setFile(null);
    setFolderPath('');
    setEquipmentId(document?.equipment_id ?? '');
    const docType = document?.document_type as DocumentType | undefined;
    setDocumentType(docType && documentTypes.includes(docType) ? docType : 'MANUAL');
    uploadMutation.reset();
    bulkUploadMutation.reset();
    ingestRecordsMutation.reset();
    replaceMutation.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, document]);

  // When switching to the record-based method, ensure the selected document type
  // is one the backend accepts for that method.
  const handleMethodChange = (next: IngestionMethod) => {
    setMethod(next);
    setFile(null);
    if (next === 'records' && !recordDocumentTypes.includes(documentType)) {
      setDocumentType(recordDocumentTypes[0]);
    }
  };

  const canSubmit = (() => {
    if (isUpdate) return Boolean(file);
    if (method === 'folder') return folderPath.trim().length > 0;
    if (method === 'records') return Boolean(file);
    return Boolean(file) && equipmentId.length > 0;
  })();

  const handleSubmit = () => {
    if (!canSubmit) return;

    if (isUpdate) {
      if (!file || !document) return;
      // Replace the file only; equipment and document type stay unchanged.
      replaceMutation.mutate(
        { documentId: document.document_id, params: { file } },
        {
          onSuccess: () => {
            onSuccess('Document updated successfully.');
            onClose();
          },
        }
      );
      return;
    }

    if (method === 'folder') {
      bulkUploadMutation.mutate(
        { folderPath: folderPath.trim(), documentType },
        {
          onSuccess: (job) => {
            onSuccess(
              `Bulk ingestion queued — ${job.accepted_files} file(s) accepted (job ${job.job_id}).`
            );
            onClose();
          },
        }
      );
      return;
    }

    if (method === 'records') {
      if (!file) return;
      ingestRecordsMutation.mutate(
        { file, documentType },
        {
          onSuccess: (job) => {
            onSuccess(
              `Record ingestion queued — ${job.accepted_files} record(s) accepted (job ${job.job_id}).`
            );
            onClose();
          },
        }
      );
      return;
    }

    // method === 'single'
    if (!file) return;
    uploadMutation.mutate(
      { file, equipmentId, documentType },
      {
        onSuccess: () => {
          onSuccess('Document ingested successfully.');
          onClose();
        },
      }
    );
  };

  const typeOptions = method === 'records' ? recordDocumentTypes : documentTypes;

  const submitLabel = (() => {
    if (activeMutation.isPending) {
      if (isUpdate) return 'Updating…';
      if (method === 'single') return 'Uploading…';
      return 'Submitting…';
    }
    if (isUpdate) return 'Save';
    if (method === 'single') return 'Upload';
    return 'Submit';
  })();

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{isUpdate ? 'Update Document' : 'Ingest New Document'}</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2.5} sx={{ pt: 0.5 }}>
          {!isUpdate && (
            <RadioGroup
              row
              value={method}
              onChange={(e) => handleMethodChange(e.target.value as IngestionMethod)}
            >
              <FormControlLabel
                value="single"
                control={<Radio size="small" />}
                label="Single Document"
              />
              <FormControlLabel
                value="folder"
                control={<Radio size="small" />}
                label="Folder Path"
              />
              <FormControlLabel
                value="records"
                control={<Radio size="small" />}
                label="Record File"
              />
            </RadioGroup>
          )}

          {isUpdate && (
            <Box
              sx={{
                p: 1.5,
                borderRadius: 1.5,
                bgcolor: 'action.hover',
                display: 'flex',
                flexDirection: 'column',
                gap: 0.5,
              }}
            >
              <Typography variant="body2">
                Replacing <strong>{document?.document_name ?? '—'}</strong>
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Equipment: {document?.equipment_id ?? '—'}
                {document?.equipment_type ? ` (${document.equipment_type})` : ''} · Type:{' '}
                {document?.document_type
                  ? String(document.document_type).replace(/_/g, ' ')
                  : '—'}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Equipment and document type cannot be changed here — only the file is
                replaced.
              </Typography>
            </Box>
          )}

          {method === 'records' && !isUpdate && (
            <Typography variant="caption" color="text.secondary">
              Upload a single JSON or CSV file containing multiple records for different
              equipment. Supported for Failure Report and Maintenance Log only.
            </Typography>
          )}

          {/* File picker — shown for single-document, record-file, and update flows. */}
          {(isUpdate || method === 'single' || method === 'records') && (
            <Button
              component="label"
              variant="outlined"
              startIcon={<UploadFileOutlinedIcon />}
              sx={{ justifyContent: 'flex-start', py: 1.25 }}
            >
              {file
                ? file.name
                : method === 'records'
                  ? 'Choose File (JSON, CSV)'
                  : 'Choose File (PDF, DOCX, TXT)'}
              <input
                type="file"
                hidden
                accept={method === 'records' ? ACCEPTED_RECORDS : ACCEPTED_SINGLE}
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </Button>
          )}

          {/* Folder path — bulk-upload flow only. */}
          {method === 'folder' && !isUpdate && (
            <TextField
              label="Folder Path"
              size="small"
              required
              fullWidth
              placeholder="R:\\path\\to\\documents"
              value={folderPath}
              onChange={(e) => setFolderPath(e.target.value)}
              helperText="Absolute path to a folder accessible by the ingestion service."
            />
          )}

          {/* Equipment — single-document create only. */}
          {method === 'single' && !isUpdate && (
            <EquipmentSelect
              label="Equipment"
              required
              value={equipmentId}
              onChange={setEquipmentId}
            />
          )}

          {/* Document type — every create flow needs it; update keeps the original. */}
          {!isUpdate && (
            <TextField
              select
              label="Document Type"
              size="small"
              required
              fullWidth
              value={documentType}
              onChange={(e) => setDocumentType(e.target.value as DocumentType)}
            >
              {typeOptions.map((type) => (
                <MenuItem key={type} value={type}>
                  {formatType(type)}
                </MenuItem>
              ))}
            </TextField>
          )}

          {activeMutation.isError && (
            <Alert severity="error">{activeMutation.error?.message}</Alert>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={activeMutation.isPending}>
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={!canSubmit || activeMutation.isPending}
        >
          {submitLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
