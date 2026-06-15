import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ChatMessage } from '@/models/types';

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

interface ChatState {
  sessionId: string;
  /** Equipment locked for the session once the first question is asked. */
  equipmentCode: string | null;
  equipmentName: string | null;
  /** Equipment id sent to the agent chat endpoint (as the equipment_code field). */
  equipmentId: string | null;
  messages: ChatMessage[];
  addMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => string;
  setMessageError: (id: string, error: boolean) => void;
  lockEquipment: (id: string, code: string, name: string) => void;
  resetSession: () => void;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      sessionId: generateId(),
      equipmentCode: null,
      equipmentName: null,
      equipmentId: null,
      messages: [],
      addMessage: (message) => {
        const id = generateId();
        set((state) => ({
          messages: [
            ...state.messages,
            { ...message, id, timestamp: new Date().toISOString() },
          ],
        }));
        return id;
      },
      setMessageError: (id, error) =>
        set((state) => ({
          messages: state.messages.map((message) =>
            message.id === id ? { ...message, error } : message
          ),
        })),
      lockEquipment: (id, code, name) =>
        set({ equipmentId: id, equipmentCode: code, equipmentName: name }),
      resetSession: () =>
        set({
          sessionId: generateId(),
          equipmentCode: null,
          equipmentName: null,
          equipmentId: null,
          messages: [],
        }),
    }),
    { name: 'maintenance-wizard-chat-store' }
  )
);
