import { useState } from 'react';
import { Box, Typography } from '@mui/material';
import type { EquipmentListItem } from '@/models/types';
import { useEquipmentStatus } from '@/hooks/useEquipment';
import RiskMatrixChart from '@/components/predictive/RiskMatrixChart';
import RULRankingTable from '@/components/predictive/RULRankingTable';
import PredictiveDetailPanel from '@/components/predictive/PredictiveDetailPanel';
import LoadingState from '@/components/common/LoadingState';
import ErrorState from '@/components/common/ErrorState';

export default function PredictiveMaintenancePage() {
  const { data, isLoading, isError, error, refetch } = useEquipmentStatus();
  const [selected, setSelected] = useState<EquipmentListItem | null>(null);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box>
        <Typography variant="h4" gutterBottom>
          Predictive Maintenance
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Remaining useful life, future failure risk, and recommended preventive actions across the fleet.
        </Typography>
      </Box>

      {isLoading && <LoadingState label="Loading predictive data…" />}
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
          <RiskMatrixChart equipment={data} />
          <RULRankingTable equipment={data} />
        </Box>
      )}

      <PredictiveDetailPanel equipment={selected} onChange={setSelected} />
    </Box>
  );
}
