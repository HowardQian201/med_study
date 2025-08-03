import React, { useState, useRef, useEffect } from 'react';
import { Box, Typography, Container, AppBar, Toolbar, Stack, Button, Paper, Alert, List, ListItem, ListItemText, Checkbox } from '@mui/material';
import { Home as HomeIcon, Logout, CloudUpload, Description } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import ThemeToggle from '../components/ThemeToggle';
import FeedbackButton from '../components/FeedbackButton';
import axios from 'axios';

const Upload_pdfs = ({ setIsAuthenticated, user, setSummary }) => {
  const navigate = useNavigate();
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef(null);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [uploadedFilesReport, setUploadedFilesReport] = useState([]);
  const [failedFilesReport, setFailedFilesReport] = useState([]);
  const [processingJobs, setProcessingJobs] = useState([]);
  const [userPdfs, setUserPdfs] = useState([]);
  const [selectedPdfHashes, setSelectedPdfHashes] = useState([]);
  const [isQuizMode, setIsQuizMode] = useState(false); // Add isQuizMode state

  // Fetch initial processing tasks from the backend on component mount
  useEffect(() => {
    const fetchInitialTasks = async () => {
        try {
            const response = await axios.get('/api/get-user-tasks', { withCredentials: true });
            if (response.data.success) {
                // The data from backend has keys: task_id, filename, status, message, updated_at
                // The polling logic will take over for any non-terminal tasks.
                setProcessingJobs(response.data.tasks || []);
            } else {
                console.error("Failed to fetch user tasks:", response.data.error);
            }
        } catch (err) {
            console.error("Error fetching user tasks:", err);
            if (err.response?.status === 401) {
                setIsAuthenticated(false);
                navigate('/login');
            }
        }
    };

    fetchInitialTasks();
  }, [setIsAuthenticated, navigate]); // Run only on mount


  // Clear success/error messages and reports after 10 seconds
  useEffect(() => {
    let timer;
    if (successMessage || error || uploadedFilesReport.length > 0 || failedFilesReport.length > 0) {
      timer = setTimeout(() => {
        setSuccessMessage('');
        setError('');
        setUploadedFilesReport([]);
        setFailedFilesReport([]);
      }, 10000); // 10 seconds
    }
    return () => clearTimeout(timer);
  }, [successMessage, error, uploadedFilesReport, failedFilesReport]);

  // New useEffect to fetch user's associated PDFs on component mount
  useEffect(() => {
    const fetchUserPdfs = async () => {
      try {
        const response = await axios.get('/api/get-user-pdfs', { withCredentials: true });
        if (response.data.success) {
          setUserPdfs(response.data.pdfs);
        } else {
          console.error("Failed to fetch user PDFs:", response.data.error);
          // Optionally set an error state here if you want to display it
        }
      } catch (err) {
        console.error("Error fetching user PDFs:", err);
        if (err.response?.status === 401) {
          // Session expired, redirect to login
          setError('Session expired. Please log in again.'); // Add this line
          setIsAuthenticated(false);
          navigate('/login');
        } else {
          // Handle other errors, e.g., display a generic error message
          setError(err.response?.data?.error || 'An error occurred while fetching user PDFs.'); // Modified this line
        }
      }
    };

    // Load quiz mode from sessionStorage on component mount
    const storedQuizMode = sessionStorage.getItem('isQuizMode');
    if (storedQuizMode !== null) {
      setIsQuizMode(storedQuizMode === 'true');
    }

    fetchUserPdfs();
  }, [setIsAuthenticated, navigate]); // Dependencies to re-run effect if auth/navigation changes

  // Polling for processing job statuses
  useEffect(() => {
    let interval;

    if (processingJobs.length > 0) {
      interval = setInterval(async () => {
        // Capture the current state of processingJobs before mapping to detect transitions
        const currentJobsSnapshot = [...processingJobs];

        const updatedJobs = await Promise.all(
          currentJobsSnapshot.map(async (job) => {
            if (job.status === 'SUCCESS' || job.status === 'FAILURE') {
              return job; // Already completed, no need to poll
            }
            try {
              const response = await axios.get(`/api/pdf-processing-status/${job.task_id}`, {
                withCredentials: true,
              });
              if (response.data.success) {
                // If job just became SUCCESS, set displayUntil for the *new* job object
                if (response.data.status === 'SUCCESS') {
                  // Removed displayUntil logic, successful jobs will now remain visible
                  return { ...job, status: response.data.status, message: response.data.message };
                }
                return { ...job, status: response.data.status, message: response.data.message };
              } else {
                return { ...job, status: 'FAILURE', message: response.data.error || 'Failed to get status.' };
              }
            } catch (err) {
              console.error(`Error polling for task ${job.task_id}:`, err);
              return { ...job, status: 'FAILURE', message: 'Network error or server unreachable.' };
            }
          })
        );

        // Detect if any job newly transitioned to SUCCESS
        let shouldRefetchPdfs = false;
        for (let i = 0; i < updatedJobs.length; i++) {
            const oldJob = currentJobsSnapshot[i];
            const newJob = updatedJobs[i];

            // If the job was not SUCCESS before, but is SUCCESS now
            if (oldJob.status !== 'SUCCESS' && newJob.status === 'SUCCESS') {
                shouldRefetchPdfs = true;
                break; // Found at least one newly successful task, no need to check further
            }
        }

        // Update processingJobs state
        // Successful jobs are no longer filtered out after a timer
        setProcessingJobs(updatedJobs);

        // Trigger re-fetch of user PDFs if any task just completed successfully
        if (shouldRefetchPdfs) {
            try {
                const userPdfsResponse = await axios.get('/api/get-user-pdfs', { withCredentials: true });
                if (userPdfsResponse.data.success) {
                    setUserPdfs(userPdfsResponse.data.pdfs);
                }
            } catch (fetchErr) {
                console.error('Error re-fetching user PDFs after task completion:', fetchErr);
            }
        }
      }, 3000); // Poll every 3 seconds
    }

    return () => {
      clearInterval(interval);
    };
  }, [processingJobs, setUserPdfs, setIsAuthenticated, navigate]); // Added setUserPdfs, setIsAuthenticated, navigate to dependency array

  const handleFileSelect = (event) => {
    const files = Array.from(event.target.files);
    
    // Check if the number of files exceeds the limit
    if (files.length > 5) {
      setError('You can only upload up to 5 PDFs at once. Please select fewer files.');
      // Clear the file input
      event.target.value = null;
      // Clear selected files state
      setSelectedFiles([]);
      return;
    }
    
    console.log('Files selected:', files);
    setSelectedFiles(files);
    setError('');
    setSuccessMessage('');
    setUploadedFilesReport([]);
    setFailedFilesReport([]);
  };

  const handleUploadFiles = async () => {
    if (selectedFiles.length === 0) {
      setError('Please select at least one file to upload.');
      return;
    }

    setIsUploading(true);
    setError('');
    setSuccessMessage('');
    setUploadedFilesReport([]);
    setFailedFilesReport([]);

    // Create individual upload promises for each file
    const uploadPromises = selectedFiles.map(file => {
      const formData = new FormData();
      formData.append('files', file); // Single file per request
      
      return axios.post('/api/upload-pdfs', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        withCredentials: true,
      });
    });

    try {
      // Send all requests concurrently and wait for all to complete
      const responses = await Promise.allSettled(uploadPromises);
      
      let allUploadedFiles = [];
      let allFailedFiles = [];
      let allTaskDetails = [];
      let hasAnySuccess = false;

      // Process each response individually
      responses.forEach((result, index) => {
        if (result.status === 'fulfilled' && result.value.data.success) {
          hasAnySuccess = true;
          const responseData = result.value.data;
          allUploadedFiles.push(...(responseData.uploaded_files || []));
          allFailedFiles.push(...(responseData.failed_files || []));
          allTaskDetails.push(...(responseData.task_details || []));
        } else {
          // Handle individual file failures
          const fileName = selectedFiles[index].name;
          allFailedFiles.push({
            filename: fileName,
            error: result.status === 'rejected' 
              ? (result.reason?.response?.data?.error || result.reason?.message || 'Upload failed')
              : (result.value?.data?.error || 'Upload failed')
          });
        }
      });

      // Update state with aggregated results
      setUploadedFilesReport(allUploadedFiles);
      setFailedFilesReport(allFailedFiles);
      
      // Initialize processing jobs state
      const initialProcessingJobs = allTaskDetails.map(task => ({
          ...task,
          status: 'PENDING',
          message: 'Queued for processing'
      }));
      setProcessingJobs(prevJobs => [...prevJobs, ...initialProcessingJobs]);

      let generalMessage = '';
      if (allUploadedFiles.length > 0) {
          generalMessage += `Successfully uploaded ${allUploadedFiles.length} files. `;
      }
      if (allFailedFiles.length > 0) {
          generalMessage += `Failed to upload ${allFailedFiles.length} files.`;
      }

      if (generalMessage) {
          setSuccessMessage(generalMessage);
      } else {
          setSuccessMessage('Operation completed with no new uploads, existing files, or failures.');
      }

      // Re-fetch user PDFs after upload to reflect any 'touched' files in the UI
      if (hasAnySuccess) {
        try {
            const userPdfsResponse = await axios.get('/api/get-user-pdfs', { withCredentials: true });
            if (userPdfsResponse.data.success) {
                setUserPdfs(userPdfsResponse.data.pdfs);
            }
        } catch (fetchErr) {
            console.error('Error re-fetching user PDFs after upload completion:', fetchErr);
        }
      }

      setSelectedFiles([]);
      fileInputRef.current.value = null;

    } catch (err) {
      console.error('Error uploading files:', err);
      if (err.response?.status === 401) {
        setError('Session expired. Please log in again.');
        setIsAuthenticated(false);
        navigate('/login');
      } else {
        setError(err.response?.data?.error || 'An unknown error occurred during upload.');
      }
    } finally {
      setIsUploading(false);
    }
  };

  const handleClearCompletedTasks = async () => {
    try {
      const response = await axios.post('/api/clear-completed-tasks', {}, { withCredentials: true });
      if (response.data.success) {
        setProcessingJobs(prevJobs => prevJobs.filter(job => job.status !== 'SUCCESS' && job.status !== 'FAILURE'));
        setSuccessMessage('Completed and failed tasks cleared successfully.');
      } else {
        setError(response.data.error || 'Failed to clear completed tasks.');
      }
    } catch (err) {
      console.error('Error clearing completed tasks:', err);
      if (err.response?.status === 401) {
        setError('Session expired. Please log in again.');
        setIsAuthenticated(false);
        navigate('/login');
      } else {
        setError(err.response?.data?.error || 'An unknown error occurred during task clearing.');
      }
    }
  };

  const handleRemoveSelectedPdfs = async () => {
    if (selectedPdfHashes.length === 0) return;

    if (!window.confirm(`Are you sure you want to remove ${selectedPdfHashes.length} selected PDF(s) from your account? This action cannot be undone.`)) {
      return; // User cancelled the operation
    }

    try {
      const response = await axios.post('/api/remove-user-pdfs', { pdf_hashes: selectedPdfHashes }, { withCredentials: true });
      if (response.data.success) {
        setSuccessMessage(response.data.message || 'Selected PDFs removed successfully.');
        setSelectedPdfHashes([]); // Clear selection after removal
        // Re-fetch user PDFs to update the displayed list
        const userPdfsResponse = await axios.get('/api/get-user-pdfs', { withCredentials: true });
        if (userPdfsResponse.data.success) {
          setUserPdfs(userPdfsResponse.data.pdfs);
        }
      } else {
        setError(response.data.error || 'Failed to remove selected PDFs.');
      }
    } catch (err) {
      console.error('Error removing selected PDFs:', err);
      if (err.response?.status === 401) {
        setError('Session expired. Please log in again.');
        setIsAuthenticated(false);
        navigate('/login');
      } else {
        setError(err.response?.data?.error || 'An unknown error occurred during PDF removal.');
      }
    }
  };

  const handleLogout = async () => {
    try {
      // Assuming logout clears session on backend
      await axios.post('/api/auth/logout', {}, { withCredentials: true });
      setIsAuthenticated(false);
      // No longer need to clear sessionStorage for processingJobs
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
          <Box>
            <Toolbar sx={{ pb: 0, minHeight: '48px' }}>
              <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <img src="/favicon.png" alt="MedStudyAI Logo" style={{ width: 28, height: 28 }} />
                <Typography variant="h6" component="h1" sx={{ fontWeight: 600 }}>
                  MedStudyAI
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
                  color={isQuizMode ? "primary" : "success"}
                  startIcon={<Logout />}
                  size="small"
                  sx={{ py: 0.5 }}
                >
                  Logout
                </Button>
              </Stack>
            </Toolbar>
            <Toolbar sx={{ pt: 0, mt: -2.5, mb: 0.5, minHeight: '48px' }}>
              <Box sx={{ display: 'flex', gap: 1, flexGrow: 1 }}>
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
                  sx={{ py: 1 }}
                  color={!isQuizMode ? "success" : "primary"}
                >
                  Home
                </Button>
                <Button
                  onClick={async () => {
                    try {
                      // Clear session content on the server
                      await axios.post('/api/clear-session-content', {}, { withCredentials: true });
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
                  variant="outlined"
                  startIcon={<CloudUpload />}
                  size="small"
                  sx={{ py: 1 }}
                  color={!isQuizMode ? "success" : "primary"}
                >
                  Upload PDFs
                </Button>
                <Button
                  onClick={async () => {
                    try {
                      // Clear session content on the server
                      await axios.post('/api/clear-session-content', {}, { withCredentials: true });
                      // Clear summary in App.js state
                      setSummary('');
                      // Navigate to study_session
                      navigate('/study_session');
                    } catch (err) {
                      console.error('Failed to clear session and navigate:', err);
                      // Still attempt to navigate even if clearing fails
                      navigate('/study_session');
                    }
                  }}
                  variant="outlined"
                  startIcon={<Description />} 
                  size="small"
                  sx={{ py: 1 }}
                  color={!isQuizMode ? "success" : "primary"}
                >
                  Study Session
                </Button>
              </Box>
            </Toolbar>
          </Box>
        </Container>
      </AppBar>

      {/* Main Content */}
      <Container maxWidth={false} sx={{ py: 2, px: { xs: 2, md: 6 }, textAlign: 'center' }}>
        <Typography variant="h2" component="h1" gutterBottom sx={{ mt: 2, mb: 4 }}>
          Upload PDFs to Begin
        </Typography>
        
        <Box sx={{ mt: 4, display: 'flex', flexDirection: { xs: 'column', md: 'row' }, alignItems: 'stretch', justifyContent: 'center', gap: 3 }}>
          {/* Left Column: Upload Box and Upload Button */}
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3, flex: 1.1 }}>
            <Paper
              elevation={2}
              onClick={!isUploading ? () => fileInputRef.current.click() : undefined}
              sx={{
                border: '2px dashed',
                borderColor: isUploading ? 'action.disabled' : 'divider',
                borderRadius: 2,
                p: 4,
                width: '100%',
                minHeight: 200,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: isUploading ? 'not-allowed' : 'pointer',
                bgcolor: (theme) => (
                  isUploading 
                    ? theme.palette.action.disabledBackground 
                    : (theme.palette.mode === 'light' ? 'action.hover' : 'background.paper')
                ),
                '&:hover': { 
                  borderColor: isUploading ? 'action.disabled' : 'primary.main' 
                },
                flexGrow: 1, // Allow the paper to grow vertically within its flex column
              }}
            >
              <CloudUpload sx={{ fontSize: 60, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" color="text.secondary" gutterBottom>
                Drag & Drop PDF files here, or click to browse
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Maximum 5 PDFs per upload
              </Typography>
              {selectedFiles.length > 0 && (
                <Stack sx={{ mt: 1, alignItems: 'center' }}>
                  {selectedFiles.map((file, index) => (
                    <Typography 
                      key={index} 
                      variant="body2" 
                      color="text.primary"
                      sx={{
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        maxWidth: '250px', // Adjust as needed
                      }}
                    >
                      {file.name}
                    </Typography>
                  ))}
                </Stack>
              )}
              <input
                type="file"
                multiple
                accept=".pdf"
                ref={fileInputRef}
                onChange={handleFileSelect}
                style={{ display: 'none' }}
              />
            </Paper>

            <Button
              variant="contained"
              color={!isQuizMode ? "success" : "primary"}
              size="large"
              startIcon={<CloudUpload />}
              onClick={handleUploadFiles}
              disabled={selectedFiles.length === 0 || isUploading}
              sx={{ maxWidth: 200, flexShrink: 0 }} // Prevent button from shrinking
            >
              {isUploading ? 'Uploading...' : 'Upload Files'}
            </Button>
          </Box>

          {/* Right Column: Processing Jobs Status Box */}
          {
              <Paper
                elevation={2}
                sx={{
                  border: '2px dashed',
                  borderColor: 'divider',
                  borderRadius: 2,
                  p: 4,
                  width: '100%',
                  minHeight: 200,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-start', // Align items to the top
                  justifyContent: 'flex-start', 
                  bgcolor: (theme) => (theme.palette.mode === 'light' ? 'action.hover' : 'background.paper'),
                  flex: 1.2, // Make it take equal width and stretch height
                }}
              >
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', mb: 2 }}>
                  <Typography variant="h4" color="text.secondary" gutterBottom sx={{ mb: 0 }}>
                    PDF Processing Statuses
                  </Typography>
                  <Button
                    variant="outlined"
                    color={!isQuizMode ? "success" : "primary"}
                    size="small"
                    onClick={handleClearCompletedTasks}
                    disabled={processingJobs.filter(job => job.status === 'SUCCESS' || job.status === 'FAILURE').length === 0}
                  >
                    Clear Completed
                  </Button>
                </Box>
                
                {processingJobs.length === 0 ? (
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 2, alignSelf: 'center' }}>
                        No processing jobs active.
                    </Typography>
                ) : (
                    <Stack sx={{ width: '100%', mt: 2 }} spacing={1} alignItems="flex-start">
                        {processingJobs.map((job, index) => (
                            <Box key={index} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <Typography 
                                    variant="body2" 
                                    color="text.primary"
                                    sx={{
                                        whiteSpace: 'nowrap',
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        minWidth: '250px',
                                        maxWidth: '250px', // Adjust as needed, considering the gap for message
                                    }}
                                >
                                    {job.filename}
                                </Typography>
                                <Typography variant="body2" color={(theme) => {
                                    if (job.status === 'SUCCESS') return theme.palette.success.main;
                                    if (job.status === 'FAILURE') return theme.palette.error.main;
                                    return theme.palette.info.main; // PENDING, STARTED
                                }}>
                                    {/* Display both status and message */}
                                    {job.status} - {job.message}
                                </Typography>
                            </Box>
                        ))}
                    </Stack>
                )}
              </Paper>
          }
        </Box>

        {/* User's Uploaded PDFs Box */}
        <Paper
          elevation={2}
          sx={{
            mt: 3, // Margin top to separate from the above boxes
            p: 4,
            width: '100%',
            bgcolor: (theme) => (theme.palette.mode === 'light' ? 'action.hover' : 'background.paper'),
            borderRadius: 2,
            textAlign: 'left',
          }}
        >
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h3" color="text.primary" gutterBottom sx={{ mb: 0, ml: 4 }}>
              Your Uploaded PDFs ({userPdfs.length})
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mr: 1 }}>
                <Checkbox
                  indeterminate={selectedPdfHashes.length > 0 && selectedPdfHashes.length < userPdfs.length}
                  checked={userPdfs.length > 0 && selectedPdfHashes.length === userPdfs.length}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedPdfHashes(userPdfs.map(pdf => pdf.hash));
                    } else {
                      setSelectedPdfHashes([]);
                    }
                  }}
                  disabled={userPdfs.length === 0}
                  size="small"
                  sx={{ p: 1 }}
                />
                <Typography variant="body2" color="text.secondary" sx={{ ml: -0.5 }}>Select All</Typography>
              </Box>
              <Button
                variant="contained"
                color="error"
                size="small"
                onClick={handleRemoveSelectedPdfs}
                disabled={selectedPdfHashes.length === 0}
              >
                Remove PDFs ({selectedPdfHashes.length})
              </Button>
              <Button
                variant={userPdfs.length > 0 ? "contained" : "outlined"}
                startIcon={<Description />}
                size="small"
                color={!isQuizMode ? "success" : "primary"}
                onClick={async () => {
                  try {
                    await axios.post('/api/clear-session-content', {}, { withCredentials: true });
                    setSummary('');
                    navigate('/study_session');
                  } catch (err) {
                    console.error('Failed to clear session and navigate:', err);
                    navigate('/study_session');
                  }
                }}
              >
                New Study Session
              </Button>
            </Box>
          </Box>
          
          <List dense sx={{ width: '100%' }}>
            {userPdfs.length > 0 ? (
              userPdfs.map((pdf) => (
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
                  <Checkbox
                    checked={selectedPdfHashes.includes(pdf.hash)}
                    onChange={() => {
                      setSelectedPdfHashes(prevSelected => {
                        if (prevSelected.includes(pdf.hash)) {
                          return prevSelected.filter(hash => hash !== pdf.hash);
                        } else {
                          return [...prevSelected, pdf.hash];
                        }
                      });
                    }}
                    size="small"
                  />
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
                        <Typography variant="body2" color="text.secondary" display="block" sx={{ mt: 0.2 }}>
                          {new Date(pdf.created_at).toLocaleString()}
                        </Typography>
                      </>
                    } // Display filename and created_at as secondary
                    secondaryTypographyProps={{
                      component: 'div' // Ensure secondary is rendered as a block to contain inner elements
                    }}
                  />
                </ListItem>
              ))
            ) : (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                No PDFs found. Upload new PDFs using the section above.
              </Typography>
            )}
          </List>
        </Paper>
      </Container>
      <FeedbackButton />

      {/* Floating Alerts for Upload Status */ }
      <Box 
        sx={{
          position: 'fixed',
          bottom: 16,
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 1300, // Above AppBars and other content
          width: { xs: '90%', sm: '60%', md: '40%' }, // Responsive width
          maxWidth: '500px', // Max width for larger screens
        }}
      >
        <Stack spacing={1}>
          {error && (
            <Alert severity="error" sx={{ borderRadius: 2, width: '100%' }}>
              {error}
            </Alert>
          )}
          {successMessage && (
            <Alert severity="success" sx={{ borderRadius: 2, width: '100%' }}>
              {successMessage}
            </Alert>
          )}
          
          {uploadedFilesReport.length > 0 && (
              <Alert severity="success" sx={{ borderRadius: 2, width: '100%' }}>
                  <Typography variant="subtitle2">Successfully Uploaded:</Typography>
                  <ul>
                      {uploadedFilesReport.map((file, index) => (
                          <li key={index}>{file.filename}</li>
                      ))}
                  </ul>
              </Alert>
          )}

          {failedFilesReport.length > 0 && (
              <Alert severity="error" sx={{ borderRadius: 2, width: '100%' }}>
                  <Typography variant="subtitle2">Failed Uploads:</Typography>
                  <ul>
                      {failedFilesReport.map((file, index) => (
                          <li key={index}>{file.filename} - {file.error}</li>
                      ))}
                  </ul>
              </Alert>
          )}
        </Stack>
      </Box>
    </Box>
  );
};

export default Upload_pdfs; 