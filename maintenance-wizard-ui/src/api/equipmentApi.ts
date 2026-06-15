import { httpClient } from './httpClient';
import type {
  EquipmentDetail,
  EquipmentFilter,
  EquipmentHealth,
  EquipmentListItem,
  EquipmentStatusItem,
  EquipmentStatusSummary,
  PreventiveActionsResponse,
  SensorReadingInput,
  SensorReadingBatchResponse,
} from '@/models/types';

export async function getEquipment(filters: EquipmentFilter = {}): Promise<EquipmentListItem[]> {
  const params: Record<string, string> = {};
  if (filters.plantId) params.plantId = filters.plantId;
  if (filters.equipmentType) params.equipmentType = filters.equipmentType;
  if (filters.status) params.status = filters.status;
  if (filters.criticality) params.criticality = filters.criticality;

  const { data } = await httpClient.get<EquipmentListItem[]>('/equipment', { params });
  return data;
}

export async function getEquipmentById(equipmentId: string): Promise<EquipmentDetail> {
  const { data } = await httpClient.get<EquipmentDetail>(`/equipment/${equipmentId}`);
  return data;
}

export async function getEquipmentStatus(): Promise<EquipmentStatusItem[]> {
  const { data } = await httpClient.get<EquipmentStatusItem[]>('/equipment/status');
  return data;
}

export async function getEquipmentStatusSummary(): Promise<EquipmentStatusSummary> {
  const { data } = await httpClient.get<EquipmentStatusSummary>('/equipment/status-summary');
  return data;
}

export async function getEquipmentHealth(equipmentId: string): Promise<EquipmentHealth> {
  const { data } = await httpClient.get<EquipmentHealth>(`/equipment/${equipmentId}/health`);
  return data;
}

export async function getPreventiveActions(
  equipmentId: string
): Promise<PreventiveActionsResponse> {
  const { data } = await httpClient.get<PreventiveActionsResponse>(
    `/equipment/${equipmentId}/preventive-actions`
  );
  return data;
}

export async function postSensorReadingsBatch(
  readings: SensorReadingInput[]
): Promise<SensorReadingBatchResponse> {
  const { data } = await httpClient.post<SensorReadingBatchResponse>('/sensor-readings/batch', {
    readings,
  });
  return data;
}
