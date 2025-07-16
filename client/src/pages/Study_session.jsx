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
  Stack,
  Paper,
  TextField,
  CircularProgress,
  Checkbox,
  FormControlLabel,
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
  Switch
} from '@mui/material';
import {
  CloudUpload,
  Quiz,
  Refresh,
  Clear,
  Logout,
  ContentCopy,
  Home as HomeIcon,
  Close as CloseIcon,
  OpenInNew as OpenInNewIcon
} from '@mui/icons-material';
import ThemeToggle from '../components/ThemeToggle';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Link } from '@mui/material';
import FeedbackButton from '../components/FeedbackButton';

const Study_session = ({ setIsAuthenticated, user, summary, setSummary }) => {
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [userText, setUserText] = useState('');
  const abortController = useRef(null);
  const [copySuccess, setCopySuccess] = useState(false);
  const [isContentLocked, setIsContentLocked] = useState(false);
  const [numQuestions, setNumQuestions] = useState(5);
  const [isQuizMode, setIsQuizMode] = useState(false);

  // New state for available and selected PDFs
  const [availablePdfs, setAvailablePdfs] = useState([]); // Stores { hash, filename, text } from backend
  const [selectedPdfHashes, setSelectedPdfHashes] = useState([]); // Stores only the hashes of selected PDFs
  const [showExpandedPdfList, setShowExpandedPdfList] = useState(false); // New state for expanded view

  // Clear existing results when component mounts, ensuring a fresh start
  useEffect(() => {
    clearResults();
  }, []);

  // Abort any active fetch request when the component unmounts
  useEffect(() => {
    return () => {
      if (abortController.current) {
        console.log("Study_session unmounting, aborting any active stream.");
        abortController.current.abort();
        abortController.current = null; // Clear the ref to prevent stale closures
      }
    };
  }, []); // Empty dependency array ensures this runs once on mount and cleanup on unmount

  // Display existing results if available
  useEffect(() => {
    if (summary) {
      console.log("Loading existing summary from session");
    }
  }, [summary]);

  // Load quiz mode from sessionStorage
  useEffect(() => {
    const storedQuizMode = sessionStorage.getItem('isQuizMode');
    if (storedQuizMode !== null) {
      setIsQuizMode(storedQuizMode === 'true');
    }
  }, []);

  // Lock inputs when a summary is present, unlock when it's cleared
  useEffect(() => {
    if (summary) {
      console.log("Summary is present, locking inputs.");
      setIsContentLocked(true);
    } else {
      console.log("Summary is cleared, unlocking inputs.");
      setIsContentLocked(false);
    }
  }, [summary]);

  // New useEffect to fetch available PDFs on component mount
  useEffect(() => {
    const fetchAvailablePdfs = async () => {
      try {
        const response = await axios.get('/api/get-user-pdfs', { withCredentials: true });
        if (response.data.success) {
          setAvailablePdfs(response.data.pdfs);
        } else {
          console.error("Failed to fetch available PDFs:", response.data.error);
          setError(response.data.error || 'Failed to load available PDFs.');
        }
      } catch (err) {
        console.error("Error fetching available PDFs:", err);
        if (err.response?.status === 401) {
          setError('Session expired. Please log in again.');
          setIsAuthenticated(false);
          navigate('/login');
        } else {
          setError('An error occurred while fetching available PDFs.');
        }
      }
    };

    fetchAvailablePdfs();
  }, [setIsAuthenticated, navigate]);

  const handlePdfCheckboxChange = (event) => {
    const { value, checked } = event.target;
    console.log(`Checkbox clicked: value=${value}, checked=${checked}`);
    setSelectedPdfHashes(prev => {
      const newSelected = checked ? [...prev, value] : prev.filter(hash => hash !== value);
      console.log('New selectedPdfHashes:', newSelected);
      return newSelected;
    });
  };

  const generateSummary = async () => {
    if (selectedPdfHashes.length === 0 && !userText.trim()) {
      setError('Please select at least one PDF or enter some text');
      return;
    }
  
    setIsUploading(true);
    setError('');
    setSummary('');
    abortController.current = new AbortController();
  
    // Send JSON data instead of FormData
    const payload = {
      selectedPdfHashes: selectedPdfHashes,
      userText: userText.trim(),
      isQuizMode: isQuizMode.toString()
    };

    try {
      const response = await fetch('/api/generate-summary', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
        signal: abortController.current.signal,
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(errText || 'Processing failed');
      }

      const contentType = response.headers.get('content-type');

      if (contentType && contentType.includes('application/json')) {
        // Non-streaming response
        const data = await response.json();
        if (data.success) {
          setSummary(data.results);
        } else {
          throw new Error(data.error || 'Processing failed');
        }
      } else if (contentType && contentType.includes('text/plain')) {
        // Streaming response
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let finalSummary = '';
        
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          finalSummary += chunk;
          setSummary(finalSummary);
        }

        // After stream is complete, save the final summary to the session
        // Only save if the operation was not aborted during streaming
        if (!abortController.current.signal.aborted) {
          await axios.post('/api/save-summary', { summary: finalSummary }, {
            withCredentials: true
          });
        }

      } else {
        throw new Error(`Unexpected content type: ${contentType}`);
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        setError('Processing cancelled');
      } else if (err.response?.status === 401) {
        setError('Session expired. Please log in again.');
        setIsAuthenticated(false);
        navigate('/login');
      } else {
        setError(err.message || 'An unknown error occurred');
      }
    } finally {
      setIsUploading(false);
    }
  };

  const clearResults = async () => {
    try {

      setSummary('');
      setSelectedPdfHashes([]); // Clear selected PDFs
      setUserText('');
      await axios.post('/api/clear-session-content', {}, {
        withCredentials: true
      });
    } catch (err) {
      console.error('Failed to clear results:', err);
    }
  };
  
  const regenerateSummary = async () => {
    setIsUploading(true);
    setError('');
    setSummary(''); // Clear previous summary before regenerating

    // Send JSON data instead of FormData
    const payload = {
      selectedPdfHashes: selectedPdfHashes,
      userText: userText.trim(),
    };

    try {
      const response = await fetch('/api/regenerate-summary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload), // Send the payload here
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(errText || 'Failed to regenerate summary');
      }

      const contentType = response.headers.get('content-type');

      if (contentType && contentType.includes('application/json')) {
        // Non-streaming
        const data = await response.json();
        if (data.success) {
          setSummary(data.summary);
        } else {
          throw new Error(data.error || 'Failed to regenerate summary');
        }
      } else if (contentType && contentType.includes('text/plain')) {
        // Streaming
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let finalSummary = '';
        
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          finalSummary += chunk;
          setSummary(finalSummary);
        }

        // After stream is complete, save the final summary to the session
        // Only save if the operation was not aborted during streaming
        if (!abortController.current.signal.aborted) {
          await axios.post('/api/save-summary', { summary: finalSummary }, {
            withCredentials: true
          });
        }
      
      } else {
        throw new Error(`Unexpected content type: ${contentType}`);
      }
    } catch (err) {
      setError(err.message || 'An unknown error occurred during regeneration');
    } finally {
      setIsUploading(false);
    }
  };
  
  const goToQuiz = () => {
    // Store the number of questions and quiz mode in sessionStorage so the Quiz page can access it
    sessionStorage.setItem('numQuestions', numQuestions.toString());
    sessionStorage.setItem('isQuizMode', isQuizMode.toString());
    navigate('/quiz');
  };

  const handleLogout = async () => {
    try {
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

  const handleCopySummary = async () => {
    if (!summary) return;
    
    try {
      await navigator.clipboard.writeText(summary);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000); // Reset after 2 seconds
    } catch (err) {
      console.error('Failed to copy text: ', err);
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
                <img src="/favicon.png" alt="MedStudyAI Logo" style={{ width: 28, height: 28 }} />
                <Typography variant="h6" component="h1" sx={{ fontWeight: 600 }}>
                  MedStudyAI
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
                <Button
                  onClick={async () => {
                    try {
                      clearResults();
                      // Clear summary in App.js state
                      setSummary('');
                      // Navigate to upload_pdfs
                      navigate('/upload_pdfs');
                    } catch (err) {
                      console.error('Failed to clear session and navigate:', err);
                      // Still attempt to navigate even if clearing fails
                      navigate('/upload_pdfs');
                    }
                  }}
                  variant={availablePdfs.length === 0 ? 'contained' : 'outlined'}
                  startIcon={<CloudUpload />}
                  size="small"
                  sx={{ ml: 0 }}
                  color={(availablePdfs.length === 0 && !isQuizMode) ? "success" : "primary"}
                >
                  Upload PDFs
                </Button>
                <Typography 
                  variant="body2" 
                  color="primary"
                  sx={{ 
                    fontWeight: 600,
                    bgcolor: isQuizMode ? 'primary.light' : 'success.main',
                    px: 1.5,
                    py: 0.5,
                    borderRadius: 1,
                    color: 'text.primary'
                  }}
                >
                  {isQuizMode ? 'USMLE Mode' : 'Flashcard Mode'}
                </Typography>
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
      <Container maxWidth="xl" sx={{ py: 3 }}>
        <Card elevation={3} sx={{ maxWidth: '100%', mx: 'auto' }}>
          <CardContent sx={{ p: 4 }}>

            <Box sx={{ display: 'flex', gap: 4, flexDirection: { xs: 'column', md: 'row' } }}>
              {/* Left Column - PDF Selection and Text Input */}
              <Box sx={{ flex: 1 }}>
                <Stack spacing={3}>
                  {/* PDF Selection Area (replaces File Upload) */}
                  <Paper
                    elevation={0}
                    sx={{
                      border: '2px dashed',
                      borderColor: 'divider',
                      borderRadius: 2,
                      p: 4,
                      bgcolor: (theme) => (theme.palette.mode === 'light' ? 'action.hover' : 'background.paper'),
                      width: 400,
                      height: 200,
                      overflowY: 'auto',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    <Stack spacing={-1} alignItems="flex-start" sx={{ height: '100%' }}>
                      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ width: '100%', mb: 0 }}>
                        <Typography variant="h6" fontWeight="600" sx={{ mb: 2 }}>
                          Select PDFs ({availablePdfs.length})
                        </Typography>
                        {availablePdfs.length > 0 && (
                          <Button
                            onClick={() => setShowExpandedPdfList(true)}
                            disabled={isContentLocked || isUploading}
                            size="small"
                            startIcon={<OpenInNewIcon fontSize="small" />}
                            sx={{ mb: 2 , ml: 0 }} // Add some bottom margin to align with Typography's gutterBottom
                          >
                            Expand
                          </Button>
                        )}
                      </Stack>
                      {availablePdfs.length > 0 ? (
                        <List dense sx={{ width: '100%' }}>
                          {availablePdfs.map((pdf) => (
                            <ListItem 
                              key={pdf.hash} 
                              disablePadding 
                              sx={{ 
                                '&:hover': { 
                                  bgcolor: 'action.hover',
                                  borderRadius: 1
                                },
                                py: 0.5
                              }}
                            >
                              <FormControlLabel
                                control={
                                  <Checkbox
                                    value={pdf.hash}
                                    checked={selectedPdfHashes.includes(pdf.hash)}
                                    onChange={handlePdfCheckboxChange}
                                    disabled={isContentLocked || isUploading}
                                    color={isQuizMode ? "primary" : "success"}
                                  />
                                }
                                label={
                                  <ListItemText 
                                    primary={pdf.short_summary || pdf.filename} 
                                    primaryTypographyProps={{
                                      variant: 'body2', 
                                      fontWeight: 'medium',
                                      color: 'text.primary'
                                    }}
                                    secondary={
                                      <>
                                        {pdf.filename}
                                        {pdf.created_at && (
                                          <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.2 }}>
                                            Uploaded: {new Date(pdf.created_at).toLocaleString()}
                                          </Typography>
                                        )}
                                      </>
                                    }
                                    secondaryTypographyProps={{
                                      component: 'div'
                                    }}
                                  />
                                }
                              />
                            </ListItem>
                          ))}
                        </List>
                      ) : (
                        <Typography variant="body1" color="text.secondary" sx={{ mt: 1 }}>
                          No PDFs uploaded yet. Upload via the "Upload PDFs" page to see them here.
                        </Typography>
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
                      bgcolor: (theme) => (theme.palette.mode === 'light' ? 'action.hover' : 'background.paper')
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
                      disabled={isContentLocked || isUploading}
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
                      onClick={generateSummary}
                      disabled={isContentLocked || (selectedPdfHashes.length === 0 && !userText.trim()) || isUploading}
                      variant="contained"
                      size="large"
                      startIcon={isUploading ? <CircularProgress size={24} color="inherit" /> : <CloudUpload />}
                      sx={{ px: 4, py: 1.5, width: 300, }}
                      color={isQuizMode ? "primary" : "success"}
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
                        borderColor: 'divider',
                        textAlign: 'left',
                        position: 'relative',
                        '& h1': { fontSize: '1.7rem', fontWeight: 600, mb: 2, mt: 3, textAlign: 'left' },
                        '& h2': { fontSize: '1.4rem', fontWeight: 600, mb: 1.5, mt: 2.5, textAlign: 'left' },
                        '& h3': { fontSize: '1.2rem', fontWeight: 600, mb: 1, mt: 2, textAlign: 'left' },
                        '& p': { mb: 1.5, fontSize: '1rem', lineHeight: 1.6, textAlign: 'left' },
                        '& ul, & ol': { mb: 1.5, pl: 3, textAlign: 'left' },
                        '& li': { mb: 0.5, textAlign: 'left' },
                        '& code': {
                          backgroundColor: 'action.hover',
                          px: 0.8,
                          py: 0.3,
                          borderRadius: 1,
                          fontSize: '0.9em'
                        },
                        '& pre': {
                          backgroundColor: 'action.hover',
                          p: 2,
                          borderRadius: 1,
                          overflow: 'auto',
                          mb: 2,
                          textAlign: 'left'
                        },
                        '& blockquote': {
                          borderLeft: 4,
                          borderColor: 'divider',
                          pl: 2,
                          ml: 0,
                          my: 2,
                          fontStyle: 'italic',
                          textAlign: 'left'
                        },
                        '& a': {
                          color: 'primary.main',
                          textDecoration: 'none',
                          '&:hover': {
                            textDecoration: 'underline'
                          }
                        },
                        '& table': {
                          borderCollapse: 'collapse',
                          width: '100%',
                          mb: 2,
                          textAlign: 'left'
                        },
                        '& th, & td': {
                          border: 1,
                          borderColor: 'divider',
                          p: 1,
                          textAlign: 'left'
                        },
                        '& th': {
                          backgroundColor: 'action.hover',
                          fontWeight: 600
                        }
                      }}
                    >
                      <Button
                        onClick={handleCopySummary}
                        disabled={!summary || isUploading}
                        size="small"
                        sx={{
                          position: 'absolute',
                          top: 8,
                          right: 8,
                          minWidth: 'auto',
                          p: 0.5,
                          color: (!summary || isUploading) ? 'action.disabled' : (copySuccess ? 'success.main' : 'text.secondary'),
                          '&:hover': {
                            bgcolor: (summary && !isUploading) ? 'action.hover' : 'transparent',
                            color: (summary && !isUploading) ? 'primary.main' : 'action.disabled'
                          },
                          '&:disabled': {
                            color: 'action.disabled'
                          },
                          zIndex: 1
                        }}
                        title={!summary ? 'No summary to copy' : isUploading ? 'Wait for summary to finish loading' : (copySuccess ? 'Copied!' : 'Copy to clipboard')}
                      >
                        <ContentCopy fontSize="small" />
                      </Button>
                      <ReactMarkdown 
                        children={summary} 
                        remarkPlugins={[remarkGfm]}
                        components={{
                          h1: (props) => <Typography variant="h4" gutterBottom {...props} />,
                          h2: (props) => <Typography variant="h5" gutterBottom {...props} />,
                          h3: (props) => <Typography variant="h6" gutterBottom {...props} />,
                          p: (props) => <Typography variant="body1" paragraph {...props} />,
                          a: (props) => <Link {...props} />,
                        }}
                      />
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
                        bgcolor: (theme) => (theme.palette.mode === 'light' ? 'action.hover' : 'background.paper'),
                        border: '2px dashed',
                        borderColor: 'divider',
                        position: 'relative'
                      }}
                    >
                      <Button
                        onClick={handleCopySummary}
                        disabled={!summary || isUploading}
                        size="small"
                        sx={{
                          position: 'absolute',
                          top: 8,
                          right: 8,
                          minWidth: 'auto',
                          p: 0.5,
                          color: (!summary || isUploading) ? 'action.disabled' : (copySuccess ? 'success.main' : 'text.secondary'),
                          '&:hover': {
                            bgcolor: (summary && !isUploading) ? 'action.hover' : 'transparent',
                            color: (summary && !isUploading) ? 'primary.main' : 'action.disabled'
                          },
                          '&:disabled': {
                            color: 'action.disabled'
                          },
                          zIndex: 1
                        }}
                        title={!summary ? 'No summary to copy' : isUploading ? 'Wait for summary to finish loading' : (copySuccess ? 'Copied!' : 'Copy to clipboard')}
                      >
                        <ContentCopy fontSize="small" />
                      </Button>
                      <Typography variant="h6" color="text.secondary">
                        Generate a summary to see results here
                      </Typography>
                    </Paper>
                  )}

                  {/* Summary Action Buttons - Below Summary */}
                  <Box display="flex" justifyContent="center" gap={1} alignItems="center">
                    <Button
                      onClick={regenerateSummary}
                      disabled={!summary || isUploading}
                      variant="outlined"
                      size="small"
                      startIcon={isUploading ? <CircularProgress size={16} color="inherit" /> : <Refresh />}
                      sx={{ minWidth: 'fit-content' }}
                    >
                      {isUploading ? 'Regenerating...' : 'Regenerate'}
                    </Button>
                    <FormControlLabel
                        control={
                            <Switch
                              checked={isQuizMode}
                              onChange={(e) => {
                                const newValue = e.target.checked;
                                setIsQuizMode(newValue);
                                sessionStorage.setItem('isQuizMode', newValue.toString());
                              }}
                              size="small"
                              color={isQuizMode ? "primary" : "success"}
                              disabled={isUploading}
                              sx={{
                                  '& .MuiSwitch-switchBase.Mui-checked': {
                                      color: 'primary.main',
                                      '&:hover': {
                                          backgroundColor: 'primary.light'
                                      }
                                  },
                                  '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                                      backgroundColor: 'primary.main'
                                  },
                                  '& .MuiSwitch-switchBase': {
                                      color: 'success.main',
                                      '&:hover': {
                                          backgroundColor: 'success.light'
                                      }
                                  },
                                  '& .MuiSwitch-track': {
                                      backgroundColor: 'success.main'
                                  }
                              }}
                          />
                        }
                        label={
                            <Typography variant="body2" color="text.secondary">
                                {isQuizMode ? 'USMLE Mode' : 'Flashcard Mode'}
                            </Typography>
                        }
                        labelPlacement="bottom"
                        disabled={isUploading}
                        sx={{ m: 0, mx: 1, flexShrink: 0 }}
                    />
                    <Button
                      onClick={goToQuiz}
                      disabled={!summary || isUploading}
                      variant="contained"
                      color={isQuizMode ? "primary" : "success"}
                      size="small"
                      startIcon={<Quiz />}
                      sx={{ 
                        minWidth: 'fit-content',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                        px: 2
                      }}
                    >
                      Create Quiz
                      <TextField
                        type="number"
                        value={numQuestions}
                        onChange={(e) => {
                          e.stopPropagation();
                          setNumQuestions(Math.max(1, Math.min(20, parseInt(e.target.value) || 1)));
                        }}
                        onClick={(e) => e.stopPropagation()}
                        disabled={!summary || isUploading}
                        inputProps={{ 
                          min: 1, 
                          max: 20,
                          style: { textAlign: 'center', width: '40px', fontSize: '14px' }
                        }}
                        size="small"
                        sx={{
                          width: '45px',
                          '& .MuiOutlinedInput-root': {
                            height: '24px',
                            backgroundColor: 'rgba(255, 255, 255, 0.15)',
                            border: '1px solid rgba(255, 255, 255, 0.3)',
                            borderRadius: '4px',
                            '&:hover': {
                              backgroundColor: 'rgba(255, 255, 255, 0.25)',
                            },
                            '&.Mui-focused': {
                              backgroundColor: 'rgba(255, 255, 255, 0.3)',
                              border: '1px solid rgba(255, 255, 255, 0.5)',
                            }
                          },
                          '& .MuiInputBase-input': {
                            color: 'white',
                            padding: '2px 4px',
                            '&::placeholder': {
                              color: 'rgba(255, 255, 255, 0.7)',
                            }
                          },
                          '& .MuiOutlinedInput-notchedOutline': {
                            border: 'none'
                          }
                        }}
                      />
                    </Button>
                    <Button
                        onClick={clearResults}
                      disabled={!summary || isUploading}
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
      <FeedbackButton />

      {/* Expanded PDF List Dialog */}
      <Dialog open={showExpandedPdfList} onClose={() => setShowExpandedPdfList(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Typography variant="h5">All Available PDFs</Typography>
            <IconButton onClick={() => setShowExpandedPdfList(false)}>
              <CloseIcon />
            </IconButton>
          </Stack>
        </DialogTitle>
        <DialogContent dividers>
          <List dense>
            {availablePdfs.length > 0 ? (availablePdfs.map((pdf) => (
              <ListItem 
                key={pdf.hash} 
                disablePadding
                sx={{
                  '&:hover': { 
                    bgcolor: 'action.hover',
                    borderRadius: 1
                  },
                  py: 0.5
                }}
              >
                <FormControlLabel
                  control={
                    <Checkbox
                      value={pdf.hash}
                      checked={selectedPdfHashes.includes(pdf.hash)}
                      onChange={handlePdfCheckboxChange}
                      disabled={isContentLocked || isUploading}
                      color={isQuizMode ? "primary" : "success"}
                    />
                  }
                  label={
                    <ListItemText 
                      primary={pdf.short_summary || pdf.filename} 
                      primaryTypographyProps={{
                        variant: 'body1', 
                        fontWeight: 'medium',
                        color: 'text.primary'
                      }}
                      secondary={
                        <>
                          {pdf.filename}
                          {pdf.created_at && (
                            <Typography variant="body2" color="text.secondary" display="block" sx={{ mt: 0.2 }}>
                              {new Date(pdf.created_at).toLocaleString()}
                            </Typography>
                          )}
                        </>
                      }
                      secondaryTypographyProps={{
                        component: 'div'
                      }}
                    />
                  }
                />
              </ListItem>
            ))) : (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                No PDFs uploaded yet. Please log in and upload via the Home screen to see them here.
              </Typography>
            )}
          </List>
        </DialogContent>
      </Dialog>
    </Box>
  );
};

export default Study_session; 