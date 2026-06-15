import { Autocomplete, Card, CardContent, MenuItem, Stack, TextField } from '@mui/material';
import type { EquipmentFilter, EquipmentListItem } from '@/models/types';

interface EquipmentFilterPanelProps {
  filters: EquipmentFilter;
  onChange: (filters: EquipmentFilter) => void;
  equipmentOptions: EquipmentListItem[];
  selectedEquipmentId?: string;
  onSelectEquipment: (id: string | undefined) => void;
}

const statuses = ['UP', 'FAILED', 'SCHEDULED_DOWN', 'MAINTENANCE'];
const criticalities = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];

export default function EquipmentFilterPanel({
  filters,
  onChange,
  equipmentOptions,
  selectedEquipmentId,
  onSelectEquipment,
}: EquipmentFilterPanelProps) {
  const handleChange = (key: keyof EquipmentFilter, value: string) => {
    onChange({ ...filters, [key]: value || undefined });
  };

  const selectedOption =
    equipmentOptions.find((option) => option.id === selectedEquipmentId) ?? null;

  return (
    <Card variant="outlined">
      <CardContent>
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
          <Autocomplete
            size="small"
            fullWidth
            options={equipmentOptions}
            value={selectedOption}
            onChange={(_, option) => onSelectEquipment(option?.id)}
            getOptionLabel={(option) => option.equipment_name}
            isOptionEqualToValue={(option, value) => option.id === value.id}
            renderInput={(params) => (
              <TextField {...params} label="Search Equipment" placeholder="Search by name…" />
            )}
          />

          <TextField
            select
            label="Status"
            size="small"
            fullWidth
            value={filters.status ?? ''}
            onChange={(e) => handleChange('status', e.target.value)}
          >
            <MenuItem value="">All Statuses</MenuItem>
            {statuses.map((status) => (
              <MenuItem key={status} value={status}>
                {status.replace('_', ' ')}
              </MenuItem>
            ))}
          </TextField>

          <TextField
            select
            label="Criticality"
            size="small"
            fullWidth
            value={filters.criticality ?? ''}
            onChange={(e) => handleChange('criticality', e.target.value)}
          >
            <MenuItem value="">All Criticalities</MenuItem>
            {criticalities.map((c) => (
              <MenuItem key={c} value={c}>
                {c}
              </MenuItem>
            ))}
          </TextField>
        </Stack>
      </CardContent>
    </Card>
  );
}
