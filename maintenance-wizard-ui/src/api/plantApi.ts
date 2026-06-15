import { httpClient } from './httpClient';
import type { Plant } from '@/models/types';

export async function getPlants(): Promise<Plant[]> {
  const { data } = await httpClient.get<Plant[]>('/plants');
  return data;
}

export async function getPlantById(plantId: string): Promise<Plant> {
  const { data } = await httpClient.get<Plant>(`/plants/${plantId}`);
  return data;
}
