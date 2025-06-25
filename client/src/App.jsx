import { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Box, CircularProgress, Typography } from '@mui/material'
import { CustomThemeProvider } from './theme/ThemeContext'
import './App.css'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Quiz from './pages/Quiz'
import axios from 'axios'

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [summary, setSummary] = useState('');
  const [isLoading, setIsLoading] = useState(true);

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
                <Navigate to="/dashboard" replace />
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
            path="/dashboard" 
            element={
              isAuthenticated ? (
                <Dashboard 
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
                />
              ) : (
                <Navigate to="/login" replace />
              )
            } 
          />
          <Route 
            path="/" 
            element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />} 
          />
          <Route 
            path="*" 
            element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />} 
          />
        </Routes>
      </Router>
    </CustomThemeProvider>
  )
}

export default App