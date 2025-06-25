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
  LinearProgress,
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
  const [progress, setProgress] = useState(0);
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
      setProgress(0);
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
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          setProgress(percentCompleted);
        },
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

  const cancelUpload = async () => {
    if (abortController.current) {
      console.log("aborting")
      abortController.current.abort();
      setError('Upload cancelled');
      setIsUploading(false);
      await cleanup(); // Cleanup on manual cancel
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
        <Container maxWidth="xl">
          <Box sx={{ maxWidth: 1000, mx: 'auto' }}>
            <Toolbar>
              <Typography variant="h6" component="h1" sx={{ flexGrow: 1, fontWeight: 600 }}>
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
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Card elevation={3} sx={{ maxWidth: 1000, mx: 'auto' }}>
          <CardContent sx={{ p: 4 }}>
            <Typography 
              variant="h4" 
              component="h2" 
              align="center" 
              gutterBottom
              fontWeight="bold"
              color="text.primary"
            >
              PDF Text Extraction
            </Typography>

            <Grid container spacing={4}>
              {/* PDF Upload Section */}
              <Grid item xs={12} md={6}>
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
                      transition: 'all 0.2s ease',
                      '&:hover': {
                        bgcolor: 'action.selected',
                        borderColor: 'primary.main'
                      }
                    }}
                  >
                    <Stack spacing={2} alignItems="center">
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
                          cursor: 'pointer'
                        }}
                      />
                      
                      {files.length > 0 && (
                        <Box sx={{ width: '100%', mt: 2 }}>
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
                </Stack>
              </Grid>

              {/* Text Input Section */}
              <Grid item xs={12} md={6}>
                <Stack spacing={3}>
                  <Paper
                    elevation={0}
                    sx={{
                      border: '2px solid',
                      borderColor: 'divider',
                      borderRadius: 2,
                      p: 3,
                      bgcolor: 'background.paper',
                      height: '100%',
                      minHeight: 200
                    }}
                  >
                    <Typography variant="h6" fontWeight="600" gutterBottom>
                      Additional Text
                    </Typography>
                    <TextField
                      multiline
                      rows={8}
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
                      }}
                    />
                  </Paper>
                </Stack>
              </Grid>
            </Grid>

            <Stack spacing={4} mt={4}>
              {/* Upload Button */}
              <Box display="flex" justifyContent="center">
                <Button
                  onClick={uploadPDFs}
                  disabled={(files.length === 0 && !userText.trim()) || isUploading}
                  variant="contained"
                  size="large"
                  startIcon={<CloudUpload />}
                  sx={{ px: 4, py: 1.5 }}
                >
                  {isUploading ? 'Processing...' : 'Generate New Summary'}
                </Button>
              </Box>

              {/* Progress Bar */}
              {isUploading && (
                <Box>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="body2" color="text.secondary">
                      Upload {progress}% complete. Summarizing...
                    </Typography>
                    <Button
                      onClick={cancelUpload}
                      color="error"
                      size="small"
                      startIcon={<Cancel />}
                    >
                      Cancel
                    </Button>
                  </Box>
                  <LinearProgress 
                    variant="determinate" 
                    value={progress} 
                    sx={{ borderRadius: 1, height: 8 }}
                  />
                </Box>
              )}

              {/* Error Message */}
              {error && (
                <Alert severity="error" sx={{ borderRadius: 2 }}>
                  {error}
                </Alert>
              )}

              {/* Results Section */}
              {summary && (
                <Box>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                    <Typography variant="h6" fontWeight="600" color="text.primary">
                      Summary:
                    </Typography>
                    <Stack direction="row" spacing={1}>
                      <Button
                        onClick={regenerateSummary}
                        disabled={isUploading}
                        variant="outlined"
                        size="small"
                        startIcon={<Refresh />}
                      >
                        {isUploading ? 'Regenerating...' : 'Regenerate'}
                      </Button>
                      <Button
                        onClick={goToQuiz}
                        variant="outlined"
                        color="secondary"
                        size="small"
                        startIcon={<Quiz />}
                      >
                        Quiz Me
                      </Button>
                      <Button
                        onClick={clearResults}
                        color="error"
                        size="small"
                        startIcon={<Clear />}
                      >
                        Clear
                      </Button>
                    </Stack>
                  </Box>
                  
                  <Paper 
                    elevation={1} 
                    sx={{ 
                      p: 3, 
                      maxHeight: 400, 
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
                </Box>
              )}
            </Stack>
          </CardContent>
        </Card>
      </Container>
    </Box>
  );
};

export default Dashboard; 