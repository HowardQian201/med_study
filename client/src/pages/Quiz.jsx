import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

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
    // Record that this question has been answered
    setSubmittedAnswers({
      ...submittedAnswers,
      [questionId]: true
    });
    
    // Save answers to backend immediately (with small delay to ensure state updates)
    setTimeout(() => {
      saveUserAnswers();
    }, 100);
  };

  const isAnswerCorrect = (questionId) => {
    const question = questions.find(q => q.id === questionId);
    return selectedAnswers[questionId] === question.correctAnswer;
  };

  const moveToNextQuestion = () => {
    if (currentQuestion < questions.length - 1) {
      setCurrentQuestion(currentQuestion + 1);
    } else {
      // If on the last question, show results directly
      setShowResults(true);
    }
  };

  const moveToPreviousQuestion = () => {
    if (currentQuestion > 0) {
      setCurrentQuestion(currentQuestion - 1);
    }
  };

  const resetQuiz = () => {
    setSelectedAnswers({});
    setSubmittedAnswers({});
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
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <h1 className="text-xl font-semibold text-gray-900">Quiz</h1>
            </div>
            <div className="flex items-center space-x-4">
              <span className="text-gray-700">Welcome, {user?.name}</span>
              <button
                onClick={handleLogout}
                className="ml-4 px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-4xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="w-full p-8 bg-white rounded-xl shadow-lg">
            <div className="flex justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-800">
                {showResults ? "Quiz Results" : "Quiz Questions"}
              </h2>
              <button
                onClick={handleBack}
                className="px-4 py-2 text-sm font-medium text-indigo-600 border border-indigo-600 rounded hover:bg-indigo-50"
              >
                Back to Dashboard
              </button>
            </div>

            {isLoading ? (
              <div className="flex justify-center items-center h-64">
                <div className="text-gray-600">
                  <svg className="animate-spin -ml-1 mr-3 h-8 w-8 text-indigo-500 inline-block" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span className="text-lg">Generating quiz questions...</span>
                </div>
              </div>
            ) : error ? (
              <div className="text-red-500 text-center p-4 border border-red-200 rounded bg-red-50">
                {error}
              </div>
            ) : (
              <div>
                {/* Show results screen */}
                {showResults ? (
                  <div className="py-6">
                    <div className="mb-8 text-center">
                      <h3 className="text-2xl font-bold mb-4">Quiz Complete!</h3>
                      {allQuestionsAnswered ? (
                        <div className="inline-block bg-gray-100 rounded-lg px-8 py-6 mb-6">
                          <div className="flex items-center justify-center">
                            <div className="relative w-32 h-32">
                              <svg className="w-32 h-32 transform -rotate-90" viewBox="0 0 100 100">
                                <circle 
                                  className="text-gray-200" 
                                  strokeWidth="8" 
                                  stroke="currentColor" 
                                  fill="transparent" 
                                  r="40" 
                                  cx="50" 
                                  cy="50" 
                                />
                                <circle 
                                  className={`${stats.percentage >= 70 ? 'text-green-500' : stats.percentage >= 40 ? 'text-yellow-500' : 'text-red-500'}`}
                                  strokeWidth="8" 
                                  strokeDasharray={`${stats.percentage * 2.51} 251`}
                                  strokeLinecap="round" 
                                  stroke="currentColor" 
                                  fill="transparent" 
                                  r="40" 
                                  cx="50" 
                                  cy="50" 
                                />
                              </svg>
                              <div className="absolute inset-0 flex items-center justify-center">
                                <span className="text-3xl font-bold">{stats.percentage}%</span>
                              </div>
                            </div>
                          </div>
                          <p className="text-lg mt-2">{stats.correct} correct out of {stats.total} questions</p>
                        </div>
                      ) : (
                        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
                          <p className="text-yellow-800">You haven't answered all questions yet. Your current score is based on the questions you've completed.</p>
                        </div>
                      )}
                      
                      <div className="flex justify-center space-x-4 mt-4">
                        <button
                          onClick={resetQuiz}
                          className="px-5 py-2 font-medium text-indigo-600 border border-indigo-600 rounded hover:bg-indigo-50"
                        >
                          Try Again
                        </button>
                        <button
                          onClick={generateMoreQuestions}
                          disabled={isGeneratingMoreQuestions}
                          className={`px-5 py-2 font-medium text-white bg-green-600 rounded hover:bg-green-700 flex items-center ${isGeneratingMoreQuestions ? 'opacity-70 cursor-not-allowed' : ''}`}
                        >
                          {isGeneratingMoreQuestions && (
                            <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                          )}
                          Generate New Questions
                        </button>
                        <button
                          onClick={togglePreviousQuestions}
                          disabled={isLoadingPreviousQuestions}
                          className={`px-5 py-2 font-medium text-white bg-purple-600 rounded hover:bg-purple-700 flex items-center ${isLoadingPreviousQuestions ? 'opacity-70 cursor-not-allowed' : ''}`}
                        >
                          {isLoadingPreviousQuestions && (
                            <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                          )}
                          {showAllPreviousQuestions ? 'Show Current Quiz' : 'View All Previous Questions'}
                        </button>
                      </div>
                    </div>
                    
                    {/* Current quiz results view */}
                    {!showAllPreviousQuestions && (
                      <div className="mt-8">
                        <h4 className="text-xl font-semibold mb-4">Question Review</h4>
                        <div className="space-y-6">
                          {stats.questionsWithStatus.map((question) => (
                            <div 
                              key={question.id} 
                              className={`p-4 border rounded-lg ${
                                question.isAnswered 
                                  ? (question.isCorrect 
                                    ? 'border-green-200 bg-green-50' 
                                    : 'border-red-200 bg-red-50')
                                  : 'border-gray-200'
                              }`}
                            >
                              <div className="flex items-start mb-2">
                                <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full mr-2 mt-1 ${
                                  question.isAnswered
                                    ? (question.isCorrect 
                                      ? 'bg-green-500 text-white' 
                                      : 'bg-red-500 text-white')
                                    : 'bg-gray-300 text-white'
                                }`}>
                                  {question.isAnswered
                                    ? (question.isCorrect 
                                      ? '✓' 
                                      : '✗')
                                    : '?'
                                  }
                                </span>
                                <h5 className="text-lg font-medium">{question.text}</h5>
                              </div>
                              
                              <div className="ml-8 space-y-2">
                                {question.options.map((option, index) => (
                                  <div 
                                    key={index}
                                    className={`p-2 rounded ${
                                      question.isAnswered
                                        ? (index === question.correctAnswer
                                          ? 'bg-green-100 border-l-4 border-green-500' 
                                          : question.userAnswer === index
                                            ? 'bg-red-100 border-l-4 border-red-500'
                                            : 'text-gray-600')
                                        : question.userAnswer === index
                                          ? 'bg-indigo-50 border-l-4 border-indigo-500'
                                          : 'text-gray-600'
                                    }`}
                                  >
                                    <span className={`transition-colors duration-200 ${
                                      question.isAnswered
                                        ? (index === question.correctAnswer
                                          ? 'font-medium text-green-700'
                                          : question.userAnswer === index
                                            ? 'font-medium text-red-700'
                                            : 'text-gray-700')
                                        : 'text-gray-700'
                                    }`}>
                                      <span className="font-medium mr-2">{String.fromCharCode(65 + index)}. </span>
                                      {cleanOptionText(option)}
                                    </span>
                                    {question.isAnswered && index === question.correctAnswer && (
                                      <span className="ml-2 text-green-600 font-medium"> (Correct answer)</span>
                                    )}
                                    {question.isAnswered && question.userAnswer === index && question.userAnswer !== question.correctAnswer && (
                                      <span className="ml-2 text-red-600 font-medium"> (Your answer)</span>
                                    )}
                                  </div>
                                ))}
                                
                                {question.isAnswered && (
                                  <div className="mt-3 p-3 bg-gray-50 rounded border border-gray-200">
                                    <p className="text-gray-700"><span className="font-medium">Explanation:</span> {question.reason}</p>
                                  </div>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    {/* All previous questions view */}
                    {showAllPreviousQuestions && (
                      <div className="mt-8">
                        <div className="flex justify-between items-center mb-4">
                          <h4 className="text-xl font-semibold">All Previous Questions</h4>
                          <span className="text-sm text-gray-500">                            Showing {allPreviousQuestions.length} quiz set{allPreviousQuestions.length !== 1 ? 's' : ''} from previous sessions                          </span>
                        </div>
                        
                        {allPreviousQuestions.length === 0 ? (
                          <div className="text-center py-8 text-gray-500">
                            {isLoadingPreviousQuestions ? (
                              <div className="flex justify-center items-center">
                                <svg className="animate-spin h-8 w-8 text-indigo-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                                <span className="ml-2">Loading previous questions...</span>
                              </div>
                            ) : (
                              <p>No previous questions found</p>
                            )}
                          </div>
                        ) : (
                          <div className="space-y-6">
                            {allPreviousQuestions.map((questionSet, setIndex) => (
                              <div key={setIndex} className="border border-gray-200 rounded-lg p-4">
                                <h5 className="font-medium text-lg mb-3">Quiz Set #{setIndex + 1}</h5>
                                {questionSet.map((question, qIndex) => (
                                  <div key={`${setIndex}-${qIndex}`} className="mb-4 p-4 bg-gray-50 rounded-lg">
                                    <h6 className="font-medium text-gray-800 mb-2">
                                      Question {qIndex + 1}: {question.text}
                                    </h6>
                                    <div className="ml-4 space-y-2 mt-2">
                                      {question.options.map((option, optIndex) => {
                                        const isCorrectAnswer = optIndex === question.correctAnswer;
                                        const isUserAnswer = question.userAnswer === optIndex;
                                        const wasAnswered = question.isAnswered;
                                        
                                        return (
                                          <div 
                                            key={optIndex}
                                            className={`p-2 rounded ${
                                              wasAnswered
                                                ? (isCorrectAnswer
                                                    ? 'bg-green-100 border-l-4 border-green-500' 
                                                    : isUserAnswer
                                                      ? 'bg-red-100 border-l-4 border-red-500'
                                                      : 'text-gray-600')
                                                : (isCorrectAnswer
                                                    ? 'bg-green-100 border-l-4 border-green-500'
                                                    : 'text-gray-600')
                                            }`}
                                          >
                                            <span className="font-medium mr-2">{String.fromCharCode(65 + optIndex)}. </span>
                                            {cleanOptionText(option)}
                                            {isCorrectAnswer && (
                                              <span className="ml-2 text-green-600 font-medium"> (Correct answer)</span>
                                            )}
                                            {wasAnswered && isUserAnswer && !isCorrectAnswer && (
                                              <span className="ml-2 text-red-600 font-medium"> (Your answer)</span>
                                            )}
                                          </div>
                                        );
                                      })}
                                      <div className="mt-3 p-3 bg-gray-100 rounded border border-gray-200">
                                        <p className="text-gray-700"><span className="font-medium">Explanation:</span> {question.reason}</p>
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  <>
                    {questions.length > 0 && (
                      <div className="mb-6">
                        <div className="mb-2 text-sm font-medium text-gray-500">
                          Question {currentQuestion + 1} of {questions.length}
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div 
                            className="bg-indigo-600 h-2 rounded-full" 
                            style={{ width: `${((currentQuestion + 1) / questions.length) * 100}%` }}
                          />
                        </div>
                      </div>
                    )}

                    {questions.length > 0 && (
                      <div>
                        <div className="mb-6">
                          <h3 className="text-xl font-medium text-gray-800 mb-4">
                            {questions[currentQuestion].text}
                          </h3>
                          <div className="space-y-3">
                            {questions[currentQuestion].options.map((option, index) => {
                              const questionId = questions[currentQuestion].id;
                              const isSelected = selectedAnswers[questionId] === index;
                              const isSubmitted = submittedAnswers[questionId];
                              const correctAnswer = questions[currentQuestion].correctAnswer;
                              const isCorrect = isSelected && index === correctAnswer;
                              const isIncorrect = isSelected && index !== correctAnswer;
                              const isCorrectAnswer = index === correctAnswer;

                              return (
                                <div 
                                  key={index}
                                  onClick={() => handleAnswerSelect(questionId, index)}
                                  className={`p-4 border rounded-lg cursor-pointer transition-all duration-200 transform ${
                                    isSubmitted 
                                      ? (isCorrect
                                          ? 'border-green-500 bg-green-50 shadow-md scale-[1.02]'
                                          : isIncorrect
                                            ? 'border-red-500 bg-red-50 shadow-md scale-[1.02]'
                                            : isCorrectAnswer
                                              ? 'border-green-500 bg-green-50 opacity-70'
                                              : 'border-gray-200 opacity-70'
                                        )
                                      : (isSelected
                                          ? 'border-indigo-500 bg-indigo-100 shadow-md scale-[1.02]' 
                                          : 'border-gray-200 hover:border-indigo-300 hover:bg-gray-50 hover:scale-[1.01]'
                                        )
                                  }`}
                                >
                                  <div className="flex items-center">
                                    <div className={`w-6 h-6 rounded-full border flex items-center justify-center mr-3 transition-all duration-200 ${
                                      isSubmitted
                                        ? (isCorrect
                                            ? 'border-green-500 bg-green-500 text-white'
                                            : isIncorrect
                                              ? 'border-red-500 bg-red-500 text-white'
                                              : isCorrectAnswer
                                                ? 'border-green-500 bg-green-500 text-white opacity-70'
                                                : 'border-gray-300'
                                          )
                                        : (isSelected
                                            ? 'border-indigo-500 bg-indigo-500 text-white' 
                                            : 'border-gray-300'
                                          )
                                    }`}>
                                      {isSelected && !isSubmitted && (
                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                        </svg>
                                      )}
                                      {isCorrect && (
                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                        </svg>
                                      )}
                                      {isIncorrect && (
                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                                          <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                                        </svg>
                                      )}
                                      {isCorrectAnswer && isSubmitted && !isSelected && (
                                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                                          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                        </svg>
                                      )}
                                    </div>
                                    <span className={`transition-colors duration-200 ${
                                      isSubmitted
                                        ? (isCorrect
                                            ? 'font-medium text-green-700'
                                            : isIncorrect
                                              ? 'font-medium text-red-700'
                                              : isCorrectAnswer
                                                ? 'font-medium text-green-700 opacity-70'
                                                : 'text-gray-700 opacity-70'
                                          )
                                        : (isSelected
                                            ? 'font-medium text-indigo-700'
                                            : 'text-gray-700'
                                          )
                                    }`}>
                                      <span className="font-medium mr-2">{String.fromCharCode(65 + index)}. </span>
                                      {cleanOptionText(option)}
                                    </span>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>

                        {/* Explanation section that appears after submission */}
                        {submittedAnswers[questions[currentQuestion].id] && (
                          <div className={`mt-4 p-4 rounded-lg border ${
                            isAnswerCorrect(questions[currentQuestion].id) 
                              ? 'border-green-200 bg-green-50' 
                              : 'border-red-200 bg-red-50'
                          }`}>
                            <h4 className={`font-bold ${
                              isAnswerCorrect(questions[currentQuestion].id) 
                                ? 'text-green-700' 
                                : 'text-red-700'
                            }`}>
                              {isAnswerCorrect(questions[currentQuestion].id) 
                                ? 'Correct!' 
                                : 'Incorrect!'}
                            </h4>
                            <p className="mt-2">
                              {questions[currentQuestion].reason}
                            </p>
                          </div>
                        )}

                        <div className="flex justify-between mt-8">
                          <button
                            onClick={moveToPreviousQuestion}
                            disabled={currentQuestion === 0}
                            className={`px-4 py-2 border rounded ${
                              currentQuestion === 0 
                                ? 'border-gray-200 text-gray-400 cursor-not-allowed' 
                                : 'border-indigo-500 text-indigo-600 hover:bg-indigo-50'
                            }`}
                          >
                            Previous
                          </button>
                          
                          {!submittedAnswers[questions[currentQuestion].id] ? (
                            <button
                              onClick={() => handleSubmitAnswer(questions[currentQuestion].id)}
                              disabled={selectedAnswers[questions[currentQuestion].id] === undefined}
                              className={`px-4 py-2 rounded ${
                                selectedAnswers[questions[currentQuestion].id] === undefined
                                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed' 
                                  : 'bg-indigo-600 text-white hover:bg-indigo-700'
                              }`}
                            >
                              Submit Answer
                            </button>
                          ) : (
                            currentQuestion >= questions.length - 1 ? (
                              <button
                                onClick={completeQuiz}
                                className="px-4 py-2 rounded bg-green-600 text-white hover:bg-green-700"
                              >
                                Complete Quiz
                              </button>
                            ) : (
                              <button
                                onClick={moveToNextQuestion}
                                className="px-4 py-2 rounded bg-green-600 text-white hover:bg-green-700"
                              >
                                Next Question
                              </button>
                            )
                          )}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

export default Quiz; 