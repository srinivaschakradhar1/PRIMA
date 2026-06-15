import { Box, CircularProgress, Typography } from '@mui/material';

interface LoadingStateProps {
  label?: string;
  minHeight?: number | string;
}

export default function LoadingState({ label = 'Loading…', minHeight = 240 }: LoadingStateProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 1.5,
        minHeight,
        color: 'text.secondary',
      }}
    >
      <CircularProgress size={28} color="secondary" />
      <Typography variant="body2" sx={{ fontFamily: '"JetBrains Mono", monospace' }}>
        {label}
      </Typography>
    </Box>
  );
}
