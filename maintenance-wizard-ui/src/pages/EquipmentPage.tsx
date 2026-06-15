import { useState } from 'react';
import { Box, Typography } from '@mui/material';
import type { EquipmentFilter, EquipmentListItem } from '@/models/types';
import { useEquipmentList, useEquipmentDetail } from '@/hooks/useEquipment';
import EquipmentFilterPanel from '@/components/equipment/EquipmentFilterPanel';
import EquipmentTable from '@/components/equipment/EquipmentTable';
import LoadingState from '@/components/common/LoadingState';
import ErrorState from '@/components/common/ErrorState';

export default function EquipmentPage() {
  const [filters, setFilters] = useState<EquipmentFilter>({});
  const [selectedEquipmentId, setSelectedEquipmentId] = useState<string | undefined>(undefined);

  const { data, isLoading, isError, error, refetch } = useEquipmentList(filters);
  const detail = useEquipmentDetail(selectedEquipmentId);

  // When an equipment is selected, load that single row from GET /equipment/{equipment_id}.
  const selectedListItem = data?.find((item) => item.id === selectedEquipmentId);
  const selectedRow: EquipmentListItem | undefined =
    selectedEquipmentId && detail.data
      ? {
          id: selectedEquipmentId,
          equipment_code: detail.data.equipment_code,
          equipment_name: detail.data.equipment_name,
          status: selectedListItem?.status ?? '',
          health_score: detail.data.health_score,
          risk_of_failure: detail.data.risk_of_failure,
          equipment_type: detail.data.equipment_type,
          criticality: detail.data.criticality,
          location_in_plant: detail.data.location_in_plant,
        }
      : undefined;

  const showDetailLoading = Boolean(selectedEquipmentId) && detail.isLoading;
  const showDetailError = Boolean(selectedEquipmentId) && detail.isError;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box>
        <Typography variant="h4" gutterBottom>
          Equipment
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Browse and filter all monitored assets across the plant.
        </Typography>
      </Box>

      <EquipmentFilterPanel
        filters={filters}
        onChange={setFilters}
        equipmentOptions={data ?? []}
        selectedEquipmentId={selectedEquipmentId}
        onSelectEquipment={setSelectedEquipmentId}
      />

      {isLoading && <LoadingState label="Loading equipment…" />}
      {isError && <ErrorState message={error?.message} onRetry={() => refetch()} />}

      {showDetailLoading && <LoadingState label="Loading equipment…" />}
      {showDetailError && (
        <ErrorState message={detail.error?.message} onRetry={() => detail.refetch()} />
      )}

      {selectedEquipmentId
        ? selectedRow && <EquipmentTable equipment={[selectedRow]} />
        : data && <EquipmentTable equipment={data} />}
    </Box>
  );
}
