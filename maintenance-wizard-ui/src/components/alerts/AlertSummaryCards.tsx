import { Box, Card, CardContent, Typography } from '@mui/material';
import type { Alert } from '@/models/types';
import { riskColors } from '@/theme';

interface AlertSummaryCardsProps {
  alerts: Alert[];
}

const severities = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];

export default function AlertSummaryCards({ alerts }: AlertSummaryCardsProps) {
  const counts = severities.map((severity) => ({
    severity,
    count: alerts.filter((a) => (a.severity ?? '').toUpperCase() === severity).length,
  }));

  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' },
        gap: 2,
      }}
    >
      {counts.map(({ severity, count }) => {
        const color = riskColors[severity] ?? '#7AA2C2';
        return (
          <Card key={severity} variant="outlined">
            <CardContent>
              <Typography variant="overline" sx={{ color }}>
                {severity}
              </Typography>
              <Typography variant="h4" sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
                {count}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                active alerts
              </Typography>
            </CardContent>
          </Card>
        );
      })}
    </Box>
  );
}
