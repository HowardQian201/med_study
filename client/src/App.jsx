import { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Box, CircularProgress, Typography } from '@mui/material'
import { CustomThemeProvider } from './theme/ThemeContext'
import './App.css'
import Login from './pages/Login'
import Study_session from './pages/Study_session'
import Quiz from './pages/Quiz'
import Home from './pages/Home'
import Upload_pdfs from './pages/Upload_pdfs'
import Signup from './pages/Signup'
import axios from 'axios'

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [summary, setSummary] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  // Global 401 error handler
  useEffect(() => {
    const interceptor = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          console.log('401 Unauthorized detected, clearing authentication state');
          setIsAuthenticated(false);
          setUser(null);
          setSummary('');
          // Clear any stored session data
          sessionStorage.clear();
          // The route protection will handle redirecting to login
        }
        return Promise.reject(error);
      }
    );

    // Cleanup interceptor on unmount
    return () => {
      axios.interceptors.response.eject(interceptor);
    };
  }, []);

  const checkAuth = async () => {
    setIsLoading(true);
    try {
      const response = await axios.get('/api/auth/check', {
        withCredentials: true
      });
      if (response.data.authenticated) {
        setIsAuthenticated(true);
        setUser(response.data.user);
        setSummary(response.data.summary || '');
      } else {
        setIsAuthenticated(false);
        setUser(null);
        setSummary('');
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      setIsAuthenticated(false);
      setUser(null);
      setSummary('');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    checkAuth();
  }, []);

  // Don't render routes until authentication check is complete
  if (isLoading) {
    return (
      <CustomThemeProvider>
        <Box
          display="flex"
          flexDirection="column"
          alignItems="center"
          justifyContent="center"
          minHeight="100vh"
          bgcolor="background.default"
        >
          <CircularProgress size={48} sx={{ mb: 2 }} />
          <Typography variant="h6" color="text.secondary">
            Loading...
          </Typography>
        </Box>
      </CustomThemeProvider>
    );
  }

  return (
    <CustomThemeProvider>
    <Router>
      <Routes>
        <Route 
          path="/login" 
          element={
            isAuthenticated ? (
              <Navigate to="/" replace />
            ) : (
              <Login 
                setIsAuthenticated={setIsAuthenticated} 
                setUser={setUser} 
                setSummary={setSummary}
              />
            )
          } 
        />
        <Route 
          path="/"
          element={
            isAuthenticated ? (
              <Home
                setIsAuthenticated={setIsAuthenticated}
                user={user}
                setSummary={setSummary}
              />
            ) : (
              <Navigate to="/login" replace />
            )
          }
        />
        <Route 
          path="/study_session" 
          element={
            isAuthenticated ? (
              <Study_session 
                setIsAuthenticated={setIsAuthenticated} 
                user={user}
                summary={summary}
                setSummary={setSummary}
              />
            ) : (
              <Navigate to="/login" replace />
            )
          } 
        />
        <Route 
          path="/quiz" 
          element={
            isAuthenticated ? (
              <Quiz 
                setIsAuthenticated={setIsAuthenticated} 
                user={user}
                summary={summary}
                setSummary={setSummary}
              />
            ) : (
              <Navigate to="/login" replace />
            )
          } 
        />
        <Route 
          path="/upload_pdfs" 
          element={
            isAuthenticated ? (
              <Upload_pdfs 
                setIsAuthenticated={setIsAuthenticated} 
                user={user}
                setSummary={setSummary}
              />
            ) : (
              <Navigate to="/login" replace />
            )
          } 
        />
        <Route 
          path="/signup" 
          element={<Signup />} 
        />
        <Route 
          path="*" 
          element={<Navigate to={isAuthenticated ? "/" : "/login"} replace />} 
        />
      </Routes>
    </Router>
    </CustomThemeProvider>
  )
}

export default App