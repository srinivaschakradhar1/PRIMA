import { Box, Chip, Stack, Typography } from '@mui/material';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import type { ChatCitation } from '@/models/types';

interface SourceCitationPanelProps {
  citations: ChatCitation[];
}

export default function SourceCitationPanel({ citations }: SourceCitationPanelProps) {
  if (citations.length === 0) return null;

  return (
    <Box sx={{ mt: 1 }}>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
        Sources
      </Typography>
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
        {citations.map((citation, idx) => (
          <Chip
            key={`${citation.document}-${citation.page}-${idx}`}
            icon={<DescriptionOutlinedIcon sx={{ fontSize: 16 }} />}
            label={`${citation.document} · p.${citation.page}`}
            size="small"
            variant="outlined"
            sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '0.7rem' }}
          />
        ))}
      </Stack>
    </Box>
  );
}
