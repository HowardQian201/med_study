import React, { useState, useRef } from 'react';
import { Box, Typography, Container, AppBar, Toolbar, Stack, Button, Paper, Alert } from '@mui/material';
import { Home as HomeIcon, Logout, CloudUpload } from '@mui/icons-material';
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
  const [existingFilesReport, setExistingFilesReport] = useState([]);
  const [failedFilesReport, setFailedFilesReport] = useState([]);

  const handleFileSelect = (event) => {
    // Implementation will go here later
    console.log('Files selected:', event.target.files);
    setSelectedFiles(Array.from(event.target.files));
    setError('');
    setSuccessMessage('');
    setUploadedFilesReport([]);
    setExistingFilesReport([]);
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
    setExistingFilesReport([]);
    setFailedFilesReport([]);

    const formData = new FormData();
    selectedFiles.forEach(file => {
      formData.append('files', file);
    });

    try {
      const response = await axios.post('/api/upload-pdfs', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        withCredentials: true,
      });

      if (response.data.success) {
        // setSuccessMessage(response.data.message || 'Files uploaded successfully!');
        setUploadedFilesReport(response.data.uploaded_files || []);
        setExistingFilesReport(response.data.existing_files || []);
        setFailedFilesReport(response.data.failed_files || []);
        
        let generalMessage = '';
        if (response.data.uploaded_files.length > 0) {
            generalMessage += `Successfully uploaded ${response.data.uploaded_files.length} files. `;
        }
        if (response.data.existing_files.length > 0) {
            generalMessage += `Skipped ${response.data.existing_files.length} existing files. `;
        }
        if (response.data.failed_files.length > 0) {
            generalMessage += `Failed to upload ${response.data.failed_files.length} files.`;
        }

        if (generalMessage) {
            setSuccessMessage(generalMessage);
        } else {
            setSuccessMessage('Operation completed with no new uploads, existing files, or failures.');
        }

        setSelectedFiles([]);
        fileInputRef.current.value = null;
      } else {
        setError(response.data.error || 'File upload failed.');
      }
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
      <Container maxWidth="xl" sx={{ py: 4, textAlign: 'center' }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Upload PDFs
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Upload your PDFs here to start studying.
        </Typography>
        
        {error && (
          <Alert severity="error" sx={{ mt: 3, borderRadius: 2 }}>
            {error}
          </Alert>
        )}
        {successMessage && (
          <Alert severity="success" sx={{ mt: 3, borderRadius: 2 }}>
            {successMessage}
          </Alert>
        )}
        
        {uploadedFilesReport.length > 0 && (
            <Alert severity="success" sx={{ mt: 1, borderRadius: 2 }}>
                <Typography variant="subtitle2">Successfully Uploaded:</Typography>
                <ul>
                    {uploadedFilesReport.map((file, index) => (
                        <li key={index}>{file.filename}</li>
                    ))}
                </ul>
            </Alert>
        )}

        {existingFilesReport.length > 0 && (
            <Alert severity="info" sx={{ mt: 1, borderRadius: 2 }}>
                <Typography variant="subtitle2">Already Existed:</Typography>
                <ul>
                    {existingFilesReport.map((file, index) => (
                        <li key={index}>{file.filename}</li>
                    ))}
                </ul>
            </Alert>
        )}

        {failedFilesReport.length > 0 && (
            <Alert severity="error" sx={{ mt: 1, borderRadius: 2 }}>
                <Typography variant="subtitle2">Failed Uploads:</Typography>
                <ul>
                    {failedFilesReport.map((file, index) => (
                        <li key={index}>{file.filename} - {file.error}</li>
                    ))}
                </ul>
            </Alert>
        )}
        
        <Box sx={{ mt: 4, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
          <Paper
            elevation={2}
            sx={{
              border: '2px dashed',
              borderColor: 'divider',
              borderRadius: 2,
              p: 4,
              width: '100%',
              maxWidth: 600,
              minHeight: 200,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              bgcolor: (theme) => (theme.palette.mode === 'light' ? 'action.hover' : 'background.paper'),
              '&:hover': { borderColor: 'primary.main' },
            }}
            onClick={() => fileInputRef.current.click()}
          >
            <CloudUpload sx={{ fontSize: 60, color: 'text.secondary', mb: 2 }} />
            <Typography variant="h6" color="text.secondary" gutterBottom>
              Drag & Drop PDF files here, or click to browse
            </Typography>
            {selectedFiles.length > 0 && (
              <Stack sx={{ mt: 1, alignItems: 'center' }}>
                {selectedFiles.map((file, index) => (
                  <Typography key={index} variant="body2" color="text.primary">
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
            color="primary"
            size="large"
            startIcon={<CloudUpload />}
            onClick={handleUploadFiles}
            disabled={selectedFiles.length === 0 || isUploading}
            sx={{ maxWidth: 200 }}
          >
            {isUploading ? 'Uploading...' : 'Upload Files'}
          </Button>
        </Box>
      </Container>
      <FeedbackButton />
    </Box>
  );
};

export default Upload_pdfs; 