import { useQuery } from '@tanstack/react-query';
import { getPlantById, getPlants } from '@/api/plantApi';

export function usePlants() {
  return useQuery({
    queryKey: ['plants'],
    queryFn: getPlants,
    staleTime: 5 * 60_000,
  });
}

export function usePlant(plantId: string | undefined) {
  return useQuery({
    queryKey: ['plant', plantId],
    queryFn: () => getPlantById(plantId as string),
    enabled: Boolean(plantId),
    staleTime: 5 * 60_000,
  });
}
