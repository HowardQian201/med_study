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
  Divider
} from '@mui/material';
import { Login as LoginIcon } from '@mui/icons-material';
import ThemeToggle from '../components/ThemeToggle';
import GoogleLoginButton from '../components/GoogleLoginButton';

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
          navigate('/dashboard');
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

  const handleGoogleSuccess = async (googleUser) => {
    try {
      setIsLoading(true);
      setError('');
      
      console.log('Google login success:', googleUser);
      
      // Send the credential to our backend
      const response = await axios.post('/api/auth/google', {
        credential: googleUser.credential
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
          navigate('/dashboard');
        }
      }
    } catch (err) {
      console.error('Google login error:', err);
      setError(err.response?.data?.message || 'Google login failed');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleError = (error) => {
    console.error('Google login error:', error);
    setError('Google login failed. Please try again.');
  };

  return (
    <Container 
      component="main" 
      maxWidth="sm"
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
      {/* Theme Toggle Button */}
      <Box
        sx={{
          position: 'absolute',
          top: 16,
          right: 16,
          zIndex: 1000
        }}
      >
        <ThemeToggle />
      </Box>

      <Card 
        elevation={3}
        sx={{
          width: '100%',
          maxWidth: 400,
          p: 2
        }}
      >
        <CardContent>
          <Stack spacing={3} alignItems="center">
            <LoginIcon 
              sx={{ 
                fontSize: 48, 
                color: 'primary.main' 
              }} 
            />
            
            <Typography 
              component="h1" 
              variant="h4" 
              align="center"
              fontWeight="bold"
              color="text.primary"
            >
              Sign in to your account
            </Typography>

            {/* Google Login Button */}
            <Box sx={{ width: '100%' }}>
              <GoogleLoginButton
                onSuccess={handleGoogleSuccess}
                onError={handleGoogleError}
                disabled={isLoading}
              />
            </Box>

            <Divider sx={{ width: '100%', my: 2 }}>
              <Typography variant="body2" color="text.secondary">
                or continue with email
              </Typography>
            </Divider>
            
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
                  startIcon={isLoading ? <CircularProgress size={20} color="inherit" /> : <LoginIcon />}
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
                  <Typography variant="body2" color="text.primary" fontWeight="600">
                    Demo credentials:
                  </Typography>
                  <Typography variant="body2" color="text.primary" sx={{ mt: 0.5 }}>
                    test@example.com / password123
                  </Typography>
                </Box>
              </Stack>
            </Box>
          </Stack>
        </CardContent>
      </Card>
    </Container>
  );
};

export default Login; 