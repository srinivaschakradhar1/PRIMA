import { Alert, AlertTitle, Button, Box } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

export default function ErrorState({
  title = 'Could not load data',
  message = 'The maintenance API did not respond as expected. Confirm the backend is running on localhost:8080.',
  onRetry,
}: ErrorStateProps) {
  return (
    <Alert
      severity="error"
      variant="outlined"
      action={
        onRetry ? (
          <Button color="error" size="small" startIcon={<RefreshIcon />} onClick={onRetry}>
            Retry
          </Button>
        ) : undefined
      }
      sx={{ borderRadius: 2 }}
    >
      <AlertTitle>{title}</AlertTitle>
      <Box sx={{ fontFamily: '"JetBrains Mono", monospace', fontSize: '0.8rem' }}>{message}</Box>
    </Alert>
  );
}
