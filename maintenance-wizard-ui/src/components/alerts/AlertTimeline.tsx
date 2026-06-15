import { Box, Card, CardContent, Typography } from '@mui/material';
import type { Alert } from '@/models/types';
import { riskColors } from '@/theme';
import { formatDateTime } from '@/utils/format';
import EmptyState from '@/components/common/EmptyState';
import ScheduleOutlinedIcon from '@mui/icons-material/ScheduleOutlined';

interface AlertTimelineProps {
  alerts: Alert[];
}

export default function AlertTimeline({ alerts }: AlertTimelineProps) {
  const sorted = [...alerts].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
          Alert Timeline
        </Typography>
        {sorted.length === 0 ? (
          <EmptyState
            icon={<ScheduleOutlinedIcon sx={{ fontSize: 32, opacity: 0.4 }} />}
            title="Nothing to show"
            description="Alerts will appear here as they are raised."
          />
        ) : (
          <Box sx={{ position: 'relative', pl: 3 }}>
            <Box
              sx={{
                position: 'absolute',
                left: 7,
                top: 6,
                bottom: 6,
                width: '2px',
                backgroundColor: 'divider',
              }}
            />
            {sorted.map((alert) => {
              const color = riskColors[(alert.severity ?? '').toUpperCase()] ?? '#7AA2C2';
              return (
                <Box key={alert.id} sx={{ position: 'relative', pb: 2 }}>
                  <Box
                    sx={{
                      position: 'absolute',
                      left: -24,
                      top: 4,
                      width: 12,
                      height: 12,
                      borderRadius: '50%',
                      backgroundColor: color,
                      border: '2px solid',
                      borderColor: 'background.paper',
                      boxShadow: `0 0 0 2px ${color}55`,
                    }}
                  />
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {alert.alert_type} — {alert.equipment_name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                    {alert.message}
                  </Typography>
                  <Typography
                    variant="caption"
                    sx={{ color, fontFamily: '"JetBrains Mono", monospace' }}
                  >
                    {formatDateTime(alert.created_at)}
                  </Typography>
                </Box>
              );
            })}
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
