import { Box, Card, CardContent, Divider, Grid, Typography } from '@mui/material';
import type { EquipmentDetail } from '@/models/types';
import StatusChip from '@/components/common/StatusChip';
import { formatDate } from '@/utils/format';

interface EquipmentSummaryCardProps {
  equipment: EquipmentDetail;
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="body2" sx={{ fontWeight: 600 }}>
        {value}
      </Typography>
    </Box>
  );
}

export default function EquipmentSummaryCard({ equipment }: EquipmentSummaryCardProps) {
  return (
    <Card variant="outlined">
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
          <Box>
            <Typography variant="h5">{equipment.equipment_name}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
              {equipment.equipment_type}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <StatusChip kind="status" value={equipment.health} />
            <StatusChip kind="criticality" value={equipment.criticality} />
          </Box>
        </Box>
        <Divider sx={{ my: 1.5 }} />
        <Grid container spacing={2}>
          <Grid item xs={6} sm={3}>
            <Field label="Manufacturer" value={equipment.manufacturer} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <Field label="Model" value={equipment.model_number} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <Field label="Location" value={equipment.location_in_plant} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <Field label="Expected Life" value={`${equipment.expected_life_days} days`} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <Field label="End of Life" value={formatDate(equipment.expected_end_of_life_date)} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <Field
              label="Risk of Failure"
              value={<StatusChip kind="risk" value={equipment.risk_of_failure} />}
            />
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
}
