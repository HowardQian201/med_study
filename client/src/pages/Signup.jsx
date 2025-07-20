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
  Link,
  IconButton,
  InputAdornment
} from '@mui/material';
import ThemeToggle from '../components/ThemeToggle';
import { Visibility, VisibilityOff } from '@mui/icons-material';

const SignUp = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [name, setName] = useState(''); // New state for name
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!email || !password || !confirmPassword || !name) { // Add name to validation
      setError('All fields are required');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    try {
      setIsLoading(true);
      setError('');

      const response = await axios.post('/api/auth/signup', {
        email,
        password,
        name // Include name in the request body
      });

      if (response.data.success) {
        navigate('/login', { state: { message: 'Account created successfully! Please log in.' } });
      }
    } catch (err) {
      if (err.response?.status === 409) {
        setError('Account with this email already exists.');
      } else {
        setError(err.response?.data?.message || 'Sign up failed');
      }
      console.error('Sign up error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handlePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };

  const handleConfirmPasswordVisibility = () => {
    setShowConfirmPassword(!showConfirmPassword);
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
              <img src="/favicon.png" alt="MedStudyAI Logo" style={{ width: 40, height: 40 }} />
              <Typography 
                component="h1" 
                variant="h4" 
                fontWeight="bold"
                color="text.primary"
              >
                MedStudyAI
              </Typography>
            </Box>
            
            <Typography 
              component="h2" 
              variant="h5" 
              align="center"
              color="text.secondary"
            >
              Create your account
            </Typography>
            
            <Box 
              component="form" 
              onSubmit={handleSubmit}
              sx={{ width: '100%' }}
            >
              <Stack spacing={2}>
                <TextField
                  id="name"
                  name="name"
                  label="Full Name"
                  type="text"
                  variant="outlined"
                  fullWidth
                  required
                  autoComplete="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={isLoading}
                />
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
                  type={showPassword ? "text" : "password"}
                  variant="outlined"
                  fullWidth
                  required
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isLoading}
                  InputProps={{
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          onClick={handlePasswordVisibility}
                          edge="end"
                        >
                          {showPassword ? <VisibilityOff /> : <Visibility />}
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                />

                <TextField
                  id="confirmPassword"
                  name="confirmPassword"
                  label="Confirm Password"
                  type={showConfirmPassword ? "text" : "password"}
                  variant="outlined"
                  fullWidth
                  required
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  disabled={isLoading}
                  InputProps={{
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          onClick={handleConfirmPasswordVisibility}
                          edge="end"
                        >
                          {showConfirmPassword ? <VisibilityOff /> : <Visibility />}
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
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
                  {isLoading ? 'Creating account...' : 'Sign Up'}
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
                  <Typography variant="body2" color="text.secondary">
                    Already have an account? {' '}
                    <Link component="button" onClick={() => navigate('/login')} sx={{ fontWeight: 'bold' }}>
                      Sign in
                    </Link>
                  </Typography>
                </Box>
              </Stack>
            </Box>

            <Box sx={{ mt: 2 }}>
              <ThemeToggle />
            </Box>
          </Stack>
        </CardContent>
      </Card>
    </Container>
  );
};

export default SignUp; 