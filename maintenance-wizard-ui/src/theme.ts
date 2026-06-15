import { createTheme, type ThemeOptions } from '@mui/material/styles';

// Design tokens
// Base: deep furnace-slate (#0B1F2A / #11293A)
// Accent: molten steel orange (#FF6A3D)
// Secondary: circuit green (#3DDC97) for healthy/positive states
// Warning amber (#FFB454), Danger ember red (#E84855)
// Display face: Space Grotesk, Body: Inter, Data/mono: JetBrains Mono

const baseTokens = {
  furnace: '#FF6A3D',
  furnaceDark: '#E2521F',
  circuit: '#3DDC97',
  amber: '#FFB454',
  ember: '#E84855',
  slateDeep: '#0B1F2A',
  slateMid: '#11293A',
  slatePanel: '#162E40',
  slateLine: '#27435A',
  textPrimary: '#EAF1F5',
  textSecondary: '#9FB3C2',
};

const sharedTypography: ThemeOptions['typography'] = {
  fontFamily: '"Inter", "Helvetica Neue", Arial, sans-serif',
  h1: { fontFamily: '"Space Grotesk", sans-serif', fontWeight: 700, letterSpacing: '-0.02em' },
  h2: { fontFamily: '"Space Grotesk", sans-serif', fontWeight: 700, letterSpacing: '-0.01em' },
  h3: { fontFamily: '"Space Grotesk", sans-serif', fontWeight: 600 },
  h4: { fontFamily: '"Space Grotesk", sans-serif', fontWeight: 600 },
  h5: { fontFamily: '"Space Grotesk", sans-serif', fontWeight: 600 },
  h6: { fontFamily: '"Space Grotesk", sans-serif', fontWeight: 600 },
  subtitle1: { fontWeight: 500 },
  subtitle2: { fontWeight: 500, letterSpacing: '0.04em', textTransform: 'uppercase' as const },
  button: { fontWeight: 600, textTransform: 'none' as const },
  overline: {
    fontFamily: '"JetBrains Mono", monospace',
    letterSpacing: '0.12em',
    fontWeight: 500,
  },
};

export const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: baseTokens.furnace, dark: baseTokens.furnaceDark, contrastText: '#0B1F2A' },
    secondary: { main: baseTokens.circuit, contrastText: '#0B1F2A' },
    warning: { main: baseTokens.amber },
    error: { main: baseTokens.ember },
    background: {
      default: baseTokens.slateDeep,
      paper: baseTokens.slatePanel,
    },
    text: {
      primary: baseTokens.textPrimary,
      secondary: baseTokens.textSecondary,
    },
    divider: baseTokens.slateLine,
  },
  shape: { borderRadius: 10 },
  typography: sharedTypography,
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundImage:
            'radial-gradient(circle at 15% 0%, rgba(255,106,61,0.06), transparent 45%), radial-gradient(circle at 85% 100%, rgba(61,220,151,0.05), transparent 40%)',
        },
        '::-webkit-scrollbar': { width: 8, height: 8 },
        '::-webkit-scrollbar-thumb': {
          backgroundColor: baseTokens.slateLine,
          borderRadius: 8,
        },
        '::-webkit-scrollbar-track': { backgroundColor: 'transparent' },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: baseTokens.slateMid,
          backgroundImage: 'none',
          borderBottom: `1px solid ${baseTokens.slateLine}`,
          boxShadow: 'none',
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: baseTokens.slateMid,
          backgroundImage: 'none',
          borderRight: `1px solid ${baseTokens.slateLine}`,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
        outlined: {
          borderColor: baseTokens.slateLine,
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundColor: baseTokens.slatePanel,
          border: `1px solid ${baseTokens.slateLine}`,
          backgroundImage: 'none',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
        },
        containedPrimary: {
          color: '#0B1F2A',
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 600,
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        head: {
          fontFamily: '"JetBrains Mono", monospace',
          fontSize: '0.7rem',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          color: baseTokens.textSecondary,
          borderBottom: `1px solid ${baseTokens.slateLine}`,
        },
        body: {
          borderBottom: `1px solid ${baseTokens.slateLine}`,
        },
      },
    },
    MuiLinearProgress: {
      styleOverrides: {
        root: {
          borderRadius: 4,
          backgroundColor: 'rgba(255,255,255,0.06)',
        },
      },
    },
  },
});

export const lightTheme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: baseTokens.furnaceDark, contrastText: '#FFFFFF' },
    secondary: { main: '#1F9D6E', contrastText: '#FFFFFF' },
    warning: { main: '#C97A12' },
    error: { main: baseTokens.ember },
    background: {
      default: '#F2F5F7',
      paper: '#FFFFFF',
    },
    text: {
      primary: '#0B1F2A',
      secondary: '#54707F',
    },
    divider: '#D9E2E8',
  },
  shape: { borderRadius: 10 },
  typography: sharedTypography,
  components: {
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#FFFFFF',
          color: '#0B1F2A',
          boxShadow: 'none',
          borderBottom: '1px solid #D9E2E8',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          border: '1px solid #D9E2E8',
          backgroundImage: 'none',
        },
      },
    },
  },
});

export const statusColors: Record<string, string> = {
  UP: baseTokens.circuit,
  RUNNING: baseTokens.circuit,
  FAILED: baseTokens.ember,
  SCHEDULED_DOWN: baseTokens.amber,
  MAINTENANCE: '#7AA2C2',
};

export const riskColors: Record<string, string> = {
  LOW: baseTokens.circuit,
  MEDIUM: baseTokens.amber,
  HIGH: baseTokens.furnace,
  CRITICAL: baseTokens.ember,
};

export const criticalityColors: Record<string, string> = {
  LOW: '#7AA2C2',
  MEDIUM: baseTokens.amber,
  HIGH: baseTokens.furnace,
  CRITICAL: baseTokens.ember,
};

export { baseTokens };
