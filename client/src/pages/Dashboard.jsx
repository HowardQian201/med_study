import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  Button,
  Container,
  Card,
  CardContent,
  Alert,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Stack,
  Divider,
  Paper,
  Chip,
  Grid,
  TextField
} from '@mui/material';
import {
  CloudUpload,
  Quiz,
  Refresh,
  Clear,
  Cancel,
  Logout,
  Description
} from '@mui/icons-material';
import ThemeToggle from '../components/ThemeToggle';

const Dashboard = ({ setIsAuthenticated, user, summary, setSummary }) => {
  const navigate = useNavigate();
  const [files, setFiles] = useState([]);
  const [error, setError] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [userText, setUserText] = useState('');
  const abortController = useRef(null);

  // Cleanup function to be called in various scenarios
  const cleanup = async () => {
    try {
      await axios.post('/api/cleanup', {}, {
        withCredentials: true
      });
    } catch (err) {
      console.error('Cleanup failed:', err);
    }
  };

  // Cleanup on component unmount
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, []);

  // Display existing results if available
  useEffect(() => {
    if (summary) {
      console.log("Loading existing summary from session");
    }
  }, [summary]);

  const handleFileSelect = (e) => {
    console.log("selecting files");
    const selectedFiles = Array.from(e.target.files);
    
    // Filter for only PDF files
    const pdfFiles = selectedFiles.filter(file => file.type === 'application/pdf');
    
    if (pdfFiles.length > 0) {
      setFiles(pdfFiles);
      setError('');
      console.log(`Selected ${pdfFiles.length} PDF files`);
    } else {
      setError('Please select at least one PDF file');
      setFiles([]);
    }
  };

  const uploadPDFs = async () => {
    // Check that we have either files or user text
    if (files.length === 0 && !userText.trim()) {
      setError('Please select at least one file or enter some text');
      return;
    }
  
    try {
      console.log(`Processing ${files.length} PDFs and additional text`);
      setIsUploading(true);
      setError('');
      setSummary('');
      
      abortController.current = new AbortController();
  
      // Create FormData and append all files
      const formData = new FormData();
      files.forEach(file => {
        formData.append('files', file);
      });
      
      // Add user text if provided
      if (userText.trim()) {
        formData.append('userText', userText.trim());
      }

      const response = await axios.post('/api/upload-multiple', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        withCredentials: true,
        signal: abortController.current.signal,
      });

      if (response.data.success) {
        console.log("processing success");
        // Update to handle the new response format (text instead of dictionary)
        setSummary(response.data.results);
      } else {
        setError('Processing failed');
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        setError('Processing cancelled');
        await cleanup(); // Cleanup on cancel
      } else if (err.response?.status === 401) {
        setError('Session expired. Please log in again.');
        await cleanup(); // Cleanup on session expiry
        setIsAuthenticated(false);
        navigate('/login');
      } else {
        setError(err.response?.data?.error || err.message);
        console.error('Processing failed:', err);
      }
    } finally {
      setIsUploading(false);
    }
  };

  const clearResults = async () => {
    try {
      setSummary('');
      await axios.post('/api/clear-results', {}, {
        withCredentials: true
      });
    } catch (err) {
      console.error('Failed to clear results:', err);
    }
  };
  
  const regenerateSummary = async () => {
    try {
      setIsUploading(true); // Reuse the loading state
      setError('');
      
      const response = await axios.post('/api/regenerate-summary', {
        userText: userText.trim() || undefined
      }, {
        withCredentials: true
      });
      
      if (response.data.success) {
        console.log("Summary regenerated successfully");
        setSummary(response.data.summary);
      } else {
        setError('Failed to regenerate summary');
      }
    } catch (err) {
      console.error('Failed to regenerate summary:', err);
      setError(err.response?.data?.error || 'Failed to regenerate summary');
    } finally {
      setIsUploading(false);
    }
  };
  
  const goToQuiz = () => {
    navigate('/quiz');
  };

  const handleLogout = async () => {
    try {
      await cleanup(); // Cleanup before logout
      await axios.post('/api/auth/logout', {}, {
        withCredentials: true
      });
      setIsAuthenticated(false);
      navigate('/login');
    } catch (err) {
      console.error('Logout failed:', err);
      // Still navigate to login even if logout request fails
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
              <Typography variant="h6" component="h1" sx={{ flexGrow: 1, fontWeight: 600, textAlign: 'left' }}>
                Dashboard
              </Typography>
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
      <Container maxWidth="xl" sx={{ py: 3 }}>
        <Card elevation={3} sx={{ maxWidth: '100%', mx: 'auto' }}>
          <CardContent sx={{ p: 4 }}>
            <Typography 
              variant="h4" 
              component="h2" 
              align="center" 
              gutterBottom
              fontWeight="bold"
              color="text.primary"
            >
              PDF/Text Summarizer
            </Typography>

            <Box sx={{ display: 'flex', gap: 4, flexDirection: { xs: 'column', md: 'row' } }}>
              {/* Left Column - Upload and Text Input */}
              <Box sx={{ flex: 1 }}>
                <Stack spacing={3}>
                  {/* File Upload Area */}
                  <Paper
                    elevation={0}
                    sx={{
                      border: '2px dashed',
                      borderColor: 'divider',
                      borderRadius: 2,
                      p: 4,
                      bgcolor: 'action.hover',
                      width: 400,
                      height: 200,
                      transition: 'all 0.2s ease',
                      '&:hover': {
                        bgcolor: 'action.selected',
                        borderColor: 'primary.main'
                      }
                    }}
                  >
                    <Stack spacing={2} alignItems="center" sx={{ height: '100%' }}>
                      <input
                        type="file"
                        accept="application/pdf"
                        onChange={handleFileSelect}
                        multiple
                        style={{
                          width: '100%',
                          padding: '8px',
                          border: 'none',
                          borderRadius: '8px',
                          backgroundColor: 'transparent',
                          cursor: 'pointer',
                        }}
                      />
                      
                      {files.length > 0 && (
                        <Box sx={{ width: '100%', mt: 2, overflow: 'auto', maxHeight: 120 }}>
                          <Typography variant="body2" color="text.secondary" gutterBottom>
                            Selected: {files.length} file(s)
                          </Typography>
                          <List dense>
                            {files.map((file, index) => (
                              <ListItem key={index} sx={{ pl: 0 }}>
                                <Description sx={{ mr: 1, color: 'primary.main' }} />
                                <ListItemText 
                                  primary={file.name}
                                  primaryTypographyProps={{ variant: 'body2' }}
                                />
                              </ListItem>
                            ))}
                          </List>
                        </Box>
                      )}
                    </Stack>
                  </Paper>

                  {/* Text Input Area */}
                  <Paper
                    elevation={0}
                    sx={{
                      border: '2px solid',
                      borderColor: 'divider',
                      borderRadius: 2,
                      p: 3,
                      bgcolor: 'background.paper'
                    }}
                  >
                    <Typography variant="h6" fontWeight="600" gutterBottom>
                      Additional Text
                    </Typography>
                    <TextField
                      multiline
                      rows={6}
                      fullWidth
                      placeholder="Enter any additional text or notes that you want to include with the PDF content for summary and quiz generation..."
                      value={userText}
                      onChange={(e) => setUserText(e.target.value)}
                      variant="outlined"
                      sx={{
                        '& .MuiOutlinedInput-root': {
                          '& fieldset': {
                            borderColor: 'divider',
                          },
                        },
                        width: '100%',
                        height: 160,
                      }}
                    />
                  </Paper>

                  {/* Generate Button */}
                  <Box display="flex" justifyContent="center">
                    <Button
                      onClick={uploadPDFs}
                      disabled={(files.length === 0 && !userText.trim()) || isUploading}
                      variant="contained"
                      size="large"
                      startIcon={<CloudUpload />}
                      sx={{ px: 4, py: 1.5, width: 300, }}
                    >
                      {isUploading ? 'Processing...' : 'Generate Summary'}
                    </Button>
                  </Box>

                  {/* Error Message */}
                  {error && (
                    <Alert severity="error" sx={{ borderRadius: 2 }}>
                      {error}
                    </Alert>
                  )}
                </Stack>
              </Box>

              {/* Right Column - Summary Results */}
              <Box sx={{ flex: 1 }}>
                <Stack spacing={3}>
                  
                  
                  {summary ? (
                    <Paper 
                      elevation={1} 
                      sx={{ 
                        p: 3, 
                        height: 500,
                        width: 600,
                        overflow: 'auto',
                        bgcolor: 'background.paper',
                        border: '1px solid',
                        borderColor: 'divider'
                      }}
                    >
                      <Typography 
                        variant="body1" 
                        color="text.primary"
                        align="left"
                        sx={{ 
                          whiteSpace: 'pre-wrap',
                          lineHeight: 1.6
                        }}
                      >
                        {summary}
                      </Typography>
                    </Paper>
                  ) : (
                    <Paper 
                      elevation={1} 
                      sx={{ 
                        height: 500,
                        width: 600,
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center',
                        bgcolor: 'action.hover',
                        border: '2px dashed',
                        borderColor: 'divider'
                      }}
                    >
                      <Typography variant="h6" color="text.secondary">
                        Generate a summary to see results here
                      </Typography>
                    </Paper>
                  )}

                  {/* Summary Action Buttons - Below Summary */}
                  <Box display="flex" justifyContent="center" gap={1}>
                    <Button
                      onClick={regenerateSummary}
                      disabled={!summary || isUploading}
                      variant="outlined"
                      size="small"
                      startIcon={<Refresh />}
                      sx={{ minWidth: 'fit-content' }}
                    >
                      {isUploading ? 'Regenerating...' : 'Regenerate'}
                    </Button>
                    <Button
                      onClick={goToQuiz}
                      disabled={!summary}
                      variant="contained"
                      color="primary"
                      size="small"
                      startIcon={<Quiz />}
                      sx={{ minWidth: 'fit-content' }}
                    >
                      Quiz Me
                    </Button>
                    <Button
                      onClick={clearResults}
                      disabled={!summary}
                      variant="outlined"
                      color="error"
                      size="small"
                      startIcon={<Clear />}
                      sx={{ minWidth: 'fit-content' }}
                    >
                      Clear
                    </Button>
                  </Box>
                </Stack>
              </Box>
            </Box>
          </CardContent>
        </Card>
      </Container>
    </Box>
  );
};

export default Dashboard; 