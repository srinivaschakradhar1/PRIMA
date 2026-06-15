import { Box, Card, CardContent, Typography } from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import EventBusyOutlinedIcon from '@mui/icons-material/EventBusyOutlined';
import BuildOutlinedIcon from '@mui/icons-material/BuildOutlined';
import type { EquipmentStatusSummary } from '@/models/types';

interface PlantStatsCardsProps {
  summary?: EquipmentStatusSummary;
}

const cardConfig = [
  { key: 'UP' as const, label: 'Running', icon: CheckCircleOutlineIcon, color: '#3DDC97' },
  { key: 'FAILED' as const, label: 'Failed', icon: ErrorOutlineIcon, color: '#E84855' },
  { key: 'SCHEDULED_DOWN' as const, label: 'Scheduled Down', icon: EventBusyOutlinedIcon, color: '#FFB454' },
  { key: 'MAINTENANCE' as const, label: 'In Maintenance', icon: BuildOutlinedIcon, color: '#7AA2C2' },
];

export default function PlantStatsCards({ summary }: PlantStatsCardsProps) {
  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' },
        gap: 2,
      }}
    >
      {cardConfig.map(({ key, label, icon: Icon, color }) => (
        <Card key={key} variant="outlined">
          <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Box
              sx={{
                width: 44,
                height: 44,
                borderRadius: 2,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: `${color}1A`,
                color,
              }}
            >
              <Icon />
            </Box>
            <Box>
              <Typography variant="h4" sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
                {summary ? summary[key] : '—'}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {label}
              </Typography>
            </Box>
          </CardContent>
        </Card>
      ))}
    </Box>
  );
}
