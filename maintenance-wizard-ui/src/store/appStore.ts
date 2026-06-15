import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AppState {
  selectedEquipmentId: string | null;
  setSelectedEquipmentId: (id: string | null) => void;

  currentPlantId: string | null;
  setCurrentPlantId: (id: string | null) => void;

  themeMode: 'dark' | 'light';
  toggleThemeMode: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      selectedEquipmentId: null,
      setSelectedEquipmentId: (id) => set({ selectedEquipmentId: id }),

      currentPlantId: null,
      setCurrentPlantId: (id) => set({ currentPlantId: id }),

      themeMode: 'dark',
      toggleThemeMode: () =>
        set((state) => ({ themeMode: state.themeMode === 'dark' ? 'light' : 'dark' })),
    }),
    { name: 'maintenance-wizard-app-store' }
  )
);
