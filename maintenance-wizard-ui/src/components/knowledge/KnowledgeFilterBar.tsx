import { useState } from 'react';
import { Button, Card, CardContent, MenuItem, Stack, TextField } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import type { DocumentType, KnowledgeDocumentFilter } from '@/models/types';
import EquipmentSelect from './EquipmentSelect';

interface KnowledgeFilterBarProps {
  onSearch: (filters: KnowledgeDocumentFilter) => void;
  onReset: () => void;
  disabled?: boolean;
}

const documentTypes: DocumentType[] = [
  'MANUAL',
  'SOP',
  'FAILURE_REPORT',
  'MAINTENANCE_LOG',
  'SPARE_PART',
];

const emptyDraft = { equipmentId: '', documentType: '' };

export default function KnowledgeFilterBar({
  onSearch,
  onReset,
  disabled,
}: KnowledgeFilterBarProps) {
  const [draft, setDraft] = useState(emptyDraft);

  const handleSearch = () => {
    onSearch({
      equipmentId: draft.equipmentId.trim() || undefined,
      documentType: (draft.documentType as DocumentType) || undefined,
    });
  };

  const handleReset = () => {
    setDraft(emptyDraft);
    onReset();
  };

  return (
    <Card variant="outlined">
      <CardContent>
        <Stack
          direction={{ xs: 'column', md: 'row' }}
          spacing={2}
          alignItems={{ md: 'center' }}
        >
          <EquipmentSelect
            label="Equipment"
            value={draft.equipmentId}
            onChange={(equipmentId) => setDraft((d) => ({ ...d, equipmentId }))}
          />

          <TextField
            select
            label="Document Type"
            size="small"
            fullWidth
            value={draft.documentType}
            onChange={(e) => setDraft((d) => ({ ...d, documentType: e.target.value }))}
          >
            <MenuItem value="">All Document Types</MenuItem>
            {documentTypes.map((type) => (
              <MenuItem key={type} value={type}>
                {type.replace(/_/g, ' ')}
              </MenuItem>
            ))}
          </TextField>

          <Stack direction="row" spacing={1} sx={{ flexShrink: 0 }}>
            <Button
              variant="contained"
              startIcon={<SearchIcon />}
              onClick={handleSearch}
              disabled={disabled}
            >
              Search
            </Button>
            <Button
              variant="outlined"
              startIcon={<RestartAltIcon />}
              onClick={handleReset}
              disabled={disabled}
            >
              Reset
            </Button>
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  );
}
