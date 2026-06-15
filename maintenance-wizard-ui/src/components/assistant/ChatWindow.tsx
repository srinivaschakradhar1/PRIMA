import { useEffect, useRef } from 'react';
import { Box, Typography } from '@mui/material';
import AutoAwesomeOutlinedIcon from '@mui/icons-material/AutoAwesomeOutlined';
import type { ChatMessage } from '@/models/types';
import ConversationHistory from './ConversationHistory';
import EmptyState from '@/components/common/EmptyState';
import LoadingState from '@/components/common/LoadingState';

interface ChatWindowProps {
  messages: ChatMessage[];
  isPending: boolean;
  onRetry: (message: ChatMessage) => void;
}

export default function ChatWindow({ messages, isPending, onRetry }: ChatWindowProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, isPending]);

  return (
    <Box
      ref={scrollRef}
      sx={{
        flexGrow: 1,
        overflowY: 'auto',
        p: 2,
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
      }}
    >
      {messages.length === 0 ? (
        <EmptyState
          icon={<AutoAwesomeOutlinedIcon sx={{ fontSize: 36, opacity: 0.4 }} />}
          title="Ask the maintenance copilot anything"
          description='Try: "Why is BF-101 temperature increasing?"'
          sx={{ flexGrow: 1, justifyContent: 'center' }}
        />
      ) : (
        <ConversationHistory messages={messages} onRetry={onRetry} />
      )}
      {isPending && (
        <Box sx={{ mt: 1 }}>
          <LoadingState label="Analyzing equipment context…" minHeight={60} />
        </Box>
      )}
      <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
        {/* anchor for layout */}
      </Typography>
    </Box>
  );
}
