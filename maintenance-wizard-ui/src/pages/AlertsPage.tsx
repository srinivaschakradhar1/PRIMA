import { Box, Typography } from '@mui/material';
import { useEquipmentStatus } from '@/hooks/useEquipment';
import { deriveAlertsFromStatus } from '@/utils/alerts';
import AlertSummaryCards from '@/components/alerts/AlertSummaryCards';
import CriticalAlertsTable from '@/components/alerts/CriticalAlertsTable';
import AlertTimeline from '@/components/alerts/AlertTimeline';
import LoadingState from '@/components/common/LoadingState';
import ErrorState from '@/components/common/ErrorState';

export default function AlertsPage() {
  const { data, isLoading, isError, error, refetch } = useEquipmentStatus();
  const alerts = deriveAlertsFromStatus(data ?? []);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box>
        <Typography variant="h4" gutterBottom>
          System Alerts
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Alerts derived from equipment status, health records, and prediction results across the plant.
        </Typography>
      </Box>

      {isLoading && <LoadingState label="Loading alerts…" />}
      {isError && <ErrorState message={error?.message} onRetry={() => refetch()} />}

      {data && (
        <>
          <AlertSummaryCards alerts={alerts} />
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', md: '2fr 1fr' },
              gap: 2,
              alignItems: 'flex-start',
            }}
          >
            <CriticalAlertsTable alerts={alerts} />
            <AlertTimeline alerts={alerts} />
          </Box>
        </>
      )}
    </Box>
  );
}
