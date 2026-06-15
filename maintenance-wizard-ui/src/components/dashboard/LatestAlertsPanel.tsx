import { Box, Card, CardContent, Stack, Typography } from '@mui/material';
import { Link } from 'react-router-dom';
import WarningAmberOutlinedIcon from '@mui/icons-material/WarningAmberOutlined';
import type { EquipmentStatusItem } from '@/models/types';
import { deriveAlertsFromStatus } from '@/utils/alerts';
import StatusChip from '@/components/common/StatusChip';
import EmptyState from '@/components/common/EmptyState';

interface LatestAlertsPanelProps {
  equipment?: EquipmentStatusItem[];
}

export default function LatestAlertsPanel({ equipment }: LatestAlertsPanelProps) {
  const alerts = deriveAlertsFromStatus(equipment ?? []).slice(0, 6);

  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="subtitle2" color="text.secondary">
            Latest Alerts
          </Typography>
          <Typography
            component={Link}
            to="/alerts"
            variant="caption"
            sx={{ color: 'primary.main', textDecoration: 'none' }}
          >
            View all →
          </Typography>
        </Box>
        {alerts.length === 0 ? (
          <EmptyState
            icon={<WarningAmberOutlinedIcon sx={{ fontSize: 32, opacity: 0.4 }} />}
            title="No active alerts"
            description="All equipment is operating within expected thresholds."
          />
        ) : (
          <Stack spacing={1.25}>
            {alerts.map((alert) => (
              <Box
                key={alert.id}
                component={Link}
                to={`/equipment/${alert.equipment_id}`}
                sx={{
                  display: 'flex',
                  gap: 1.5,
                  alignItems: 'flex-start',
                  textDecoration: 'none',
                  color: 'inherit',
                  p: 1,
                  borderRadius: 1.5,
                  border: '1px solid',
                  borderColor: 'divider',
                  '&:hover': { backgroundColor: 'rgba(255,255,255,0.03)' },
                }}
              >
                <StatusChip kind="risk" value={alert.severity} sx={{ mt: 0.25 }} />
                <Box>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {alert.alert_type}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {alert.message}
                  </Typography>
                </Box>
              </Box>
            ))}
          </Stack>
        )}
      </CardContent>
    </Card>
  );
}
