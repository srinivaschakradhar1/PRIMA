import { Box, Button, Typography } from '@mui/material';
import { useNavigate, useParams } from 'react-router-dom';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useEquipmentDetail, useEquipmentHealth, usePreventiveActions } from '@/hooks/useEquipment';
import EquipmentSummaryCard from '@/components/health/EquipmentSummaryCard';
import HealthScoreGauge from '@/components/health/HealthScoreGauge';
import RULCard from '@/components/health/RULCard';
import PreventiveActionsTable from '@/components/health/PreventiveActionsTable';
import SensorTrendChart from '@/components/health/SensorTrendChart';
import LoadingState from '@/components/common/LoadingState';
import ErrorState from '@/components/common/ErrorState';

export default function EquipmentDetailsPage() {
  const { equipmentId } = useParams<{ equipmentId: string }>();
  const navigate = useNavigate();

  const equipmentQuery = useEquipmentDetail(equipmentId);
  const healthQuery = useEquipmentHealth(equipmentId);
  const actionsQuery = usePreventiveActions(equipmentId);

  if (equipmentQuery.isLoading) return <LoadingState label="Loading equipment details…" minHeight={400} />;
  if (equipmentQuery.isError || !equipmentQuery.data) {
    return (
      <ErrorState
        title="Equipment not found"
        message={equipmentQuery.error?.message ?? 'This equipment could not be loaded.'}
        onRetry={() => equipmentQuery.refetch()}
      />
    );
  }

  const equipment = equipmentQuery.data;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Button startIcon={<ArrowBackIcon />} size="small" onClick={() => navigate('/equipment')}>
          Back to Equipment
        </Button>
      </Box>

      <Typography variant="h4">{equipment.equipment_code}</Typography>

      <EquipmentSummaryCard equipment={equipment} />

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
          gap: 2,
        }}
      >
        {healthQuery.isError ? (
          <ErrorState message={healthQuery.error?.message} onRetry={() => healthQuery.refetch()} />
        ) : (
          <HealthScoreGauge
            healthScore={healthQuery.data?.health_score ?? equipment.health_score}
            risk={healthQuery.data?.risk ?? equipment.risk_of_failure}
          />
        )}
        <RULCard rulDays={healthQuery.data?.rul_days} risk={healthQuery.data?.risk} />
      </Box>

      {actionsQuery.isError ? (
        <ErrorState message={actionsQuery.error?.message} onRetry={() => actionsQuery.refetch()} />
      ) : (
        <PreventiveActionsTable
          actions={actionsQuery.data?.actions ?? []}
          equipmentName={actionsQuery.data?.equipment ?? equipment.equipment_name}
        />
      )}

      <SensorTrendChart />
    </Box>
  );
}
