import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getEquipment,
  getEquipmentById,
  getEquipmentHealth,
  getEquipmentStatus,
  getEquipmentStatusSummary,
  getPreventiveActions,
  postSensorReadingsBatch,
} from '@/api/equipmentApi';
import type { EquipmentFilter, SensorReadingInput } from '@/models/types';

export function useEquipmentList(filters: EquipmentFilter = {}) {
  return useQuery({
    queryKey: ['equipment', filters],
    queryFn: () => getEquipment(filters),
    staleTime: 30_000,
  });
}

export function useEquipmentDetail(equipmentId: string | undefined) {
  return useQuery({
    queryKey: ['equipment-detail', equipmentId],
    queryFn: () => getEquipmentById(equipmentId as string),
    enabled: Boolean(equipmentId),
  });
}

export function useEquipmentStatus() {
  return useQuery({
    queryKey: ['equipment-status'],
    queryFn: getEquipmentStatus,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useEquipmentStatusSummary() {
  return useQuery({
    queryKey: ['equipment-status-summary'],
    queryFn: getEquipmentStatusSummary,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useEquipmentHealth(equipmentId: string | undefined) {
  return useQuery({
    queryKey: ['equipment-health', equipmentId],
    queryFn: () => getEquipmentHealth(equipmentId as string),
    enabled: Boolean(equipmentId),
  });
}

export function usePreventiveActions(equipmentId: string | undefined) {
  return useQuery({
    queryKey: ['preventive-actions', equipmentId],
    queryFn: () => getPreventiveActions(equipmentId as string),
    enabled: Boolean(equipmentId),
  });
}

export function useSubmitSensorReadings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (readings: SensorReadingInput[]) => postSensorReadingsBatch(readings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['equipment'] });
      queryClient.invalidateQueries({ queryKey: ['equipment-status'] });
      queryClient.invalidateQueries({ queryKey: ['equipment-status-summary'] });
    },
  });
}
