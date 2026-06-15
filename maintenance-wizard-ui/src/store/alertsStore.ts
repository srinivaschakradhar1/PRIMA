import { create } from 'zustand';

interface AlertsState {
  unreadCount: number;
  setUnreadCount: (count: number) => void;
  decrementUnread: () => void;
  markAllRead: () => void;
}

export const useAlertsStore = create<AlertsState>((set) => ({
  unreadCount: 0,
  setUnreadCount: (count) => set({ unreadCount: count }),
  decrementUnread: () => set((state) => ({ unreadCount: Math.max(0, state.unreadCount - 1) })),
  markAllRead: () => set({ unreadCount: 0 }),
}));
