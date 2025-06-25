import React from 'react';
import { Box, Tooltip } from '@mui/material';
import { DarkMode, LightMode } from '@mui/icons-material';
import { useTheme } from '../theme/ThemeContext';

const ThemeToggle = ({ size = 'medium', ...props }) => {
  const { mode, toggleTheme } = useTheme();
  
  const sizeMap = {
    small: { width: 48, height: 24, iconSize: 16 },
    medium: { width: 56, height: 28, iconSize: 18 },
    large: { width: 64, height: 32, iconSize: 20 }
  };
  
  const dimensions = sizeMap[size] || sizeMap.medium;

  return (
    <Tooltip title={`Switch to ${mode === 'light' ? 'dark' : 'light'} mode`}>
      <Box
        onClick={toggleTheme}
        sx={{
          width: dimensions.width,
          height: dimensions.height,
          backgroundColor: mode === 'light' ? '#e0e0e0' : '#424242',
          borderRadius: dimensions.height / 2,
          position: 'relative',
          cursor: 'pointer',
          transition: 'all 0.3s ease',
          display: 'flex',
          alignItems: 'center',
          padding: '2px',
          border: '1px solid',
          borderColor: mode === 'light' ? '#bdbdbd' : '#616161',
          '&:hover': {
            backgroundColor: mode === 'light' ? '#d5d5d5' : '#525252',
            transform: 'scale(1.05)',
          },
          '&:active': {
            transform: 'scale(0.98)',
          },
          ...props.sx
        }}
        {...props}
      >
        {/* Background icons */}
        <Box
          sx={{
            position: 'absolute',
            left: 6,
            display: 'flex',
            alignItems: 'center',
            opacity: mode === 'light' ? 0.4 : 0.8,
            transition: 'opacity 0.3s ease',
          }}
        >
          <LightMode sx={{ fontSize: dimensions.iconSize, color: '#ffa726' }} />
        </Box>
        
        <Box
          sx={{
            position: 'absolute',
            right: 6,
            display: 'flex',
            alignItems: 'center',
            opacity: mode === 'dark' ? 0.4 : 0.8,
            transition: 'opacity 0.3s ease',
          }}
        >
          <DarkMode sx={{ fontSize: dimensions.iconSize, color: '#5c6bc0' }} />
        </Box>

        {/* Sliding toggle circle */}
        <Box
          sx={{
            width: dimensions.height - 6,
            height: dimensions.height - 6,
            backgroundColor: '#ffffff',
            borderRadius: '50%',
            position: 'absolute',
            left: mode === 'light' ? 3 : dimensions.width - dimensions.height + 3,
            transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
            border: '1px solid rgba(0,0,0,0.1)',
          }}
        >
          {/* Active icon in the circle */}
          {mode === 'light' ? (
            <LightMode sx={{ 
              fontSize: dimensions.iconSize - 2, 
              color: '#ffa726',
              opacity: 0.8 
            }} />
          ) : (
            <DarkMode sx={{ 
              fontSize: dimensions.iconSize - 2, 
              color: '#5c6bc0',
              opacity: 0.8 
            }} />
          )}
        </Box>
      </Box>
    </Tooltip>
  );
};

export default ThemeToggle; 