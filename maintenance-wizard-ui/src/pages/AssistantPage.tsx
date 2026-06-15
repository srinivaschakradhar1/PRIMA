import { useState } from 'react';
import { Box, Button, Paper, Typography } from '@mui/material';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import { useChatStore } from '@/store/chatStore';
import { useAgentChat } from '@/hooks/useAgent';
import { useEquipmentList } from '@/hooks/useEquipment';
import ChatWindow from '@/components/assistant/ChatWindow';
import PromptInput from '@/components/assistant/PromptInput';
import type { ChatMessage, EquipmentListItem } from '@/models/types';

export default function AssistantPage() {
  const {
    sessionId,
    equipmentCode,
    equipmentName,
    equipmentId,
    messages,
    addMessage,
    setMessageError,
    lockEquipment,
    resetSession,
  } = useChatStore();
  const chatMutation = useAgentChat();
  const { data: equipmentList, isLoading: equipmentLoading } = useEquipmentList();

  const [selectedEquipment, setSelectedEquipment] = useState<EquipmentListItem | null>(null);

  const lockedEquipmentLabel =
    equipmentCode != null ? `${equipmentCode} — ${equipmentName ?? ''}`.trim() : null;

  const sendChat = (
    message: string,
    userMessageId: string,
    id: string,
    history: ChatMessage[]
  ) => {
    setMessageError(userMessageId, false);
    chatMutation.mutate(
      {
        session_id: sessionId,
        equipment_code: id,
        conversation_history: history.map(({ role, content }) => ({ role, content })),
        message,
      },
      {
        onSuccess: (response) => {
          addMessage({ role: 'assistant', content: response.response });
        },
        onError: () => {
          setMessageError(userMessageId, true);
        },
      }
    );
  };

  const handleSubmit = (message: string) => {
    // Equipment is locked on the first question; reuse it for every follow-up.
    const id = equipmentId ?? selectedEquipment?.id;
    const code = equipmentCode ?? selectedEquipment?.equipment_code;
    const name = equipmentName ?? selectedEquipment?.equipment_name;
    if (!id || !code) return;

    if (equipmentId == null) {
      lockEquipment(id, code, name ?? '');
    }

    // Capture the conversation so far (excludes the new turn) before appending it.
    const history = messages;
    const userMessageId = addMessage({ role: 'user', content: message });
    sendChat(message, userMessageId, id, history);
  };

  const handleRetry = (message: ChatMessage) => {
    const id = equipmentId ?? selectedEquipment?.id;
    if (!id || chatMutation.isPending) return;
    // Replay the conversation up to (but not including) the message being retried.
    const retryIndex = messages.findIndex((m) => m.id === message.id);
    const history = retryIndex === -1 ? messages : messages.slice(0, retryIndex);
    sendChat(message.content, message.id, id, history);
  };

  const handleNewSession = () => {
    resetSession();
    setSelectedEquipment(null);
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, height: '100%' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Box>
          <Typography variant="h4" gutterBottom>
            AI Maintenance Assistant
          </Typography>
          <Typography variant="body2" color="text.secondary">
            General-purpose maintenance copilot grounded in your equipment manuals, logs, and sensor history.
          </Typography>
        </Box>
        <Button
          size="small"
          startIcon={<RestartAltIcon />}
          onClick={handleNewSession}
          disabled={messages.length === 0 && equipmentCode == null}
        >
          New Session
        </Button>
      </Box>

      <Paper
        variant="outlined"
        sx={{
          display: 'flex',
          flexDirection: 'column',
          height: { xs: 'calc(100vh - 280px)', md: 'calc(100vh - 260px)' },
          minHeight: 420,
        }}
      >
        <ChatWindow
          messages={messages}
          isPending={chatMutation.isPending}
          onRetry={handleRetry}
        />
        <Box sx={{ borderTop: '1px solid', borderColor: 'divider', p: 1.5 }}>
          <PromptInput
            equipmentOptions={equipmentList ?? []}
            equipmentLoading={equipmentLoading}
            selectedEquipment={selectedEquipment}
            onEquipmentChange={setSelectedEquipment}
            lockedEquipmentLabel={lockedEquipmentLabel}
            onSubmit={handleSubmit}
            disabled={chatMutation.isPending}
          />
        </Box>
      </Paper>
    </Box>
  );
}
