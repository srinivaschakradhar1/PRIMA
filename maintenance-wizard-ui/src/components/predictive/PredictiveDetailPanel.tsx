import { Box, Card, CardContent, Typography } from '@mui/material';
import EquipmentSelector from '@/components/diagnosis/EquipmentSelector';
import HealthScoreGauge from '@/components/health/HealthScoreGauge';
import RULCard from '@/components/health/RULCard';
import PreventiveActionsTable from '@/components/health/PreventiveActionsTable';
import { useEquipmentHealth, usePreventiveActions } from '@/hooks/useEquipment';
import type { EquipmentListItem } from '@/models/types';
import LoadingState from '@/components/common/LoadingState';
import EmptyState from '@/components/common/EmptyState';
import QueryStatsOutlinedIcon from '@mui/icons-material/QueryStatsOutlined';

interface PredictiveDetailPanelProps {
  equipment: EquipmentListItem | null;
  onChange: (equipment: EquipmentListItem | null) => void;
}

export default function PredictiveDetailPanel({ equipment, onChange }: PredictiveDetailPanelProps) {
  const healthQuery = useEquipmentHealth(equipment?.id);
  const actionsQuery = usePreventiveActions(equipment?.id);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Card variant="outlined">
        <CardContent>
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
            Select Equipment for Forecast
          </Typography>
          <EquipmentSelector value={equipment} onChange={onChange} />
        </CardContent>
      </Card>

      {!equipment ? (
        <Card variant="outlined">
          <CardContent>
            <EmptyState
              icon={<QueryStatsOutlinedIcon sx={{ fontSize: 32, opacity: 0.4 }} />}
              title="Choose an asset to forecast"
              description="Select equipment above to view its remaining useful life, failure risk, and preventive actions."
            />
          </CardContent>
        </Card>
      ) : healthQuery.isLoading || actionsQuery.isLoading ? (
        <LoadingState label="Loading prediction data…" />
      ) : (
        <>
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
              gap: 2,
            }}
          >
            <HealthScoreGauge
              healthScore={healthQuery.data?.health_score ?? equipment.health_score}
              risk={healthQuery.data?.risk ?? equipment.risk_of_failure}
            />
            <RULCard rulDays={healthQuery.data?.rul_days} risk={healthQuery.data?.risk} />
          </Box>
          <PreventiveActionsTable
            actions={actionsQuery.data?.actions ?? []}
            equipmentName={actionsQuery.data?.equipment ?? equipment.equipment_name}
          />
        </>
      )}
    </Box>
  );
}
