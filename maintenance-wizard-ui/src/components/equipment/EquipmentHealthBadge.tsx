import { Box, LinearProgress, Typography } from '@mui/material';

interface EquipmentHealthBadgeProps {
  score: number;
}

export default function EquipmentHealthBadge({ score }: EquipmentHealthBadgeProps) {
  const color = score < 40 ? 'error' : score < 70 ? 'warning' : 'secondary';

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 120 }}>
      <LinearProgress
        variant="determinate"
        value={Math.min(100, Math.max(0, score))}
        color={color}
        sx={{ flexGrow: 1, height: 6 }}
      />
      <Typography variant="caption" sx={{ fontFamily: '"JetBrains Mono", monospace', minWidth: 28 }}>
        {score}
      </Typography>
    </Box>
  );
}
