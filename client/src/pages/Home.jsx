import React, { useState, useEffect } from 'react';
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
  CircularProgress,
  Alert,
  Stack,
  Paper,
  Grid,
  TextField,
  IconButton,
  ButtonBase
} from '@mui/material';
import {
  Logout,
  ArrowForward,
  Book,
  History,
  Edit as EditIcon,
  Save as SaveIcon,
  Cancel as CancelIcon,
} from '@mui/icons-material';
import ThemeToggle from '../components/ThemeToggle';
import { format } from 'date-fns';

const Home = ({ user, setIsAuthenticated, setSummary }) => {
  const navigate = useNavigate();
  const [sets, setSets] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [loadingSet, setLoadingSet] = useState(null);
  
  // State for editing titles
  const [editingSetHash, setEditingSetHash] = useState(null);
  const [editingTitle, setEditingTitle] = useState('');

  useEffect(() => {
    const fetchSets = async () => {
      try {
        const response = await axios.get('/api/get-question-sets', {
          withCredentials: true,
        });
        if (response.data.success) {
          setSets(response.data.sets);
        } else {
          setError('Failed to load study sets.');
        }
      } catch (err) {
        if (err.response?.status === 401) {
            navigate('/login');
        } else {
            setError(err.response?.data?.error || 'An error occurred while fetching study sets.');
        }
      } finally {
        setIsLoading(false);
      }
    };

    if (user) {
        fetchSets();
    }
  }, [user, navigate]);

  const handleLogout = async () => {
    try {
      await axios.post('/api/auth/logout', {}, { withCredentials: true });
      setIsAuthenticated(false);
      navigate('/login');
    } catch (err) {
      console.error('Logout failed:', err);
      setIsAuthenticated(false);
      navigate('/login');
    }
  };

  const handleStartNewSession = () => {
    navigate('/pdf_summary');
  };
  
  const handleLoadSet = async (contentHash) => {
    setLoadingSet(contentHash);
    setError('');
    try {
        const response = await axios.post('/api/load-study-set', { content_hash: contentHash }, {
            withCredentials: true
        });

        if (response.data.success) {
            setSummary(response.data.summary || '');
            navigate('/quiz');
        } else {
            setError('Failed to load the selected study set.');
        }

    } catch (err) {
        setError(err.response?.data?.error || 'An error occurred while loading the set.');
    } finally {
        setLoadingSet(null);
    }
  }

  const handleEditStart = (set) => {
    setEditingSetHash(set.hash);
    setEditingTitle(set.short_summary || '');
  };

  const handleEditCancel = () => {
    setEditingSetHash(null);
    setEditingTitle('');
  };

  const handleEditSave = async (contentHash) => {
    if (!editingTitle.trim()) {
        setError('Title cannot be empty.');
        return;
    }

    // Get the current set being edited
    const currentSet = sets.find(s => s.hash === contentHash);
    if (currentSet && currentSet.short_summary === editingTitle.trim()) {
        // If title hasn't changed, just exit edit mode
        handleEditCancel();
        return;
    }
    
    try {
        const response = await axios.post('/api/update-set-title', {
            content_hash: contentHash,
            new_title: editingTitle
        }, {
            withCredentials: true
        });

        if (response.data.success) {
            // Update the local state to reflect the change immediately
            setSets(sets.map(s => s.hash === contentHash ? { ...s, short_summary: editingTitle } : s));
            handleEditCancel(); // Exit editing mode
        } else {
            setError('Failed to update the title.');
        }
    } catch (err) {
        setError(err.response?.data?.error || 'An error occurred while saving the title.');
    }
  };


  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      {/* App Bar */}
      <AppBar position="static" color="default" elevation={1}>
        <Container maxWidth="xl">
          <Toolbar>
            <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <img src="/favicon.png" alt="MedStudy.AI Logo" style={{ width: 28, height: 28 }} />
              <Typography variant="h6" component="h1" sx={{ fontWeight: 600 }}>
                MedStudy.AI
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
        </Container>
      </AppBar>

      {/* Main Content */}
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Stack spacing={4} alignItems="center">
            {/* Description and New Session */}
            <Card elevation={3} sx={{ p: 2, width: '100%', maxWidth: 1200 }}>
                <CardContent sx={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'center',
                    minHeight: '80px'
                }}>
                    <Box sx={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: 6,
                        justifyContent: 'center',
                        width: '100%'
                    }}>
                        <Box sx={{ flex: '0 0 60%' }}>
                            <Typography variant="h6" color="text.primary">
                                Transform your medical PDFs and notes into interactive study materials with AI-generated summaries and USMLE clinical vignette style questions.
                            </Typography>
                        </Box>
                        <Button
                            variant="contained"
                            color="primary"
                            size="large"
                            startIcon={<Book />}
                            onClick={handleStartNewSession}
                            sx={{ flexShrink: 0 }}
                        >
                            Start New Study Session
                        </Button>
                    </Box>
                </CardContent>
            </Card>

            {/* Previous Sets */}
            <Paper elevation={2} sx={{ p: 3, width: '100%', maxWidth: 1200 }}>
                <Box display="flex" alignItems="center" mb={2}>
                    <History sx={{ mr: 1, color: 'text.secondary' }}/>
                    <Typography variant="h5" component="h3" fontWeight="600">
                        Previous Study Sets
                    </Typography>
                </Box>

                {isLoading ? (
                    <Box textAlign="center" p={3}><CircularProgress /></Box>
                ) : error ? (
                    <Alert severity="error">{error}</Alert>
                ) : sets.length === 0 ? (
                    <Alert severity="info">You don't have any previous study sets. Start a new session to begin!</Alert>
                ) : (
                    <Grid container spacing={3}>
                        {sets.map((set) => (
                            <Grid item xs={12} sm={6} md={4} lg={3} sx={{ 
                                width: {
                                    xs: '100%',
                                    sm: 'calc((100% - 24px) / 2)',
                                    md: 'calc((100% - 48px) / 3)',
                                    lg: 'calc((100% - 72px) / 4)'
                                },
                                maxWidth: {
                                    xs: 'none',
                                    sm: 'calc((1200px - 24px) / 2)',
                                    md: 'calc((1200px - 48px) / 3)',
                                    lg: 'calc((1200px - 72px) / 4)'
                                }
                            }} key={set.hash}>
                                <Card 
                                    elevation={1} 
                                    sx={{ 
                                        '&:hover': {
                                            boxShadow: 4,
                                            borderColor: 'primary.main'
                                        },
                                        border: '1px solid',
                                        borderColor: 'divider',
                                        transition: 'all 0.2s ease',
                                        height: '100%'
                                    }}
                                >
                                    <CardContent>
                                        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                                            <Box sx={{ mb: 1 }}>
                                                {editingSetHash === set.hash ? (
                                                    <TextField
                                                        value={editingTitle}
                                                        onChange={(e) => setEditingTitle(e.target.value)}
                                                        variant="outlined"
                                                        size="small"
                                                        fullWidth
                                                        autoFocus
                                                        multiline
                                                        rows={3}
                                                        onBlur={() => {
                                                            // Small delay to allow save button click to register
                                                            setTimeout(() => {
                                                                handleEditCancel();
                                                            }, 50);
                                                        }}
                                                        sx={{ 
                                                            mb: 2,
                                                            '& .MuiInputBase-input': {
                                                                textAlign: 'center',
                                                                height: '3.9em !important',
                                                                overflow: 'hidden',
                                                                lineHeight: '1.3',
                                                                resize: 'none',
                                                                fontSize: 'h6.fontSize',
                                                                fontWeight: 'bold',
                                                                padding: '4px !important'
                                                            },
                                                            '& .MuiOutlinedInput-root': {
                                                                height: '3.9em',
                                                                padding: 0
                                                            },
                                                            '& .MuiOutlinedInput-notchedOutline': {
                                                                borderRadius: 1
                                                            }
                                                        }}
                                                    />
                                                ) : (
                                                    <ButtonBase 
                                                        onClick={(e) => {
                                                            e.preventDefault();
                                                            handleEditStart(set);
                                                        }}
                                                        sx={{ 
                                                            display: 'block', 
                                                            textAlign: 'left', 
                                                            width: '100%',
                                                            borderRadius: 1,
                                                            '&:hover': {
                                                                backgroundColor: 'action.hover'
                                                            }
                                                        }}
                                                    >
                                                        <Typography variant="h6" fontWeight="bold" sx={{ 
                                                            height: '3.9em', 
                                                            lineHeight: 1.3,
                                                            overflow: 'hidden',
                                                            textOverflow: 'ellipsis',
                                                            display: '-webkit-box',
                                                            WebkitLineClamp: 3,
                                                            WebkitBoxOrient: 'vertical',
                                                            p: '4px',
                                                            textAlign: 'center',
                                                            mb: 1.5
                                                        }}>
                                                            {set.short_summary || 'Untitled Set'}
                                                        </Typography>
                                                    </ButtonBase>
                                                )}
                                                <Typography variant="body2" color="text.secondary" sx={{
                                                    overflow: 'hidden',
                                                    textOverflow: 'ellipsis',
                                                    whiteSpace: 'nowrap'
                                                }}>
                                                    Sources: {set.metadata?.content_names?.join(', ') || 'N/A'}
                                                </Typography>
                                                <Typography variant="caption" color="text.secondary" display="block">
                                                    Created: {format(new Date(set.created_at), "PPP p")}
                                                </Typography>
                                            </Box>
                                            <Box sx={{ mt: 'auto', display: 'flex', justifyContent: 'center', pt: 1 }}>
                                                {editingSetHash === set.hash ? (
                                                    <Stack direction="row" spacing={1} width="100%">
                                                        <Button onClick={handleEditCancel} variant="contained" size="small" fullWidth startIcon={<CancelIcon />}>Cancel</Button>
                                                        <Button onClick={() => handleEditSave(set.hash)} variant="contained" size="small" fullWidth startIcon={<SaveIcon />}>Save</Button>
                                                    </Stack>
                                                ) : (
                                                    <Button
                                                        variant="contained"
                                                        onClick={() => handleLoadSet(set.hash)}
                                                        disabled={loadingSet === set.hash}
                                                        endIcon={loadingSet === set.hash ? <CircularProgress size={16} /> : <ArrowForward />}
                                                        fullWidth
                                                        sx={{ maxWidth: '200px' }}
                                                    >
                                                        {loadingSet === set.hash ? 'Loading' : 'Review'}
                                                    </Button>
                                                )}
                                            </Box>
                                        </Box>
                                    </CardContent>
                                </Card>
                            </Grid>
                        ))}
                    </Grid>
                )}
            </Paper>
        </Stack>
      </Container>
    </Box>
  );
};

export default Home;