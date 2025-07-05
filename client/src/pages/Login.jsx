import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  Box,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  Alert,
  Container,
  CircularProgress,
  Stack,
  Link
} from '@mui/material';
import ThemeToggle from '../components/ThemeToggle';

const Login = ({ setIsAuthenticated, setUser, setSummary }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Simple validation
    if (!email || !password) {
      setError('Email and password are required');
      return;
    }

    try {
      setIsLoading(true);
      setError('');
      
      const response = await axios.post('/api/auth/login', {
        email,
        password
      }, {
        withCredentials: true
      });

      if (response.data.success) {
        // Get user info after successful login
        const userResponse = await axios.get('/api/auth/check', {
          withCredentials: true
        });
        
        if (userResponse.data.authenticated) {
          setIsAuthenticated(true);
          setUser(userResponse.data.user);
          setSummary(userResponse.data.summary || '');
          navigate('/');
        }
      }
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Invalid credentials');
      } else {
        setError(err.response?.data?.message || 'Login failed');
      }
      console.error('Login error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Container 
      component="main" 
      maxWidth="xl"
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'background.default',
        py: 3,
        position: 'relative'
      }}
    >
      <Card 
        elevation={3}
        sx={{
          width: '100%',
          minWidth: 400,
          maxWidth: 700,
          p: 2
        }}
      >
        <CardContent>
          <Stack spacing={3} alignItems="center">
            <Box display="flex" alignItems="center" gap={1.5}>
              <img src="/favicon.png" alt="MedStudy.AI Logo" style={{ width: 40, height: 40 }} />
              <Typography 
                component="h1" 
                variant="h4" 
                fontWeight="bold"
                color="text.primary"
              >
                MedStudy.AI
              </Typography>
            </Box>
            
            <Typography 
              component="h2" 
              variant="h5" 
              align="center"
              color="text.secondary"
            >
              Sign in to your account
            </Typography>
            
            <Box 
              component="form" 
              onSubmit={handleSubmit}
              sx={{ width: '100%' }}
            >
              <Stack spacing={2}>
                <TextField
                  id="email"
                  name="email"
                  label="Email address"
                  type="email"
                  variant="outlined"
                  fullWidth
                  required
                  autoComplete="email"
                  autoFocus
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={isLoading}
                />
                
                <TextField
                  id="password"
                  name="password"
                  label="Password"
                  type="password"
                  variant="outlined"
                  fullWidth
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isLoading}
                />

                {error && (
                  <Alert severity="error" sx={{ mt: 2 }}>
                    {error}
                  </Alert>
                )}

                <Button
                  type="submit"
                  fullWidth
                  variant="contained"
                  size="large"
                  disabled={isLoading}
                  startIcon={isLoading ? <CircularProgress size={20} color="inherit" /> : undefined}
                  sx={{ 
                    mt: 3, 
                    py: 1.5,
                    fontSize: '1rem',
                    fontWeight: 'medium'
                  }}
                >
                  {isLoading ? 'Signing in...' : 'Sign in'}
                </Button>
                
                <Box 
                  sx={{ 
                    mt: 2, 
                    p: 2, 
                    backgroundColor: 'action.hover', 
                    borderRadius: 1,
                    textAlign: 'center',
                    border: '1px solid',
                    borderColor: 'divider'
                  }}
                >
                  <Typography variant="h5" color="text.primary" fontWeight="600">
                    Sign up:
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                    Email hhqian17@gmail.com for a new account
                  </Typography>
                </Box>
              </Stack>
            </Box>

            {/* Theme Toggle at bottom of card */}
            <Box sx={{ mt: 2 }}>
              <ThemeToggle />
            </Box>
          </Stack>
        </CardContent>
      </Card>
    </Container>
  );
};

export default Login; 