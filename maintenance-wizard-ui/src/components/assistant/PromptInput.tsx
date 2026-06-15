import { useState, type KeyboardEvent } from 'react';
import { Autocomplete, Box, IconButton, TextField } from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import PrecisionManufacturingOutlinedIcon from '@mui/icons-material/PrecisionManufacturingOutlined';
import type { EquipmentListItem } from '@/models/types';

interface PromptInputProps {
  equipmentOptions: EquipmentListItem[];
  equipmentLoading: boolean;
  selectedEquipment: EquipmentListItem | null;
  onEquipmentChange: (equipment: EquipmentListItem | null) => void;
  /** When set, the equipment is locked for the session and cannot be changed. */
  lockedEquipmentLabel: string | null;
  onSubmit: (message: string) => void;
  disabled?: boolean;
}

export default function PromptInput({
  equipmentOptions,
  equipmentLoading,
  selectedEquipment,
  onEquipmentChange,
  lockedEquipmentLabel,
  onSubmit,
  disabled,
}: PromptInputProps) {
  const [value, setValue] = useState('');

  const hasEquipment = lockedEquipmentLabel != null || selectedEquipment != null;
  const canSend = !disabled && hasEquipment && Boolean(value.trim());

  const handleSubmit = () => {
    if (!canSend) return;
    onSubmit(value.trim());
    setValue('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end' }}>
      {lockedEquipmentLabel != null ? (
        <TextField
          size="small"
          value={lockedEquipmentLabel}
          label="Equipment"
          disabled
          sx={{ width: { xs: 160, sm: 240 }, flexShrink: 0 }}
          InputProps={{
            startAdornment: (
              <PrecisionManufacturingOutlinedIcon
                fontSize="small"
                sx={{ mr: 0.5, color: 'text.disabled' }}
              />
            ),
          }}
        />
      ) : (
        <Autocomplete
          options={equipmentOptions}
          loading={equipmentLoading}
          value={selectedEquipment}
          onChange={(_, newValue) => onEquipmentChange(newValue)}
          getOptionLabel={(option) => `${option.equipment_code} — ${option.equipment_name}`}
          isOptionEqualToValue={(option, val) => option.id === val.id}
          disabled={disabled}
          sx={{ width: { xs: 160, sm: 240 }, flexShrink: 0 }}
          renderInput={(params) => (
            <TextField {...params} label="Equipment" placeholder="Select equipment" size="small" />
          )}
        />
      )}
      <TextField
        fullWidth
        multiline
        maxRows={4}
        size="small"
        placeholder={
          hasEquipment
            ? 'Ask about equipment health, diagnostics, or maintenance history…'
            : 'Select an equipment to start…'
        }
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
      />
      <IconButton color="primary" onClick={handleSubmit} disabled={!canSend}>
        <SendIcon />
      </IconButton>
    </Box>
  );
}
