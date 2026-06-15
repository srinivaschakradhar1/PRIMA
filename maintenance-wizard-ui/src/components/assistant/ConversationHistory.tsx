import { Avatar, Box, Button, Paper, Typography } from '@mui/material';
import AutoAwesomeOutlinedIcon from '@mui/icons-material/AutoAwesomeOutlined';
import PersonOutlineIcon from '@mui/icons-material/PersonOutline';
import RefreshIcon from '@mui/icons-material/Refresh';
import type { ChatMessage } from '@/models/types';
import MarkdownMessage from './MarkdownMessage';

interface ConversationHistoryProps {
  messages: ChatMessage[];
  onRetry: (message: ChatMessage) => void;
}

export default function ConversationHistory({ messages, onRetry }: ConversationHistoryProps) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {messages.map((message) => {
        const isUser = message.role === 'user';
        return (
          <Box
            key={message.id}
            sx={{
              display: 'flex',
              gap: 1.5,
              alignSelf: isUser ? 'flex-end' : 'flex-start',
              maxWidth: '85%',
              flexDirection: isUser ? 'row-reverse' : 'row',
            }}
          >
            <Avatar
              sx={{
                width: 32,
                height: 32,
                bgcolor: isUser ? 'rgba(127,178,202,0.2)' : 'rgba(255,106,61,0.18)',
                color: isUser ? '#7AA2C2' : 'primary.main',
              }}
            >
              {isUser ? <PersonOutlineIcon fontSize="small" /> : <AutoAwesomeOutlinedIcon fontSize="small" />}
            </Avatar>
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: isUser ? 'flex-end' : 'flex-start',
                gap: 0.5,
              }}
            >
              <Paper
                variant="outlined"
                sx={{
                  p: 1.5,
                  borderRadius: 2,
                  backgroundColor: isUser ? 'rgba(127,178,202,0.06)' : 'rgba(255,106,61,0.05)',
                }}
              >
                {isUser ? (
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                    {message.content}
                  </Typography>
                ) : (
                  <MarkdownMessage content={message.content} />
                )}
              </Paper>
              {isUser && message.error && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Typography variant="caption" color="error">
                    Couldn't get a response.
                  </Typography>
                  <Button
                    size="small"
                    color="error"
                    variant="text"
                    startIcon={<RefreshIcon sx={{ fontSize: 16 }} />}
                    onClick={() => onRetry(message)}
                    sx={{ minWidth: 0, py: 0 }}
                  >
                    Retry
                  </Button>
                </Box>
              )}
            </Box>
          </Box>
        );
      })}
    </Box>
  );
}
