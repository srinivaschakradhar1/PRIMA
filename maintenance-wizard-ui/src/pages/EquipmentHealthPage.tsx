import { Box, Typography } from '@mui/material';
import { useEquipmentStatus } from '@/hooks/useEquipment';
import EquipmentHealthHistogram from '@/components/dashboard/EquipmentHealthHistogram';
import CriticalEquipmentTable from '@/components/dashboard/CriticalEquipmentTable';
import RULRankingTable from '@/components/predictive/RULRankingTable';
import LoadingState from '@/components/common/LoadingState';
import ErrorState from '@/components/common/ErrorState';

export default function EquipmentHealthPage() {
  const { data, isLoading, isError, error, refetch } = useEquipmentStatus();

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box>
        <Typography variant="h4" gutterBottom>
          Equipment Health
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Fleet-wide health score distribution and the assets that need attention first.
        </Typography>
      </Box>

      {isLoading && <LoadingState label="Loading health data…" />}
      {isError && <ErrorState message={error?.message} onRetry={() => refetch()} />}

      {data && (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
            gap: 2,
            alignItems: 'stretch',
          }}
        >
          <EquipmentHealthHistogram equipment={data} />
          <RULRankingTable equipment={data} />
        </Box>
      )}

      {data && <CriticalEquipmentTable equipment={data} />}
    </Box>
  );
}
