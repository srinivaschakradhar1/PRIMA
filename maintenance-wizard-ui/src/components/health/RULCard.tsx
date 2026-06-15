import { Box, Card, CardContent, Typography } from '@mui/material';
import HourglassBottomOutlinedIcon from '@mui/icons-material/HourglassBottomOutlined';
import StatusChip from '@/components/common/StatusChip';

interface RULCardProps {
  rulDays?: number;
  risk?: string;
}

export default function RULCard({ rulDays, risk }: RULCardProps) {
  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, height: '100%' }}>
        <Typography variant="subtitle2" color="text.secondary">
          Remaining Useful Life
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexGrow: 1 }}>
          <Box
            sx={{
              width: 56,
              height: 56,
              borderRadius: 2,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: 'rgba(255,106,61,0.12)',
              color: 'primary.main',
            }}
          >
            <HourglassBottomOutlinedIcon fontSize="large" />
          </Box>
          <Box>
            <Typography variant="h3" sx={{ fontFamily: '"JetBrains Mono", monospace', lineHeight: 1 }}>
              {rulDays ?? '—'}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              days remaining
            </Typography>
          </Box>
        </Box>
        {risk && (
          <Box>
            <StatusChip kind="risk" value={risk} />
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
