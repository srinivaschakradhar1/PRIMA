import { Autocomplete, TextField } from '@mui/material';
import type { EquipmentListItem } from '@/models/types';
import { useEquipmentList } from '@/hooks/useEquipment';

interface EquipmentSelectorProps {
  value: EquipmentListItem | null;
  onChange: (equipment: EquipmentListItem | null) => void;
}

export default function EquipmentSelector({ value, onChange }: EquipmentSelectorProps) {
  const { data: equipmentList, isLoading } = useEquipmentList();

  return (
    <Autocomplete
      options={equipmentList ?? []}
      loading={isLoading}
      getOptionLabel={(option) => `${option.equipment_code} — ${option.equipment_name}`}
      value={value}
      onChange={(_, newValue) => onChange(newValue)}
      isOptionEqualToValue={(option, val) => option.id === val.id}
      renderInput={(params) => (
        <TextField {...params} label="Equipment" placeholder="Search by code or name" size="small" />
      )}
    />
  );
}
