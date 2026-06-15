import { Box, Typography } from '@mui/material';
import { useEquipmentStatus, useEquipmentStatusSummary } from '@/hooks/useEquipment';
import PlantStatsCards from '@/components/dashboard/PlantStatsCards';
import EquipmentStatusPieChart from '@/components/dashboard/EquipmentStatusPieChart';
import EquipmentHealthHistogram from '@/components/dashboard/EquipmentHealthHistogram';
import CriticalEquipmentTable from '@/components/dashboard/CriticalEquipmentTable';
import LatestAlertsPanel from '@/components/dashboard/LatestAlertsPanel';
import ErrorState from '@/components/common/ErrorState';

export default function DashboardPage() {
  const summaryQuery = useEquipmentStatusSummary();
  const statusQuery = useEquipmentStatus();

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Box>
        <Typography variant="h4" gutterBottom>
          Plant Overview
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Live equipment status, health distribution, and surfaced risks across Steel Plant A.
        </Typography>
      </Box>

      {summaryQuery.isError && (
        <ErrorState message={summaryQuery.error?.message} onRetry={() => summaryQuery.refetch()} />
      )}

      <PlantStatsCards summary={summaryQuery.data} />

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
          gap: 2,
        }}
      >
        <EquipmentStatusPieChart summary={summaryQuery.data} />
        <EquipmentHealthHistogram equipment={statusQuery.data} />
      </Box>

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: '2fr 1fr' },
          gap: 2,
          alignItems: 'stretch',
        }}
      >
        {statusQuery.isError ? (
          <ErrorState message={statusQuery.error?.message} onRetry={() => statusQuery.refetch()} />
        ) : (
          <CriticalEquipmentTable equipment={statusQuery.data} />
        )}
        <LatestAlertsPanel equipment={statusQuery.data} />
      </Box>
    </Box>
  );
}
