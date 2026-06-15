import { Chip, type ChipProps } from '@mui/material';
import { riskColors, statusColors, criticalityColors } from '@/theme';

interface StatusChipProps extends ChipProps {
  kind: 'status' | 'risk' | 'criticality';
  value: string;
}

export default function StatusChip({ kind, value, sx, ...rest }: StatusChipProps) {
  const palette =
    kind === 'status' ? statusColors : kind === 'risk' ? riskColors : criticalityColors;
  const color = palette[value?.toUpperCase()] ?? '#7AA2C2';

  return (
    <Chip
      {...rest}
      label={value}
      size="small"
      sx={{
        color,
        backgroundColor: `${color}1A`,
        border: `1px solid ${color}55`,
        fontFamily: '"JetBrains Mono", monospace',
        fontSize: '0.7rem',
        letterSpacing: '0.04em',
        ...sx,
      }}
    />
  );
}
