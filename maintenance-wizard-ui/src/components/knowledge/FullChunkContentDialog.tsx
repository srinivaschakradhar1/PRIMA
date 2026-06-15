import {
  Box,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  Stack,
  Typography,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import type { KnowledgeChunk } from '@/models/types';

interface FullChunkContentDialogProps {
  chunk: KnowledgeChunk | null;
  onClose: () => void;
}

function MetaItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        {label}
      </Typography>
      <Typography variant="body2" sx={{ fontWeight: 600 }}>
        {value ?? '—'}
      </Typography>
    </Box>
  );
}

export default function FullChunkContentDialog({
  chunk,
  onClose,
}: FullChunkContentDialogProps) {
  return (
    <Dialog
      open={Boolean(chunk)}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{ sx: { width: '80vw', maxWidth: '80vw', height: '80vh' } }}
    >
      <DialogTitle
        sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
      >
        Chunk Content
        <IconButton onClick={onClose} size="small">
          <CloseIcon fontSize="small" />
        </IconButton>
      </DialogTitle>
      <DialogContent dividers sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {chunk && (
          <>
            <Stack
              direction="row"
              spacing={3}
              flexWrap="wrap"
              useFlexGap
              sx={{ rowGap: 1.5 }}
            >
              <MetaItem label="Chunk ID" value={chunk.chunk_id} />
              <MetaItem label="Page" value={chunk.page ?? '—'} />
              <MetaItem label="Concept" value={chunk.concept ?? '—'} />
              <MetaItem label="Semantic Type" value={chunk.semantic_type ?? '—'} />
              <MetaItem label="Token Count" value={chunk.token_count ?? '—'} />
            </Stack>
            <Divider />
            <Typography variant="subtitle2" color="text.secondary">
              Content
            </Typography>
            <Box
              sx={{
                flex: 1,
                overflow: 'auto',
                p: 2,
                borderRadius: 2,
                bgcolor: 'action.hover',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                fontFamily: '"JetBrains Mono", monospace',
                fontSize: '0.85rem',
                lineHeight: 1.6,
              }}
            >
              {chunk.text}
            </Box>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
