import React, { createContext, useContext, useState } from 'react';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';

// Base theme configuration
const getTheme = (mode) => createTheme({
  palette: {
    mode: mode,
    primary: {
      main: mode === 'light' ? '#1976d2' : '#1565c0',
      light: mode === 'light' ? '#42a5f5' : '#1976d2',
      dark: mode === 'light' ? '#1565c0' : '#0d47a1',
      contrastText: '#ffffff',
    },
    secondary: {
      main: mode === 'light' ? '#388e3c' : '#81c784',
      light: mode === 'light' ? '#81c784' : '#a5d6a7',
      dark: mode === 'light' ? '#2e7d32' : '#66bb6a',
      contrastText: '#ffffff',
    },
    success: {
      main: mode === 'light' ? '#388e3c' : '#81c784',
      light: mode === 'light' ? '#f1f8f1' : '#81c784',
      dark: mode === 'light' ? '#2e7d32' : '#5e8860',
    },
    background: {
      default: mode === 'light' ? '#f5f7fa' : '#121212',
      paper: mode === 'light' ? '#ffffff' : '#1e1e1e',
    },
    text: {
      primary: mode === 'light' ? '#2c3e50' : '#ffffff',
      secondary: mode === 'light' ? '#546e7a' : '#b0bec5',
    },
  },
  typography: {
    fontFamily: [
      'Inter',
      'Roboto',
      'Arial',
      'sans-serif',
    ].join(','),
    h1: {
      fontSize: '2.5rem',
      fontWeight: 700,
      lineHeight: 1.2,
    },
    h2: {
      fontSize: '2rem',
      fontWeight: 600,
      lineHeight: 1.3,
    },
    h3: {
      fontSize: '1.75rem',
      fontWeight: 600,
      lineHeight: 1.3,
    },
    h4: {
      fontSize: '1.5rem',
      fontWeight: 600,
      lineHeight: 1.4,
    },
    h5: {
      fontSize: '1.25rem',
      fontWeight: 600,
      lineHeight: 1.4,
    },
    h6: {
      fontSize: '1.125rem',
      fontWeight: 600,
      lineHeight: 1.4,
    },
    body1: {
      fontSize: '1rem',
      lineHeight: 1.6,
    },
    body2: {
      fontSize: '0.875rem',
      lineHeight: 1.6,
    },
    button: {
      fontWeight: 600,
      textTransform: 'none',
    },
  },
  spacing: 8,
  shape: {
    borderRadius: 12,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          padding: '10px 24px',
          fontSize: '0.95rem',
          fontWeight: 600,
          textTransform: 'none',
          boxShadow: 'none',
          '&:hover': {
            boxShadow: mode === 'light' ? '0 4px 12px rgba(0,0,0,0.15)' : '0 4px 12px rgba(255,255,255,0.1)',
          },
        },
        contained: {
          '&:hover': {
            boxShadow: mode === 'light' ? '0 6px 16px rgba(0,0,0,0.2)' : '0 6px 16px rgba(255,255,255,0.15)',
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 16,
          boxShadow: mode === 'light' ? '0 4px 20px rgba(0,0,0,0.08)' : '0 4px 20px rgba(0,0,0,0.4)',
          border: mode === 'light' ? '1px solid rgba(0,0,0,0.06)' : '1px solid rgba(255,255,255,0.1)',
          '&:hover': {
            boxShadow: mode === 'light' ? '0 8px 32px rgba(0,0,0,0.12)' : '0 8px 32px rgba(0,0,0,0.6)',
          },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 12,
            '&:hover .MuiOutlinedInput-notchedOutline': {
              borderColor: mode === 'light' ? '#1976d2' : '#1565c0',
            },
          },
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          fontSize: '0.875rem',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 12,
        },
        elevation1: {
          boxShadow: mode === 'light' ? '0 2px 12px rgba(0,0,0,0.08)' : '0 2px 12px rgba(0,0,0,0.3)',
        },
        elevation2: {
          boxShadow: mode === 'light' ? '0 4px 20px rgba(0,0,0,0.1)' : '0 4px 20px rgba(0,0,0,0.4)',
        },
        elevation3: {
          boxShadow: mode === 'light' ? '0 8px 32px rgba(0,0,0,0.12)' : '0 8px 32px rgba(0,0,0,0.5)',
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          fontWeight: 500,
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: mode === 'light' ? '#ffffff' : undefined,
        },
      },
    },
  },
});

// Create the context
const ThemeContext = createContext();

// Theme provider component
export const CustomThemeProvider = ({ children }) => {
  const [mode, setMode] = useState(() => {
    // Get saved theme from localStorage or default to 'light'
    return localStorage.getItem('themeMode') || 'light';
  });

  const theme = getTheme(mode);

  const toggleTheme = () => {
    const newMode = mode === 'light' ? 'dark' : 'light';
    setMode(newMode);
    localStorage.setItem('themeMode', newMode);
  };

  const contextValue = {
    mode,
    toggleTheme,
    theme,
  };

  return (
    <ThemeContext.Provider value={contextValue}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ThemeContext.Provider>
  );
};

// Custom hook to use the theme context
export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a CustomThemeProvider');
  }
  return context;
};

export default CustomThemeProvider; 