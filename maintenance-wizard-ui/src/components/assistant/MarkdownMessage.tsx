import { Box, Divider, Link, Typography } from '@mui/material';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownMessageProps {
  content: string;
}

// Map markdown nodes onto MUI primitives so assistant replies inherit the app's
// typography, spacing, and color tokens instead of raw browser defaults.
const components: Components = {
  p: ({ children }) => (
    <Typography variant="body2" sx={{ my: 0.75, '&:first-of-type': { mt: 0 }, '&:last-of-type': { mb: 0 } }}>
      {children}
    </Typography>
  ),
  h1: ({ children }) => (
    <Typography variant="subtitle1" sx={{ fontWeight: 700, mt: 1.5, mb: 0.5 }}>
      {children}
    </Typography>
  ),
  h2: ({ children }) => (
    <Typography variant="subtitle1" sx={{ fontWeight: 700, mt: 1.5, mb: 0.5 }}>
      {children}
    </Typography>
  ),
  h3: ({ children }) => (
    <Typography variant="subtitle2" sx={{ fontWeight: 700, mt: 1.25, mb: 0.5 }}>
      {children}
    </Typography>
  ),
  h4: ({ children }) => (
    <Typography variant="subtitle2" sx={{ fontWeight: 700, mt: 1, mb: 0.25 }}>
      {children}
    </Typography>
  ),
  ul: ({ children }) => (
    <Box component="ul" sx={{ my: 0.75, pl: 2.5, '& li': { mb: 0.25 } }}>
      {children}
    </Box>
  ),
  ol: ({ children }) => (
    <Box component="ol" sx={{ my: 0.75, pl: 2.5, '& li': { mb: 0.25 } }}>
      {children}
    </Box>
  ),
  li: ({ children }) => (
    <Typography component="li" variant="body2">
      {children}
    </Typography>
  ),
  a: ({ href, children }) => (
    <Link href={href} target="_blank" rel="noopener noreferrer" color="primary">
      {children}
    </Link>
  ),
  strong: ({ children }) => (
    <Box component="strong" sx={{ fontWeight: 700 }}>
      {children}
    </Box>
  ),
  em: ({ children }) => (
    <Box component="em" sx={{ fontStyle: 'italic' }}>
      {children}
    </Box>
  ),
  blockquote: ({ children }) => (
    <Box
      component="blockquote"
      sx={{
        my: 1,
        pl: 1.5,
        ml: 0,
        borderLeft: '3px solid',
        borderColor: 'divider',
        color: 'text.secondary',
      }}
    >
      {children}
    </Box>
  ),
  hr: () => <Divider sx={{ my: 1 }} />,
  code: ({ className, children }) => {
    const isBlock = Boolean(className);
    if (isBlock) {
      return (
        <Box
          component="code"
          sx={{
            fontFamily: 'monospace',
            fontSize: '0.8125rem',
            whiteSpace: 'pre',
          }}
        >
          {children}
        </Box>
      );
    }
    return (
      <Box
        component="code"
        sx={{
          fontFamily: 'monospace',
          fontSize: '0.8125rem',
          bgcolor: 'rgba(127,178,202,0.12)',
          px: 0.5,
          py: 0.125,
          borderRadius: 0.5,
        }}
      >
        {children}
      </Box>
    );
  },
  pre: ({ children }) => (
    <Box
      component="pre"
      sx={{
        my: 1,
        p: 1.25,
        borderRadius: 1,
        bgcolor: 'rgba(0,0,0,0.25)',
        border: '1px solid',
        borderColor: 'divider',
        overflowX: 'auto',
      }}
    >
      {children}
    </Box>
  ),
  table: ({ children }) => (
    <Box sx={{ overflowX: 'auto', my: 1 }}>
      <Box
        component="table"
        sx={{
          borderCollapse: 'collapse',
          width: '100%',
          fontSize: '0.8125rem',
          '& th, & td': {
            border: '1px solid',
            borderColor: 'divider',
            px: 1,
            py: 0.5,
            textAlign: 'left',
          },
          '& th': { fontWeight: 700, bgcolor: 'rgba(127,178,202,0.08)' },
        }}
      >
        {children}
      </Box>
    </Box>
  ),
};

export default function MarkdownMessage({ content }: MarkdownMessageProps) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {content}
    </ReactMarkdown>
  );
}
