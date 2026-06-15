import { Autocomplete, CircularProgress, TextField } from '@mui/material';
import { useEquipmentList } from '@/hooks/useEquipment';

interface EquipmentSelectProps {
  value: string;
  onChange: (equipmentId: string) => void;
  label?: string;
  placeholder?: string;
  required?: boolean;
  error?: boolean;
  helperText?: string;
  disabled?: boolean;
  size?: 'small' | 'medium';
}

export default function EquipmentSelect({
  value,
  onChange,
  label = 'Equipment',
  placeholder = 'Search equipment…',
  required,
  error,
  helperText,
  disabled,
  size = 'small',
}: EquipmentSelectProps) {
  const { data: equipmentList, isLoading } = useEquipmentList();
  const options = equipmentList ?? [];
  const selected = options.find((e) => e.id === value) ?? null;

  return (
    <Autocomplete
      options={options}
      value={selected}
      loading={isLoading}
      disabled={disabled}
      size={size}
      fullWidth
      onChange={(_, option) => onChange(option?.id ?? '')}
      getOptionLabel={(option) => `${option.equipment_code} — ${option.equipment_name}`}
      isOptionEqualToValue={(option, val) => option.id === val.id}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          required={required}
          error={error}
          helperText={helperText}
          placeholder={placeholder}
          InputProps={{
            ...params.InputProps,
            endAdornment: (
              <>
                {isLoading ? <CircularProgress color="inherit" size={16} /> : null}
                {params.InputProps.endAdornment}
              </>
            ),
          }}
        />
      )}
    />
  );
}
