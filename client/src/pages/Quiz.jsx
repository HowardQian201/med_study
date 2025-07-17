import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useHotkeys } from 'react-hotkeys-hook';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
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
  Stack,
  Paper,
  FormControl,
  Chip,
  CircularProgress,
  Collapse,
  TextField
} from '@mui/material';
import {
  ArrowBack,
  ArrowForward,
  Check,
  Close,
  Refresh,
  Add,
  Home as HomeIcon,
  Logout,
  CheckCircle,
  Cancel,
  HelpOutline,
  Shuffle as ShuffleIcon,
  Star,
  StarBorder,
  Description as DescriptionIcon,
  CloudUpload
} from '@mui/icons-material';
import ThemeToggle from '../components/ThemeToggle';
import { alpha } from '@mui/material/styles';
import { Link } from '@mui/material';
import FeedbackButton from '../components/FeedbackButton';

const Quiz = ({ user, summary: propSummary, setSummary, setIsAuthenticated }) => {
  const navigate = useNavigate();
  const [questions, setQuestions] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState({});
  const [submittedAnswers, setSubmittedAnswers] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [showResults, setShowResults] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(true);
  const [isGeneratingMoreQuestions, setIsGeneratingMoreQuestions] = useState(false);
  const [visibleExplanation, setVisibleExplanation] = useState(null);
  const [numAdditionalQuestions, setNumAdditionalQuestions] = useState(5);
  const [isQuizMode, setIsQuizMode] = useState(false);
  const [isCardFlipped, setIsCardFlipped] = useState(false);
  const [currentSessionSources, setCurrentSessionSources] = useState([]); // New state for sources
  const [currentSessionShortSummary, setCurrentSessionShortSummary] = useState('');
  const [contentHash, setContentHash] = useState('');
  const [generationTimer, setGenerationTimer] = useState(0);
  const [showAnswersInPreview, setShowAnswersInPreview] = useState(false); // Changed to false to hide answers by default

  // Use refs to prevent duplicate calls
  const isFetching = useRef(false);
  const timerRef = useRef(null);

  // Timer effect for question generation
  useEffect(() => {
    const shouldShowTimer = isGeneratingMoreQuestions || isLoading;
    
    if (shouldShowTimer) {
      // Always reset timer when starting a new generation
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      setGenerationTimer(0);
      timerRef.current = setInterval(() => {
        setGenerationTimer(prev => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [isGeneratingMoreQuestions, isLoading]);

  // Helper function to format timer display
  const formatTimer = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Hotkey handlers
  const handleKeyboardAnswer = (optionIndex) => {
    const currentQuestionId = questions[currentQuestion]?.id;
    if (currentQuestionId && !submittedAnswers[currentQuestionId] && isQuizMode) {
      handleAnswerSelect(currentQuestionId, optionIndex);
    }
  };

  // Hotkey bindings
  useHotkeys('left', (e) => {
    e.preventDefault();
    if (!isPreviewing && !showResults) {
      moveToPreviousQuestion();
    }
  }, [currentQuestion, isPreviewing, showResults]);

  useHotkeys('right', (e) => {
    e.preventDefault();
    if (!isPreviewing && !showResults) {
      moveToNextQuestion();
    }
  }, [currentQuestion, isPreviewing, showResults, questions.length]);

  useHotkeys('space', (e) => {
    e.preventDefault();
    if (!isPreviewing && !showResults && !isQuizMode) {
      setIsCardFlipped(!isCardFlipped);
    }
  }, [isPreviewing, showResults, isQuizMode, isCardFlipped]);

  useHotkeys('enter', (e) => {
    e.preventDefault();
    if (!isPreviewing && !showResults && !isQuizMode) {
      setIsCardFlipped(!isCardFlipped);
    }
  }, [isPreviewing, showResults, isQuizMode, isCardFlipped]);

  useHotkeys('enter', (e) => {
    e.preventDefault();
    const currentQuestionId = questions[currentQuestion]?.id;
    if (!isPreviewing && !showResults && isQuizMode) {
      if (submittedAnswers[currentQuestionId]) {
        // If answer was submitted, go to next question
        moveToNextQuestion();
      } else if (selectedAnswers[currentQuestionId] !== undefined) {
        // If answer is selected but not submitted, submit it
        handleSubmitAnswer(currentQuestionId);
      }
    }
  }, [currentQuestion, isPreviewing, showResults, isQuizMode, selectedAnswers, submittedAnswers, questions]);

  // Number key bindings for answer selection (1-4 for A-D)
  useHotkeys('1', () => handleKeyboardAnswer(0), [currentQuestion, submittedAnswers, isQuizMode]);
  useHotkeys('2', () => handleKeyboardAnswer(1), [currentQuestion, submittedAnswers, isQuizMode]);
  useHotkeys('3', () => handleKeyboardAnswer(2), [currentQuestion, submittedAnswers, isQuizMode]);
  useHotkeys('4', () => handleKeyboardAnswer(3), [currentQuestion, submittedAnswers, isQuizMode]);

  // Hotkey for starring/unstarring current question
  const handleToggleStar = useCallback(async (questionId) => {
    try {
      const response = await axios.post('/api/toggle-star-question', { questionId }, { withCredentials: true });
      if (response.data.success && response.data.question) {
        setQuestions(prevQuestions =>
          prevQuestions.map(q =>
            q.id === questionId ? { ...q, starred: response.data.question.starred } : q
          )
        );

      } else {
        setError('Failed to toggle star status');
      }
    } catch (err) {
      console.error('Error toggling star status:', err);
      setError(err.response?.data?.error || 'Failed to toggle star status');
    }
  }, [setQuestions, setError]);

  useHotkeys('s', (e) => {
    e.preventDefault();
    if (questions.length > 0 && !isPreviewing && !showResults) {
      handleToggleStar(questions[currentQuestion].id);
    }
  }, [currentQuestion, questions, isPreviewing, showResults, handleToggleStar]);

  // Helper function to clean option text and remove existing A), B), C), D) prefixes
  const cleanOptionText = (option) => {
    // Remove patterns like "A) ", "B. ", "C) ", "D. ", etc.
    return option.replace(/^[A-D][.)]\s*/, '').trim();
  };

  // Fetch questions from the API when the component mounts or the summary changes.
  useEffect(() => {
    const storedQuizMode = sessionStorage.getItem('isQuizMode');
    if (storedQuizMode) {
      setIsQuizMode(storedQuizMode === 'true');
    }
    if (!propSummary) {
      setIsLoading(false);
      return;
    }

    if (isFetching.current) {
      return;
    }

    const fetchQuiz = async () => {
      isFetching.current = true;
        setIsLoading(true);
        setError('');
        
      try {
        // First try to get existing questions from the session
        const existingResponse = await axios.get('/api/get-quiz', {
          withCredentials: true
        });
        
        if (existingResponse.data.success && existingResponse.data.questions.length > 0) {
          setQuestions(existingResponse.data.questions);
        } else {
        // If no existing questions, generate new ones
        const numQuestions = parseInt(sessionStorage.getItem('numQuestions')) || 5;
        const isQuizModeBoolean = sessionStorage.getItem('isQuizMode') === 'true';
        const response = await axios.post('/api/generate-quiz', {
          type: 'initial',
          numQuestions: numQuestions,
          isQuizMode: String(isQuizModeBoolean), // Ensure it's a string "true" or "false"
          incorrectQuestionIds: [],
          previousQuestions: [],
          isPreviewing: false,
        }, {
          withCredentials: true
        });
        
        if (response.data.success && response.data.questions) {
          setQuestions(response.data.questions);
          setCurrentSessionShortSummary(response.data.short_summary || '');
        } else if (response.data.error === "Quiz set already exists") {
          setError("Quiz set for that material already exists. Here it is!");
          setContentHash(response.data.content_hash);
        } else {
          setError('Failed to generate quiz questions');
        }
        }
      } catch (err) {
        console.error('Error fetching quiz questions:', err);
        setError(err.response?.data?.error || 'Failed to generate quiz questions');
      } finally {
        setIsLoading(false);
        isFetching.current = false;
      }
    };

    fetchQuiz();
    
    // Cleanup function to prevent fetching if component unmounts
    return () => {
        isFetching.current = false;
    }
  }, [propSummary]);

  // New useEffect to fetch current session sources
  useEffect(() => {
    const fetchCurrentSessionSources = async () => {
      try {
        const response = await axios.get('/api/get-current-session-sources', { withCredentials: true });
        if (response.data.success) {
          setCurrentSessionSources(response.data.content_names);
          setCurrentSessionShortSummary(response.data.short_summary);
        } else {
          console.error("Failed to fetch current session sources:", response.data.error);
        }
      } catch (err) {
        console.error("Error fetching current session sources:", err);
        if (err.response?.status === 401) {
          setIsAuthenticated(false);
          navigate('/login');
        }
      }
    };

    fetchCurrentSessionSources();
  }, [setIsAuthenticated, navigate]); // Dependencies to re-run effect if auth/navigation changes

  const handleAnswerSelect = (questionId, optionIndex) => {
    // Only allow selection if the answer hasn't been submitted yet
    if (!submittedAnswers[questionId]) {
      setSelectedAnswers({
        ...selectedAnswers,
        [questionId]: optionIndex
      });
    }
  };

  const handleSubmitAnswer = (questionId) => {
    setSubmittedAnswers({ ...submittedAnswers, [questionId]: true });

    const question = questions.find(q => q.id === questionId);
    const wasCorrect = selectedAnswers[questionId] === question.correctAnswer;
    
    setVisibleExplanation({
      isCorrect: wasCorrect,
      reason: question.reason
    });
    
    setTimeout(() => saveUserAnswers(), 100);
  };

  const handleStartQuiz = () => {
    setIsPreviewing(false);
  };

  const shuffleQuestions = async () => {
    try {
      setIsLoading(true);
      setError('');
      const response = await axios.post('/api/shuffle-quiz', {}, { withCredentials: true });
      if (response.data.success && response.data.questions) {
        setQuestions(response.data.questions);
        // Reset quiz state to reflect new question order
        setSelectedAnswers({});
        setSubmittedAnswers({});
        setVisibleExplanation(null);
        setCurrentQuestion(0);
      } else {
        setError('Failed to shuffle questions');
      }
    } catch (err) {
      console.error('Error shuffling questions:', err);
      setError(err.response?.data?.error || 'Failed to shuffle questions');
    } finally {
      setIsLoading(false);
    }
  };

  const moveToNextQuestion = () => {
    if (currentQuestion < questions.length - 1) {
      const nextQuestionIndex = currentQuestion + 1;
      const nextQuestion = questions[nextQuestionIndex];
      setIsCardFlipped(false);

      if (submittedAnswers[nextQuestion.id]) {
        const wasCorrect = selectedAnswers[nextQuestion.id] === nextQuestion.correctAnswer;
        setVisibleExplanation({
          isCorrect: wasCorrect,
          reason: nextQuestion.reason
        });
      } else {
        setVisibleExplanation(null);
      }
      setCurrentQuestion(nextQuestionIndex);
    } else {
      setShowResults(true);
    }
  };

  const moveToPreviousQuestion = () => {
    if (currentQuestion > 0) {
      const prevQuestionIndex = currentQuestion - 1;
      const prevQuestion = questions[prevQuestionIndex];
      setIsCardFlipped(false);

      if (submittedAnswers[prevQuestion.id]) {
        const wasCorrect = selectedAnswers[prevQuestion.id] === prevQuestion.correctAnswer;
        setVisibleExplanation({
          isCorrect: wasCorrect,
          reason: prevQuestion.reason
        });
      } else {
        setVisibleExplanation(null);
      }
      setCurrentQuestion(prevQuestionIndex);
    }
  };

  const resetQuiz = () => {
    setSelectedAnswers({});
    setSubmittedAnswers({});
    setVisibleExplanation(null);
    setCurrentQuestion(0);
    setShowResults(false);
    setIsPreviewing(true);
  };

  const generateAdditionalQuestions = async () => {
    try {
      setIsGeneratingMoreQuestions(true);
      setError('');

      const isQuizModeBoolean = sessionStorage.getItem('isQuizMode') === 'true';
      const response = await axios.post('/api/generate-quiz', {
        type: 'additional',
        incorrectQuestionIds: [],
        previousQuestions: questions,
        isPreviewing: true,
        numQuestions: numAdditionalQuestions,
        isQuizMode: String(isQuizModeBoolean)
      }, {
        withCredentials: true
      });

      if (response.data.success && response.data.questions) {
        // Add new questions to the existing set
        setQuestions(prevQuestions => [...prevQuestions, ...response.data.questions]);
      } else {
        setError('Failed to generate more questions');
      }
    } catch (err) {
      console.error('Error generating more questions:', err);
      setError(err.response?.data?.error || 'Failed to generate more questions');
    } finally {
      setIsGeneratingMoreQuestions(false);
    }
  };

  const handleBack = async () => {
    try {
      // Clear session content on the server
      await axios.post('/api/clear-session-content', {}, { withCredentials: true });
      // Clear summary in App.js state
      if (setSummary) {
        setSummary('');
      }
      // Navigate to home
      navigate('/');
    } catch (err) {
      console.error('Failed to clear session and navigate:', err);
      // Still attempt to navigate even if clearing fails
      navigate('/');
    }
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
      setIsAuthenticated(false);
      navigate('/login');
    }
  };
  
  // Calculate quiz statistics
  const calculateStats = () => {
    if (questions.length === 0) return { correct: 0, total: 0, percentage: 0, questionsWithStatus: [] };
    
    const questionsWithStatus = questions.map(q => ({
      ...q,
      userAnswer: selectedAnswers[q.id] !== undefined ? selectedAnswers[q.id] : null,
      isCorrect: selectedAnswers[q.id] === q.correctAnswer,
      isAnswered: submittedAnswers[q.id] === true
    }));
    
    const answeredQuestions = questionsWithStatus.filter(q => q.isAnswered);
    const correctAnswers = questionsWithStatus.filter(q => q.isCorrect && q.isAnswered);
    const totalQuestions = questions.length;
    
    return {
      correct: correctAnswers.length,
      total: totalQuestions,
      percentage: answeredQuestions.length > 0 
        ? Math.round((correctAnswers.length / totalQuestions) * 100) 
        : 0,
      questionsWithStatus
    };
  };
  
  // Check if all questions have been answered
  const allQuestionsAnswered = questions.length > 0 && 
    questions.every(question => submittedAnswers[question.id]);

  const stats = calculateStats();
  const starredQuestionsCount = questions.filter(q => q.starred).length;

  // Function to save user answers to the backend
  const saveUserAnswers = async () => {
    try {
      await axios.post('/api/save-quiz-answers', {
        userAnswers: selectedAnswers,
        submittedAnswers: submittedAnswers
      }, {
        withCredentials: true
      });

    } catch (err) {
      console.error('Error saving quiz answers:', err);
      // Don't show error to user as this is background functionality
    }
  };

  // Combine the functions to complete the quiz and show results
  const completeQuiz = async () => {
    // Save answers before showing results
    await saveUserAnswers();
    
    setShowResults(true);
  };

  const handleStartStarredQuiz = async () => {
    try {
      setIsLoading(true);
      setError('');
      const response = await axios.post('/api/start-starred-quiz', {}, { withCredentials: true });
      if (response.data.success && response.data.questions) {
        setQuestions(response.data.questions);
        // Reset quiz state for the new starred quiz
        setSelectedAnswers({});
        setSubmittedAnswers({});
        setVisibleExplanation(null);
        setCurrentQuestion(0);
        setShowResults(false);
        setIsPreviewing(false); // Start the quiz immediately
      } else {
        setError(response.data.error || 'Failed to start starred quiz');
      }
    } catch (err) {
      console.error('Error starting starred quiz:', err);
      setError(err.response?.data?.error || 'Failed to start starred quiz');
    } finally {
      setIsLoading(false);
    }
  };

  const handleBulkStarQuestions = async (action) => {
    try {
      setError('');
      const response = await axios.post('/api/star-all-questions', { action }, { withCredentials: true });
      if (response.data.success && response.data.questions) {
        setQuestions(response.data.questions);
        
      } else {
        const actionText = action === 'star' ? 'star' : 'unstar';
        setError(`Failed to ${actionText} all questions`);
      }
    } catch (err) {
      const actionText = action === 'star' ? 'starring' : 'unstarring';
      console.error(`Error ${actionText} all questions:`, err);
      setError(err.response?.data?.error || `Failed to ${actionText.replace('ing', '')} all questions`);
    }
  };

  const handleStarAllQuestions = () => handleBulkStarQuestions('star');
  const handleUnstarAllQuestions = () => handleBulkStarQuestions('unstar');

  const handleBackToPreview = () => {
    setIsPreviewing(true);
    setShowResults(false);
  };

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      {/* App Bar */}
      <AppBar position="static" color="default" elevation={1} sx={{ minWidth: 1100 }}>
        <Container maxWidth="xl">
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
                  color="primary"
                  startIcon={<Logout />}
                  size="small"
                  sx={{ py: 0.5 }}
                >
                  Logout
                </Button>
              </Stack>
            </Toolbar>
            <Toolbar sx={{ pt: 0, mt: -2.5, mb: 0.5, minHeight: '48px', width: '100%' }}>
              <Box sx={{ display: 'flex', gap: 1, flexGrow: 1 }}>
                <Button
                  onClick={handleBack}
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
                      if (setSummary) {
                        setSummary('');
                      }
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
                      if (setSummary) {
                        setSummary('');
                      }
                      // Navigate to study_session
                      navigate('/study_session');
                    } catch (err) {
                      console.error('Failed to clear session and navigate:', err);
                      // Still attempt to navigate even if clearing fails
                      navigate('/study_session');
                    }
                  }}
                  variant="outlined"
                  startIcon={<DescriptionIcon />}
                  size="small"
                  sx={{ py: 1 }}
                  color={!isQuizMode ? "success" : "primary"}
                >
                  Study Session
                </Button>
                {(showResults || !isPreviewing) && (
                  <Button
                    onClick={handleBackToPreview}
                    variant="outlined"
                    startIcon={<ArrowBack />}
                    size="small"
                    sx={{ py: 1 }}
                    color={isQuizMode ? "success" : "primary"}
                  >
                    Preview
                  </Button>
                )}
              </Box>
              {(() => {
                const isQuizMode = sessionStorage.getItem('isQuizMode') === 'true';
                return (
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
                );
              })()}
            </Toolbar>
          </Box>
        </Container>
      </AppBar>

      {/* Main Content */}
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Card elevation={3} sx={{ maxWidth: 1000, mx: 'auto' }}>
          <CardContent sx={{ p: 4 }}>

            {/* Loading State */}
            {isLoading ? (
              <Paper elevation={2} sx={{ p: 4, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 300, width: 800 }}>
                <CircularProgress size={48} sx={{ mb: 2 }} />
                <Typography variant="h6" color="text.secondary">
                  {isQuizMode ? 'Generating USMLE questions ...' : 'Generating flashcards ...'}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                  {formatTimer(generationTimer)}
                </Typography>
              </Paper>
            ) : error ? (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Alert 
                  severity={error === "Quiz set for that material already exists. Here it is!" ? "info" : "error"} 
                  sx={{ 
                    borderRadius: 2,
                    flexGrow: 1
                  }}
                >
                  {error}
                </Alert>
                {error === "Quiz set for that material already exists. Here it is!" && contentHash && (
                  <Button
                    variant="contained"
                    color={isQuizMode ? "primary" : "success"}
                    onClick={async () => {
                      try {
                        setIsLoading(true);
                        const response = await axios.post('/api/load-study-set', 
                          { content_hash: contentHash }, 
                          { withCredentials: true }
                        );
                        if (response.data.success) {
                          setSummary(response.data.summary || '');
                          const quizResponse = await axios.get('/api/get-quiz', { withCredentials: true });
                          if (quizResponse.data.success) {
                            setQuestions(quizResponse.data.questions);
                            setError('');
                          }
                        }
                      } catch (err) {
                        setError(err.response?.data?.error || 'Failed to load existing set');
                      } finally {
                        setIsLoading(false);
                      }
                    }}
                    sx={{ flexShrink: 0 }}
                  >
                    Load Existing Set
                  </Button>
                )}
              </Box>
            ) : (
              <Box>
                {/* Results Screen */}
                {showResults ? (
                  <Box sx={{ py: 3 }}>
                    {/* Quiz Statistics */}
                    {(() => {

                      return (
                        <Box textAlign="center" mb={4}>
                          {isQuizMode && (
                            <>
                              <Typography variant="h5" fontWeight="600" gutterBottom sx={{ mb: 2 }}>
                                Quiz Performance
                              </Typography>
                              
                              {!allQuestionsAnswered && !isQuizMode ? (
                                <Alert severity="warning" sx={{ mb: 3, borderRadius: 2 }}>
                                  You haven't answered all questions yet. Your current score is based on the questions you've completed.
                                </Alert>
                              ) : (
                                <Paper elevation={1} sx={{ display: 'inline-block', p: 4, mb: 3, borderRadius: 3 }}>
                                  <Box display="flex" alignItems="center" justifyContent="center">
                                    <Box position="relative" display="inline-flex">
                                      <CircularProgress variant="determinate" value={100} size={120} thickness={4} sx={{ color: 'grey.300' }} />
                                      <CircularProgress
                                        variant="determinate"
                                        value={stats.percentage}
                                        size={120}
                                        thickness={4}
                                        sx={{
                                          color: stats.percentage >= 70 ? 'success.main' :
                                                stats.percentage >= 40 ? 'warning.main' : 'error.main',
                                          position: 'absolute',
                                          left: 0,
                                        }}
                                      />
                                      <Box sx={{ top: 0, left: 0, bottom: 0, right: 0, position: 'absolute', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                        <Typography variant="h4" component="div" fontWeight="bold">
                                          {stats.percentage}%
                                        </Typography>
                                      </Box>
                                    </Box>
                                  </Box>
                                  <Typography variant="body1" color="text.secondary" mt={2}>
                                    {stats.correct} correct out of {stats.total} questions
                                  </Typography>
                                </Paper>
                              )}
                            </>
                          )}
                          
                          {/* Action Buttons */}
                          <Stack direction="row" spacing={2} justifyContent="center">
                            <Button
                              onClick={resetQuiz}
                              variant="contained"
                              startIcon={<Refresh />}
                              disabled={isGeneratingMoreQuestions}
                              color={isQuizMode ? "primary" : "success"}
                            >
                              Try Again / Generate More
                            </Button>
                          </Stack>
                        </Box>
                      );
                    })()}
                    
                    {/* Current Quiz Results */}
                      <Box>
                        <Typography variant="h3" fontWeight="600" gutterBottom>
                          {isQuizMode ? 'USMLE Set Review' : 'Flashcard Set Review'}
                        </Typography>
                        <Stack spacing={3}>
                          {stats.questionsWithStatus.map((question, index) => (
                            <Card 
                              key={question.id} 
                              elevation={1}
                              sx={{
                                border: '1px solid',
                                borderColor: isQuizMode 
                                  ? (question.isAnswered 
                                      ? (question.isCorrect ? 'success.main' : 'error.main')
                                      : 'divider')
                                  : 'divider'
                              }}
                            >
                              <CardContent>
                                <Box display="flex" alignItems="flex-start" mb={2}>
                                  {isQuizMode && (
                                    <Chip
                                      icon={question.isAnswered
                                        ? (question.isCorrect ? <CheckCircle /> : <Cancel />)
                                        : <HelpOutline />
                                      }
                                      label={question.isAnswered
                                        ? (question.isCorrect ? 'Correct' : 'Incorrect')
                                        : 'Unanswered'
                                      }
                                      color={question.isAnswered
                                        ? (question.isCorrect ? 'success' : 'error')
                                        : 'default'
                                    }
                                      size="small"
                                      sx={{ mr: 2 }}
                                    />
                                  )}
                                  <Typography variant="body1" fontWeight="500" sx={{ flexGrow: 1 }}>
                                    #{index + 1}: {question.text}
                                  </Typography>
                                  <Button 
                                    onClick={() => handleToggleStar(question.id)}
                                    sx={{
                                      minWidth: 'auto', 
                                      p: 0, 
                                      '&:hover': { bgcolor: 'transparent' }
                                    }}
                                  >
                                    {question.starred ? <Star color="warning" /> : <StarBorder color="warning" />}
                                  </Button>
                                </Box>
                              
                                <Box ml={2}>
                                  {isQuizMode ? (
                                    <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 2 }}>
                                      {question.options.map((option, index) => {
                                        const questionId = question.id;
                                        const isSelected = selectedAnswers[questionId] === index;
                                        const isSubmitted = submittedAnswers[questionId];
                                        const correctAnswer = question.correctAnswer;
                                        const isCorrect = isSelected && index === correctAnswer;
                                        const isIncorrect = isSelected && index !== correctAnswer;
                                        const isCorrectAnswer = index === correctAnswer;
                                        const wasAnswered = isSubmitted;
                                        const isUserAnswer = isSelected;

                                        return (
                                          <Paper
                                            key={index}
                                            elevation={0}
                                            onClick={() => handleAnswerSelect(questionId, index)}
                                            sx={{
                                              p: 2,
                                              minHeight: '40px',
                                              display: 'flex',
                                              alignItems: 'center',
                                              border: '2px solid',
                                              borderColor: isSubmitted 
                                                ? (isCorrect
                                                    ? 'success.main'
                                                    : isIncorrect
                                                      ? 'error.main'
                                                      : isCorrectAnswer
                                                        ? 'success.main'
                                                        : 'divider')
                                                : (isSelected
                                                    ? 'primary.main'
                                                    : 'divider'),
                                              bgcolor: isSubmitted
                                                ? (isCorrect || isCorrectAnswer ? alpha('#4caf50', 0.1) : isIncorrect ? alpha('#f44336', 0.1) : 'transparent')
                                                : 'transparent',
                                              cursor: isSubmitted ? 'default' : 'pointer',
                                              transition: 'all 0.2s ease',
                                              '&:hover': isSubmitted ? {} : {
                                                borderColor: 'primary.main',
                                                bgcolor: alpha('#1976d2', 0.05)
                                              }
                                            }}
                                          >
                                            <Stack direction="column" spacing={1}>
                                              {isCorrectAnswer && (
                                                <Chip label="Correct answer" color="success" size="small" sx={{ minWidth: 120, maxWidth: 120 }} />
                                              )}
                                              {wasAnswered && isUserAnswer && !isCorrectAnswer && (
                                                <Chip label="Your answer" color="error" size="small" sx={{ minWidth: 120, maxWidth: 120 }} />
                                              )}
                                              <Box display="flex" alignItems="flex-start" gap={1}>
                                                <Box component="span" fontWeight="600">
                                                  {String.fromCharCode(65 + index)}.
                                                </Box>
                                                <Typography variant="body2" sx={{ textAlign: 'left' }}>
                                                  {cleanOptionText(option)}
                                                </Typography>
                                              </Box>
                                            </Stack>
                                          </Paper>
                                        );
                                      })}
                                    </Box>
                                  ) : (
                                    <Box>
                                      <Typography variant="h6" color="success" gutterBottom>
                                        Answer:
                                      </Typography>
                                      <Typography variant="body1" sx={{ mb: 2 }}>
                                        {cleanOptionText(question.options[question.correctAnswer])}
                                      </Typography>
                                    </Box>
                                  )}
                                  
                                  <Box sx={{ mt: 3 }}>
                                    <Typography variant="h6" color={isQuizMode ? "primary" : "success"} gutterBottom>
                                      Explanation:
                                    </Typography>
                                    <Typography variant="body1" color="text.primary">
                                      {question.reason}
                                    </Typography>
                                  </Box>
                                </Box>
                              </CardContent>
                            </Card>
                          ))}
                        </Stack>
                      </Box>
                  </Box>
                ) : isPreviewing ? (
                  <Box>
                    {/* First Row of Buttons */}
                    <Box display="flex" justifyContent="center" gap={2} mb={2}>
                      <Button
                        onClick={generateAdditionalQuestions}
                        variant="outlined"
                        color={isQuizMode ? "primary" : "success"}
                        size="large"
                        startIcon={isGeneratingMoreQuestions ? <CircularProgress size={24} color="inherit" /> : <Add />}
                        disabled={isGeneratingMoreQuestions}
                        sx={{ 
                          display: 'flex',
                          alignItems: 'center',
                          gap: 1,
                          px: 2
                        }}
                      >
                        {isGeneratingMoreQuestions ? (
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <span>Generating...</span>
                            <Typography variant="body2" color="text.secondary">
                              {formatTimer(generationTimer)}
                            </Typography>
                          </Box>
                        ) : 'Generate More'}
                        <TextField
                          type="number"
                          value={numAdditionalQuestions}
                          onChange={(e) => {
                            e.stopPropagation();
                            setNumAdditionalQuestions(Math.max(1, Math.min(20, parseInt(e.target.value) || 1)));
                          }}
                          onClick={(e) => e.stopPropagation()}
                          disabled={isGeneratingMoreQuestions}
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
                              backgroundColor: 'rgba(25, 118, 210, 0.15)',
                              border: '1px solid rgba(25, 118, 210, 0.3)',
                              borderRadius: '4px',
                              '&:hover': {
                                backgroundColor: 'rgba(25, 118, 210, 0.25)',
                              },
                              '&.Mui-focused': {
                                backgroundColor: 'rgba(25, 118, 210, 0.3)',
                                border: '1px solid rgba(25, 118, 210, 0.5)',
                              }
                            },
                            '& .MuiInputBase-input': {
                              color: (theme) => theme.palette.mode === 'dark' ? 'white' : 'primary.main',
                              padding: '2px 4px',
                              '&::placeholder': {
                                color: 'rgba(25, 118, 210, 0.7)',
                              }
                            },
                            '& .MuiOutlinedInput-notchedOutline': {
                              border: 'none'
                            }
                          }}
                        />
                      </Button>
                      <Button
                        onClick={handleStartQuiz}
                        variant="contained"
                        color={isQuizMode ? "primary" : "success"}
                        size="large"
                        startIcon={<ArrowForward />}
                        disabled={isGeneratingMoreQuestions}
                      >
                        Start Quiz
                      </Button>
                      <Button
                        onClick={handleStartStarredQuiz}
                        variant="contained"
                        color="warning"
                        size="large"
                        startIcon={<Star />}
                        disabled={starredQuestionsCount === 0 || isGeneratingMoreQuestions}
                      >
                        Start Quiz ({starredQuestionsCount})
                      </Button>
                    </Box>

                    {/* Second Row of Buttons */}
                    <Box display="flex" justifyContent="center" gap={2} mb={4}>
                      <Button
                        onClick={() => setShowAnswersInPreview(prev => !prev)}
                        variant="outlined"
                        color={isQuizMode ? "primary" : "success"}
                        size="large"
                        startIcon={showAnswersInPreview ? <HelpOutline /> : <CheckCircle />}
                      >
                        {showAnswersInPreview ? 'Hide Answers' : 'Show Answers'}
                      </Button>
                      <Button
                        onClick={shuffleQuestions}
                        variant="outlined"
                        color={isQuizMode ? "primary" : "success"}
                        size="large"
                        startIcon={<ShuffleIcon />}
                        disabled={questions.length < 2 || isGeneratingMoreQuestions}
                      >
                        Shuffle
                      </Button>
                      <Button
                        onClick={handleStarAllQuestions}
                        variant="outlined"
                        color="warning"
                        size="large"
                        startIcon={<Star />}
                        disabled={isGeneratingMoreQuestions}
                      >
                        All
                      </Button>
                      <Button
                        onClick={handleUnstarAllQuestions}
                        variant="outlined"
                        color="warning"
                        size="large"
                        startIcon={<StarBorder />}
                        disabled={isGeneratingMoreQuestions}
                      >
                        All
                      </Button>
                    </Box>

                    
                    {currentSessionShortSummary && (
                      <Typography variant="h2" color="text.primary" sx={{ textAlign: 'center', mb: 0 }}>
                        {currentSessionShortSummary}
                      </Typography>
                    )}
                    {currentSessionSources.length > 0 && (
                      <Typography variant="body1" color="text.secondary" sx={{ textAlign: 'center', mb: 2 }}>
                        {currentSessionSources.map((source, index) => (
                          <div key={index}>{source}</div>
                        ))}
                      </Typography>
                    )}
                    <Typography variant="h2" component="h3" fontWeight="600" mb={2}>
                      Questions in this {isQuizMode ? 'USMLE' : 'Flashcard'} Set ({questions.length})
                    </Typography>
                    <Stack spacing={2} mb={4}>
                      {questions.map((question, index) => (
                        <Paper 
                          key={question.id} 
                          elevation={1} 
                          sx={{
                            p: 2,
                            bgcolor: 'action.hover',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: 1
                          }}
                        >
                          <Box sx={{ display: 'flex', alignItems: 'center', flexGrow: 1, gap: 2 }}>
                            <Typography variant="body1" fontWeight="bold" sx={{ flexShrink: 0 }}>
                              {index + 1}.
                            </Typography>
                            <Box sx={{ flexGrow: 1 }}>
                              <Typography variant="body1" sx={{ textAlign: 'left' }}>
                                {question.text}
                              </Typography>
                              {showAnswersInPreview && ( // Conditionally render the answer
                                <Typography variant="body2" color="warning" sx={{ textAlign: 'left', mt: 1 }}>
                                  {cleanOptionText(question.options[question.correctAnswer])}
                                </Typography>
                              )}
                            </Box>
                          </Box>
                          <Button 
                            onClick={() => handleToggleStar(question.id)}
                            sx={{
                              minWidth: 'auto', 
                              p: 0, 
                              '&:hover': { bgcolor: 'transparent' },
                            }}
                          >
                            {question.starred ? <Star color="warning" /> : <StarBorder color="warning" />}
                          </Button>
                        </Paper>
                      ))}
                    </Stack>

                    <Paper elevation={1} sx={{ p: 3, bgcolor: 'background.paper' }}>
                      <Typography variant="h2" component="h3" fontWeight="600" gutterBottom>
                        Content Summary
                      </Typography>
                      <Box sx={{ 
                        textAlign: 'left',
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
                      }}>
                        <ReactMarkdown 
                          remarkPlugins={[remarkGfm]}
                          components={{
                            h1: ({...props}) => <Typography variant="h1" {...props} />,
                            h2: ({...props}) => <Typography variant="h2" {...props} />,
                            h3: ({...props}) => <Typography variant="h3" {...props} />,
                            p: ({...props}) => <Typography variant="body1" paragraph {...props} />,
                            a: ({...props}) => <Link {...props} />,
                          }}
                        >
                          {propSummary}
                        </ReactMarkdown>
                      </Box>
                    </Paper>
                  </Box>
                ) : (
                  /* Quiz Taking Interface */
                  <Box>
                    {/* Progress Bar */}
                    {questions.length > 0 && (
                      <Box mb={4}>
                        <Typography variant="body2" color="text.secondary" gutterBottom>
                          Question {currentQuestion + 1} of {questions.length}
                        </Typography>
                        <LinearProgress 
                          variant="determinate" 
                          value={((currentQuestion + 1) / questions.length) * 100}
                          color={isQuizMode ? "primary" : "success"}
                          sx={{ borderRadius: 1, height: 8 }}
                        />
                      </Box>
                    )}

                    {/* Current Question */}
                    {questions.length > 0 && (
                      <Box>
                        <Card elevation={2} sx={{ mb: 4 }}>
                          <CardContent sx={{ p: 4, position: 'relative' }}>
                            <Button 
                              onClick={() => handleToggleStar(questions[currentQuestion].id)}
                              sx={{
                                position: 'absolute',
                                top: 16,
                                right: 16,
                                minWidth: 'auto', 
                                p: 0,
                                zIndex: 1,
                                '&:hover': { bgcolor: 'transparent' }
                              }}
                            >
                              {questions[currentQuestion].starred ? <Star color="warning" /> : <StarBorder color="warning" />}
                            </Button>
                            <Typography variant="h5" fontWeight="500" gutterBottom>
                              {questions[currentQuestion].text}
                            </Typography>
                            
                            {!isPreviewing && !showResults && (
                              <Typography variant="body2" color="text.secondary" sx={{ mt: 2, mb: 3 }}>
                                Keyboard shortcuts: {isQuizMode ? (
                                  <>
                                    Use <strong>1-4</strong> to select answers, <strong>Enter</strong> to submit,{' '}
                                    <strong>←/→</strong> for navigation, <strong>s</strong> to star/unstar
                                  </>
                                ) : (
                                  <>
                                    Press <strong>Space</strong> to flip card, <strong>←/→</strong> for navigation, <strong>s</strong> to star/unstar
                                  </>
                                )}
                              </Typography>
                            )}
                            
                            {isQuizMode ? (
                              <FormControl component="fieldset" sx={{ width: '100%', mt: 3 }}>
                                <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 2 }}>
                                  {questions[currentQuestion].options.map((option, index) => {
                                    const questionId = questions[currentQuestion].id;
                                    const isSelected = selectedAnswers[questionId] === index;
                                    const isSubmitted = submittedAnswers[questionId];
                                    const correctAnswer = questions[currentQuestion].correctAnswer;
                                    const isCorrect = isSelected && index === correctAnswer;
                                    const isIncorrect = isSelected && index !== correctAnswer;
                                    const isCorrectAnswer = index === correctAnswer;

                                    return (
                                      <Paper
                                        key={index}
                                        elevation={0}
                                        onClick={() => handleAnswerSelect(questionId, index)}
                                        sx={{
                                          p: 2,
                                          minHeight: '40px',
                                          display: 'flex',
                                          alignItems: 'center',
                                          border: '2px solid',
                                          borderColor: isSubmitted 
                                            ? (isCorrect
                                                ? 'success.main'
                                                : isIncorrect
                                                  ? 'error.main'
                                                  : isCorrectAnswer
                                                    ? 'success.main'
                                                    : 'divider')
                                            : (isSelected
                                                ? 'primary.main'
                                                : 'divider'),
                                          bgcolor: isSubmitted
                                            ? (isCorrect || isCorrectAnswer ? alpha('#4caf50', 0.1) : isIncorrect ? alpha('#f44336', 0.1) : 'transparent')
                                            : 'transparent',
                                          cursor: isSubmitted ? 'default' : 'pointer',
                                          transition: 'all 0.2s ease',
                                          '&:hover': isSubmitted ? {} : {
                                            borderColor: 'primary.main',
                                            bgcolor: alpha('#1976d2', 0.05)
                                          }
                                        }}
                                      >
                                        <Box display="flex" alignItems="center">
                                          <Box
                                            sx={{
                                              width: 24,
                                              height: 24,
                                              minWidth: 24,
                                              minHeight: 24,
                                              borderRadius: '50%',
                                              border: '2px solid',
                                              borderColor: isSubmitted 
                                                ? (isCorrect
                                                    ? 'success.main'
                                                    : isIncorrect
                                                      ? 'error.main'
                                                      : isCorrectAnswer
                                                        ? 'success.main'
                                                        : 'divider')
                                                : (isSelected
                                                    ? 'primary.main'
                                                    : 'divider'),
                                              bgcolor: isSubmitted
                                                  ? (isCorrect || isCorrectAnswer ? 'success.main' : isIncorrect ? 'error.main' : 'transparent')
                                                  : 'transparent',
                                              display: 'flex',
                                              alignItems: 'center',
                                              justifyContent: 'center',
                                              flexShrink: 0,
                                              mr: 2
                                            }}
                                          >
                                            {(isSelected && !isSubmitted) || isCorrect || (isCorrectAnswer && isSubmitted) ? (
                                              <Check sx={{ fontSize: 16, color: isSubmitted ? 'white' : 'primary.main' }} />
                                            ) : isIncorrect ? (
                                              <Close sx={{ fontSize: 16, color: 'white' }} />
                                            ) : null}
                                          </Box>
                                          <Typography
                                            variant="body1"
                                            color={isSubmitted
                                              ? (isCorrect || isCorrectAnswer ? 'success.dark' : isIncorrect ? 'error.dark' : 'text.primary')
                                              : (isSelected ? 'primary.dark' : 'text.primary')
                                            }
                                            sx={{ textAlign: 'left' }}
                                          >
                                            <Box display="flex" alignItems="flex-start" gap={1}>
                                              <Box component="span" fontWeight="600">
                                                {String.fromCharCode(65 + index)}.
                                              </Box>
                                              {cleanOptionText(option)}
                                            </Box>
                                          </Typography>
                                        </Box>
                                      </Paper>
                                    );
                                  })}
                                </Box>
                              </FormControl>
                            ) : (
                              <Box 
                                onClick={() => setIsCardFlipped(!isCardFlipped)}
                                sx={{ 
                                  mt: 4, 
                                  textAlign: 'center',
                                  cursor: 'pointer',
                                  minHeight: '200px',
                                  display: 'flex',
                                  flexDirection: 'column',
                                  justifyContent: 'center',
                                  alignItems: 'center',
                                  border: '2px dashed',
                                  borderColor: 'divider',
                                  borderRadius: 2,
                                  transition: 'all 0.2s ease',
                                  '&:hover': {
                                    bgcolor: 'action.hover',
                                    borderColor: isQuizMode ? 'primary.main' : 'success.main'
                                  }
                                }}
                              >
                                {!isCardFlipped ? (
                                  <Typography variant="body1" color="text.secondary">
                                    Click to reveal the answer
                                  </Typography>
                                ) : (
                                  <Box sx={{ p: 3 }}>
                                    <Typography variant="h4" sx={{ mb: 3 }}>
                                      {cleanOptionText(questions[currentQuestion].options[questions[currentQuestion].correctAnswer])}
                                    </Typography>
                                    <Typography variant="h6" color="secondary.main" gutterBottom>
                                      --------------------------------------
                                    </Typography>
                                    <Typography variant="body1">
                                      {questions[currentQuestion].reason}
                                    </Typography>
                                  </Box>
                                )}
                              </Box>
                            )}
                          </CardContent>
                        </Card>

                        {/* Navigation Buttons */}
                        <Box display="flex" justifyContent="space-between" mb={4}>
                          <Button
                            onClick={moveToPreviousQuestion}
                            disabled={currentQuestion === 0}
                            variant="outlined"
                            startIcon={<ArrowBack />}
                            color={isQuizMode ? "primary" : "success"}
                          >
                            Previous
                          </Button>
                          
                          {!submittedAnswers[questions[currentQuestion].id] ? (
                            <Stack direction="row" spacing={2}>
                              <Button
                                onClick={moveToNextQuestion}
                                variant="outlined"
                                startIcon={<ArrowForward />}
                                color={isQuizMode ? "primary" : "success"}
                              >
                                {isQuizMode ? 'Skip' : 'Next'}
                              </Button>
                              {isQuizMode && (
                                <Button
                                  onClick={() => handleSubmitAnswer(questions[currentQuestion].id)}
                                  disabled={selectedAnswers[questions[currentQuestion].id] === undefined}
                                  variant="contained"
                                  color="primary"
                                >
                                  Submit Answer
                                </Button>
                              )}
                            </Stack>
                          ) : (
                            currentQuestion >= questions.length - 1 ? (
                              <Button
                                onClick={completeQuiz}
                                variant="contained"
                                color="primary"
                                startIcon={<CheckCircle />}
                              >
                                Complete Quiz
                              </Button>
                            ) : (
                              <Button
                                onClick={moveToNextQuestion}
                                variant="contained"
                                color="primary"
                                endIcon={<ArrowForward />}
                              >
                                Next Question
                              </Button>
                            )
                          )}
                        </Box>

                        {/* Explanation after submission */}
                        <Collapse in={!!visibleExplanation && submittedAnswers[questions[currentQuestion].id]}>
                          {visibleExplanation && (
                            <Alert
                              severity={visibleExplanation.isCorrect ? 'success' : 'error'}
                              sx={{ 
                                mb: 2,
                                bgcolor: theme => theme.palette.mode === 'dark'
                                  ? (visibleExplanation.isCorrect 
                                      ? alpha(theme.palette.success.main, 0.2)
                                      : alpha(theme.palette.error.main, 0.2))
                                  : (visibleExplanation.isCorrect 
                                      ? 'success.light'
                                      : undefined),
                                '& .MuiAlert-icon': {
                                  color: theme => theme.palette.mode === 'dark' 
                                    ? (visibleExplanation.isCorrect 
                                        ? 'success.light' 
                                        : 'error.light')
                                    : undefined
                                }
                              }}
                              icon={visibleExplanation.isCorrect ? <CheckCircle /> : <Cancel />}
                            >
                              <Typography variant="h6" gutterBottom sx={{ textAlign: 'left' }}>
                                {visibleExplanation.isCorrect ? 'Correct!' : 'Incorrect!'}
                              </Typography>
                              <Typography variant="body1" color="text.primary" sx={{ textAlign: 'left' }}>
                                {visibleExplanation.reason}
                              </Typography>
                            </Alert>
                          )}
                        </Collapse>
                      </Box>
                    )}
                  </Box>
                )}
              </Box>
            )}
          </CardContent>
        </Card>
      </Container>
      <FeedbackButton />
    </Box>
  );
};

export default Quiz; 