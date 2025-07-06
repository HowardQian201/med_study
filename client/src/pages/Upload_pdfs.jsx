import React from 'react';
import { Box, Typography, Container, AppBar, Toolbar, Stack, Button } from '@mui/material';
import { Home as HomeIcon, Logout } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import ThemeToggle from '../components/ThemeToggle';
import FeedbackButton from '../components/FeedbackButton';
import axios from 'axios';

const Upload_pdfs = ({ setIsAuthenticated, user, setSummary }) => {
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      // Assuming logout clears session on backend
      await axios.post('/api/auth/logout', {}, { withCredentials: true });
      setIsAuthenticated(false);
      navigate('/login');
    } catch (err) {
      console.error('Logout failed:', err);
      setIsAuthenticated(false);
      navigate('/login');
    }
  };

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      {/* App Bar */}
      <AppBar position="static" color="default" elevation={1}>
        <Container maxWidth="false">
          <Box sx={{ maxWidth: '100%', mx: 'auto' }}>
            <Toolbar>
              <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <img src="/favicon.png" alt="MedStudy.AI Logo" style={{ width: 28, height: 28 }} />
                <Typography variant="h6" component="h1" sx={{ fontWeight: 600 }}>
                  MedStudy.AI
                </Typography>
                <Button
                  onClick={async () => {
                    try {
                      // Clear session content on the server
                      await axios.post('/api/clear-session-content', {}, { withCredentials: true });
                      // Clear summary in App.js state
                      setSummary('');
                      // Navigate to home
                      navigate('/');
                    } catch (err) {
                      console.error('Failed to clear session and navigate:', err);
                      // Still attempt to navigate even if clearing fails
                      navigate('/');
                    }
                  }}
                  variant="outlined"
                  startIcon={<HomeIcon />}
                  size="small"
                  sx={{ ml: 1 }}
                >
                  Home
                </Button>
              </Box>
              <Stack direction="row" spacing={2} alignItems="center">
                <Typography variant="body2" color="text.secondary">
                  Welcome, {user?.name}
                </Typography>
                <ThemeToggle size="small" />
                <Button
                  onClick={handleLogout}
                  variant="outlined"
                  color="primary"
                  startIcon={<Logout />}
                  size="small"
                >
                  Logout
                </Button>
              </Stack>
            </Toolbar>
          </Box>
        </Container>
      </AppBar>

      {/* Main Content */}
      <Container maxWidth="md" sx={{ py: 4, textAlign: 'center' }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Upload PDFs
        </Typography>
        <Typography variant="body1" color="text.secondary">
          This is where you will upload your PDF files.
        </Typography>
      </Container>
      <FeedbackButton />
    </Box>
  );
};

export default Upload_pdfs; 