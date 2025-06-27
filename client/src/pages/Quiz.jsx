import React, { useState, useEffect, useRef } from 'react';
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
  Stack,
  Paper,
  Radio,
  RadioGroup,
  FormControlLabel,
  FormControl,
  Chip,
  CircularProgress,
  Divider,
  IconButton,
  Collapse
} from '@mui/material';
import {
  ArrowBack,
  ArrowForward,
  Check,
  Close,
  Refresh,
  Add,
  History,
  Dashboard as DashboardIcon,
  Logout,
  CheckCircle,
  Cancel,
  HelpOutline
} from '@mui/icons-material';
import ThemeToggle from '../components/ThemeToggle';

const Quiz = ({ user, summary: propSummary, setIsAuthenticated }) => {
  const navigate = useNavigate();
  const [questions, setQuestions] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState({});
  const [submittedAnswers, setSubmittedAnswers] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [showResults, setShowResults] = useState(false);
  const [isGeneratingMoreQuestions, setIsGeneratingMoreQuestions] = useState(false);
  const [summary, setSummary] = useState(propSummary || '');
  const [showAllPreviousQuestions, setShowAllPreviousQuestions] = useState(false);
  const [allPreviousQuestions, setAllPreviousQuestions] = useState([]);
  const [isLoadingPreviousQuestions, setIsLoadingPreviousQuestions] = useState(false);
  const [visibleExplanation, setVisibleExplanation] = useState(null);

  // Use refs to prevent duplicate calls
  const hasFetchedQuiz = useRef(false);
  const currentSummary = useRef('');
  const isFetching = useRef(false);

  // Helper function to clean option text and remove existing A), B), C), D) prefixes
  const cleanOptionText = (option) => {
    // Remove patterns like "A) ", "B. ", "C) ", "D. ", etc.
    return option.replace(/^[A-D][.)]\s*/, '').trim();
  };

  // Check auth and fetch summary if needed
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const response = await axios.get('/api/auth/check', {
          withCredentials: true
        });
        
        if (response.data.authenticated) {
          // If we have summary from props, use it
          if (propSummary) {
            setSummary(propSummary);
          } 
          // Otherwise use summary from the auth check response
          else if (response.data.summary) {
            setSummary(response.data.summary);
          }
        } else {
          // If not authenticated, redirect to login
          setIsAuthenticated(false);
          navigate('/login');
        }
      } catch (err) {
        console.error('Auth check failed:', err);
        navigate('/login');
      }
    };

    if (!propSummary) {
      checkAuth();
    }
  }, [propSummary, navigate, setIsAuthenticated]);

  // Fetch questions from the API when the component mounts
  useEffect(() => {
    if (!summary) {
      setIsLoading(false);
      return;
    }
    
    // Don't start a new fetch if we already have questions for this summary or are currently fetching
    if ((hasFetchedQuiz.current && currentSummary.current === summary) || isFetching.current) {
      return;
    }

    const fetchQuiz = async () => {
      try {
        isFetching.current = true;
        setIsLoading(true);
        setError('');
        
        // First try to get existing questions
        const existingResponse = await axios.get('/api/get-quiz', {
          withCredentials: true
        });
        
        if (existingResponse.data.success && existingResponse.data.questions.length > 0) {
          setQuestions(existingResponse.data.questions);
          hasFetchedQuiz.current = true;
          currentSummary.current = summary;
          return;
        }
        
        // If no existing questions, generate new ones
        const response = await axios.get('/api/generate-quiz', {
          withCredentials: true
        });
        
        if (response.data.success && response.data.questions) {
          setQuestions(response.data.questions);
          hasFetchedQuiz.current = true;
          currentSummary.current = summary;
        } else {
          setError('Failed to generate quiz questions');
        }
      } catch (err) {
        console.error('Error fetching quiz questions:', err);
        setError(err.response?.data?.error || 'Failed to generate quiz questions');
        // Reset the flags on error so user can retry
        hasFetchedQuiz.current = false;
        currentSummary.current = '';
      } finally {
        setIsLoading(false);
        isFetching.current = false;
      }
    };

    fetchQuiz();
  }, [summary]);

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

  const moveToNextQuestion = () => {
    if (currentQuestion < questions.length - 1) {
      const nextQuestionIndex = currentQuestion + 1;
      const nextQuestion = questions[nextQuestionIndex];

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
  };

  const generateMoreQuestions = async () => {
    try {
      setIsGeneratingMoreQuestions(true);
      
      // Save current answers before generating new questions
      await saveUserAnswers();
      
      // Get the IDs of incorrectly answered questions
      const incorrectQuestionIds = questions
        .filter(q => selectedAnswers[q.id] !== undefined && selectedAnswers[q.id] !== q.correctAnswer)
        .map(q => q.id);
      
      const response = await axios.post('/api/generate-more-questions', {
        incorrectQuestionIds,
        previousQuestions: questions
      }, {
        withCredentials: true
      });
      
      if (response.data.success && response.data.questions) {
        setQuestions(response.data.questions);
        // Clear cached previous questions so they get refetched
        setAllPreviousQuestions([]);
        // Always show current quiz after generating new questions
        setShowAllPreviousQuestions(false);
        resetQuiz();
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

  const handleBack = () => {
    navigate('/dashboard');
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
    
    return {
      correct: correctAnswers.length,
      total: answeredQuestions.length,
      percentage: answeredQuestions.length > 0 
        ? Math.round((correctAnswers.length / answeredQuestions.length) * 100) 
        : 0,
      questionsWithStatus
    };
  };
  
  // Check if all questions have been answered
  const allQuestionsAnswered = questions.length > 0 && 
    questions.every(question => submittedAnswers[question.id]);

  const stats = calculateStats();

  // Combine the functions to complete the quiz and show results
  const completeQuiz = async () => {
    // Save answers before showing results
    await saveUserAnswers();
    setShowResults(true);
    setShowAllPreviousQuestions(false);
  };

  // Function to fetch all previous questions
  const fetchAllPreviousQuestions = async () => {
    try {
      setIsLoadingPreviousQuestions(true);
      setError('');
      
      const response = await axios.get('/api/get-all-quiz-questions', {
        withCredentials: true
      });
      
      if (response.data.success && response.data.questions) {
        setAllPreviousQuestions(response.data.questions);
        setShowAllPreviousQuestions(true);
      } else {
        setError('Failed to retrieve previous questions');
      }
    } catch (err) {
      console.error('Error fetching previous questions:', err);
      setError(err.response?.data?.error || 'Failed to retrieve previous questions');
    } finally {
      setIsLoadingPreviousQuestions(false);
    }
  };

  // Function to toggle view between results and all previous questions
  const togglePreviousQuestions = async () => {
    if (!showAllPreviousQuestions) {
      // Save current answers before switching to previous questions view
      await saveUserAnswers();
      
      if (allPreviousQuestions.length === 0) {
      await fetchAllPreviousQuestions();
      } else {
        setShowAllPreviousQuestions(true);
      }
    } else {
      setShowAllPreviousQuestions(false);
    }
  };

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

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      {/* App Bar */}
      <AppBar position="static" color="default" elevation={1}>
        <Container maxWidth="xl">
          <Box sx={{ maxWidth: '100%', mx: 'auto', textAlign: 'left' }}>
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
          </Box>
        </Container>
      </AppBar>

      {/* Main Content */}
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Card elevation={3} sx={{ maxWidth: 1000, mx: 'auto' }}>
          <CardContent sx={{ p: 4 }}>
            {/* Header */}
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
              <Typography 
                variant="h4" 
                component="h2" 
                fontWeight="bold"
                color="text.primary"
              >
                {showResults ? "Quiz Results" : "Quiz Questions"}
              </Typography>
              <Button
                onClick={handleBack}
                variant="outlined"
                startIcon={<DashboardIcon />}
                size="small"
              >
                Back to Dashboard
              </Button>
            </Box>

            {/* Loading State */}
            {isLoading ? (
              <Paper elevation={2} sx={{ p: 4, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 300, width: 800 }}>
                <CircularProgress size={48} sx={{ mb: 2 }} />
                <Typography variant="h6" color="text.secondary">
                  Generating quiz questions...
                </Typography>
              </Paper>
            ) : error ? (
              <Alert severity="error" sx={{ borderRadius: 2 }}>
                {error}
              </Alert>
            ) : (
              <Box>
                {/* Results Screen */}
                {showResults ? (
                  <Box sx={{ py: 3 }}>
                    {/* Quiz Statistics */}
                    <Box textAlign="center" mb={4}>
                      <Typography variant="h5" fontWeight="600" gutterBottom>
                        Quiz Complete!
                      </Typography>
                      
                      {allQuestionsAnswered ? (
                        <Paper elevation={1} sx={{ display: 'inline-block', p: 4, mb: 3, borderRadius: 3 }}>
                          <Box display="flex" alignItems="center" justifyContent="center">
                            <Box position="relative" display="inline-flex">
                              <CircularProgress
                                variant="determinate"
                                value={100}
                                size={120}
                                thickness={4}
                                sx={{ color: 'grey.300' }}
                              />
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
                              <Box
                                sx={{
                                  top: 0,
                                  left: 0,
                                  bottom: 0,
                                  right: 0,
                                  position: 'absolute',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                }}
                              >
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
                      ) : (
                        <Alert severity="warning" sx={{ mb: 3, borderRadius: 2 }}>
                          You haven't answered all questions yet. Your current score is based on the questions you've completed.
                        </Alert>
                      )}
                      
                      {/* Action Buttons */}
                      <Stack direction="row" spacing={2} justifyContent="center">
                        <Button
                          onClick={resetQuiz}
                          variant="outlined"
                          startIcon={<Refresh />}
                        >
                          Try Again
                        </Button>
                        <Button
                          onClick={generateMoreQuestions}
                          disabled={isGeneratingMoreQuestions}
                          variant="outlined"
                          color="secondary"
                          startIcon={isGeneratingMoreQuestions ? <CircularProgress size={16} color="inherit" /> : <Add />}
                        >
                          {isGeneratingMoreQuestions ? 'Generating...' : 'Generate New Questions'}
                        </Button>
                        <Button
                          onClick={togglePreviousQuestions}
                          disabled={isLoadingPreviousQuestions}
                          variant="outlined"
                          startIcon={isLoadingPreviousQuestions ? <CircularProgress size={16} color="inherit" /> : <History />}
                        >
                          {isLoadingPreviousQuestions 
                            ? 'Loading...' 
                            : showAllPreviousQuestions 
                              ? 'Show Current Quiz' 
                              : 'View All Previous Questions'
                          }
                        </Button>
                      </Stack>
                    </Box>

                    {/* Current Quiz Results */}
                    {!showAllPreviousQuestions && (
                      <Box>
                        <Typography variant="h3" fontWeight="600" gutterBottom>
                          Question Review
                        </Typography>
                        <Stack spacing={3}>
                          {stats.questionsWithStatus.map((question) => (
                            <Card 
                              key={question.id} 
                              elevation={1}
                              sx={{
                                border: '1px solid',
                                borderColor: question.isAnswered 
                                  ? (question.isCorrect ? 'success.main' : 'error.main')
                                  : 'divider'
                              }}
                            >
                              <CardContent>
                                <Box display="flex" alignItems="flex-start" mb={2}>
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
                                  <Typography variant="body1" fontWeight="500">
                                    {question.text}
                                  </Typography>
                                </Box>
                                
                                <Box ml={2}>
                                {question.options.map((option, index) => (
                                    <Paper
                                    key={index}
                                      elevation={0}
                                      onClick={() => handleAnswerSelect(question.id, index)}
                                      sx={{
                                        p: 2,
                                        mb: 1,
                                        border: '2px solid',
                                        borderColor: submittedAnswers[question.id] 
                                        ? (index === question.correctAnswer
                                              ? 'success.main' 
                                              : (selectedAnswers[question.id] === index && selectedAnswers[question.id] !== question.correctAnswer)
                                                ? 'error.main'
                                                : 'divider')
                                          : (selectedAnswers[question.id] === index ? 'primary.main' : 'divider'),
                                        bgcolor: submittedAnswers[question.id] 
                                          ? 'transparent'
                                          : (selectedAnswers[question.id] === index ? 'primary.light' : 'transparent'),
                                        cursor: submittedAnswers[question.id] ? 'default' : 'pointer',
                                        transition: 'all 0.2s ease',
                                        '&:hover': submittedAnswers[question.id] ? {} : {
                                          borderColor: 'primary.main',
                                          bgcolor: 'action.hover'
                                        }
                                      }}
                                    >
                                      <Typography
                                        variant="body2"
                                        color={submittedAnswers[question.id]
                                          ? (index === question.correctAnswer ? 'success.dark' : 'text.primary')
                                          : (selectedAnswers[question.id] === index ? 'primary.dark' : 'text.primary')
                                        }
                                      >
                                        <Box component="span" fontWeight="600" mr={1}>
                                          {String.fromCharCode(65 + index)}.
                                        </Box>
                                        {cleanOptionText(option)}
                                        {submittedAnswers[question.id] && index === question.correctAnswer && (
                                          <Chip label="Correct answer" color="success" size="small" sx={{ ml: 1 }} />
                                        )}
                                        {submittedAnswers[question.id] && selectedAnswers[question.id] === index && selectedAnswers[question.id] !== question.correctAnswer && (
                                          <Chip label="Your answer" color="error" size="small" sx={{ ml: 1 }} />
                                        )}
                                      </Typography>
                                    </Paper>
                                  ))}
                                  
                                  {submittedAnswers[question.id] && (
                                    <Paper elevation={0} sx={{ p: 2, mt: 2, bgcolor: 'action.hover' }}>
                                      <Typography variant="body2" color="text.primary">
                                        <Box component="span" fontWeight="600">Explanation:</Box> {question.reason}
                                      </Typography>
                                    </Paper>
                                  )}
                                </Box>
                              </CardContent>
                            </Card>
                          ))}
                        </Stack>
                      </Box>
                    )}

                    {/* All Previous Questions View */}
                    {showAllPreviousQuestions && (
                      <Box>
                        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                          <Typography variant="h6" fontWeight="600">
                            All Previous Questions
                          </Typography>
                          <Typography variant="h6" color="text.secondary">
                            Showing {allPreviousQuestions.length} quiz set{allPreviousQuestions.length !== 1 ? 's' : ''} from previous sessions
                          </Typography>
                        </Box>
                        
                        {allPreviousQuestions.length === 0 ? (
                          <Box textAlign="center" py={4}>
                            {isLoadingPreviousQuestions ? (
                              <Box display="flex" justifyContent="center" alignItems="center">
                                <CircularProgress size={32} sx={{ mr: 2 }} />
                                <Typography color="text.secondary">Loading previous questions...</Typography>
                              </Box>
                            ) : (
                              <Typography color="text.secondary">No previous questions found</Typography>
                            )}
                          </Box>
                        ) : (
                          <Stack spacing={4}>
                            {allPreviousQuestions.map((questionSet, setIndex) => (
                              <Card key={setIndex} elevation={2}>
                                <CardContent>
                                  <Typography variant="h2" fontWeight="600" gutterBottom>
                                    Quiz Set #{setIndex + 1}
                                  </Typography>
                                  <Stack spacing={3}>
                                    {questionSet.map((question, qIndex) => {
                                      // Calculate if the question was answered correctly
                                      const wasAnsweredCorrectly = question.isAnswered && question.userAnswer === question.correctAnswer;
                                      
                                      return (
                                        <Paper 
                                          key={`${setIndex}-${qIndex}`} 
                                          elevation={0} 
                                          sx={{ 
                                            p: 3, 
                                            bgcolor: 'background.paper',
                                            border: '2px solid',
                                            borderColor: question.isAnswered 
                                              ? (wasAnsweredCorrectly ? 'success.main' : 'error.main')
                                              : 'divider'
                                          }}
                                        >
                                          <Box display="flex" alignItems="flex-start" mb={2}>
                                            <Chip
                                              icon={question.isAnswered
                                                ? (wasAnsweredCorrectly ? <CheckCircle /> : <Cancel />)
                                                : <HelpOutline />
                                              }
                                              label={question.isAnswered
                                                ? (wasAnsweredCorrectly ? 'Correct' : 'Incorrect')
                                                : 'Unanswered'
                                              }
                                              color={question.isAnswered
                                                ? (wasAnsweredCorrectly ? 'success' : 'error')
                                                : 'default'
                                              }
                                              size="small"
                                              sx={{ mr: 2 }}
                                            />
                                            <Typography variant="body1" fontWeight="500">
                                              Question {qIndex + 1}: {question.text}
                                            </Typography>
                                          </Box>
                                          <Box ml={2}>
                                            {question.options.map((option, optIndex) => {
                                              const isCorrectAnswer = optIndex === question.correctAnswer;
                                              const isUserAnswer = question.userAnswer === optIndex;
                                              const wasAnswered = question.isAnswered;
                                              
                                              return (
                                                <Paper
                                                  key={optIndex}
                                                  elevation={0}
                                                  sx={{
                                                    p: 2,
                                                    mb: 1,
                                                    bgcolor: 'transparent',
                                                    border: '2px solid',
                                                    borderColor: wasAnswered
                                                      ? (isCorrectAnswer
                                                          ? 'success.main'
                                                          : isUserAnswer
                                                            ? 'error.main'
                                                            : 'divider')
                                                      : isCorrectAnswer
                                                        ? 'success.main'
                                                        : 'divider'
                                                  }}
                                                >
                                                  <Typography variant="body2">
                                                    <Box component="span" fontWeight="600" mr={1}>
                                                      {String.fromCharCode(65 + optIndex)}.
                                                    </Box>
                                                    {cleanOptionText(option)}
                                                    {isCorrectAnswer && (
                                                      <Chip label="Correct answer" color="success" size="small" sx={{ ml: 1 }} />
                                                    )}
                                                    {wasAnswered && isUserAnswer && !isCorrectAnswer && (
                                                      <Chip label="Your answer" color="error" size="small" sx={{ ml: 1 }} />
                                                    )}
                                                  </Typography>
                                                </Paper>
                                              );
                                            })}
                                            <Paper elevation={0} sx={{ p: 2, mt: 2, bgcolor: 'action.hover' }}>
                                              <Typography variant="body2" color="text.primary">
                                                <Box component="span" fontWeight="600">Explanation:</Box> {question.reason}
                                              </Typography>
                                            </Paper>
                                          </Box>
                                        </Paper>
                                      );
                                    })}
                                  </Stack>
                                </CardContent>
                              </Card>
                            ))}
                          </Stack>
                        )}
                      </Box>
                    )}
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
                          sx={{ borderRadius: 1, height: 8 }}
                        />
                      </Box>
                    )}

                    {/* Current Question */}
                    {questions.length > 0 && (
                      <Box>
                        <Card elevation={2} sx={{ mb: 4 }}>
                          <CardContent sx={{ p: 4 }}>
                            <Typography variant="h5" fontWeight="500" gutterBottom>
                            {questions[currentQuestion].text}
                            </Typography>
                            
                            <FormControl component="fieldset" sx={{ width: '100%', mt: 3 }}>
                              <Stack spacing={2}>
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
                                        mb: 1,
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
                                        bgcolor: 'transparent',
                                        cursor: isSubmitted ? 'default' : 'pointer',
                                        transition: 'all 0.2s ease',
                                        '&:hover': isSubmitted ? {} : {
                                          borderColor: 'primary.main',
                                          bgcolor: 'action.hover'
                                        }
                                      }}
                                    >
                                      <Box display="flex" alignItems="center">
                                        <Box
                                          sx={{
                                            width: 24,
                                            height: 24,
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
                                              : (isSelected ? 'primary.main' : 'transparent'),
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            mr: 2
                                          }}
                                        >
                                          {(isSelected && !isSubmitted) || isCorrect || (isCorrectAnswer && isSubmitted) ? (
                                            <Check sx={{ fontSize: 16, color: 'white' }} />
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
                                        >
                                          <Box component="span" fontWeight="600" mr={1}>
                                            {String.fromCharCode(65 + index)}.
                                          </Box>
                                          {cleanOptionText(option)}
                                        </Typography>
                                      </Box>
                                    </Paper>
                              );
                            })}
                              </Stack>
                            </FormControl>
                          </CardContent>
                        </Card>

                        {/* Navigation Buttons */}
                        <Box display="flex" justifyContent="space-between" mb={4}>
                          <Button
                            onClick={moveToPreviousQuestion}
                            disabled={currentQuestion === 0}
                            variant="outlined"
                            startIcon={<ArrowBack />}
                          >
                            Previous
                          </Button>
                          
                          {!submittedAnswers[questions[currentQuestion].id] ? (
                            <Button
                              onClick={() => handleSubmitAnswer(questions[currentQuestion].id)}
                              disabled={selectedAnswers[questions[currentQuestion].id] === undefined}
                              variant="contained"
                              color="primary"
                            >
                              Submit Answer
                            </Button>
                          ) : (
                            currentQuestion >= questions.length - 1 ? (
                              <Button
                                onClick={completeQuiz}
                                variant="contained"
                                color="secondary"
                                startIcon={<CheckCircle />}
                              >
                                Complete Quiz
                              </Button>
                            ) : (
                              <Button
                                onClick={moveToNextQuestion}
                                variant="contained"
                                color="secondary"
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
                              sx={{ mb: 2 }}
                              icon={visibleExplanation.isCorrect ? <CheckCircle /> : <Cancel />}
                            >
                              <Typography variant="h6" gutterBottom>
                                {visibleExplanation.isCorrect ? 'Correct!' : 'Incorrect!'}
                              </Typography>
                              <Typography variant="body2">
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
    </Box>
  );
};

export default Quiz; 