import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const Dashboard = ({ setIsAuthenticated, user, summary, setSummary }) => {
  const navigate = useNavigate();
  const [files, setFiles] = useState([]);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const [isUploading, setIsUploading] = useState(false);
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
    if (files.length === 0) {
      setError('Please select at least one file first');
      return;
    }
  
    try {
      console.log(`Uploading ${files.length} PDFs`);
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
        console.log("extraction success");
        // Update to handle the new response format (text instead of dictionary)
        setSummary(response.data.results);
      } else {
        setError('Text extraction failed');
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        setError('Upload cancelled');
        await cleanup(); // Cleanup on cancel
      } else if (err.response?.status === 401) {
        setError('Session expired. Please log in again.');
        await cleanup(); // Cleanup on session expiry
        setIsAuthenticated(false);
        navigate('/login');
      } else {
        setError(err.response?.data?.error || err.message);
        console.error('Upload failed:', err);
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
      
      const response = await axios.post('/api/regenerate-summary', {}, {
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
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <h1 className="text-xl font-semibold text-gray-900">Dashboard</h1>
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

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="w-full max-w-3xl mx-auto p-8 bg-white rounded-xl shadow-lg">
            <h2 className="text-2xl font-bold text-center mb-8 text-gray-800">
              PDF Text Extraction
            </h2>

            {/* File Selection Area */}
            <div className="space-y-6">
              <div className="flex flex-col items-center justify-center border-2 border-dashed border-gray-300 rounded-lg p-8 bg-gray-50 hover:bg-gray-100 transition-colors">
                <input
                  type="file"
                  accept="application/pdf"
                  onChange={handleFileSelect}
                  multiple
                  className="block w-full text-sm text-gray-500
                    file:mr-4 file:py-2 file:px-4
                    file:rounded-full file:border-0
                    file:text-sm file:font-semibold
                    file:bg-blue-50 file:text-blue-700
                    hover:file:bg-blue-100
                    cursor-pointer"
                />
                {files.length > 0 && (
                  <div className="mt-4 text-sm text-gray-600">
                    Selected: {files.length} file(s)
                    <ul className="mt-2 list-disc pl-5">
                      {files.map((file, index) => (
                        <li key={index}>{file.name}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Submit Button */}
              <div className="flex justify-center">
                <button
                  onClick={uploadPDFs}
                  disabled={files.length === 0 || isUploading}
                  className={`px-6 py-3 rounded-lg font-medium text-white 
                    ${files.length === 0 || isUploading 
                      ? 'bg-gray-400 cursor-not-allowed' 
                      : 'bg-blue-500 hover:bg-blue-600 transition-colors'
                    }`}
                >
                  {isUploading ? 'Extracting Text...' : 'Extract Text'}
                </button>
              </div>

              {/* Progress Bar */}
              {isUploading && (
                <div className="space-y-2">
                  <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
                    <div 
                      className="bg-blue-600 h-full rounded-full transition-all duration-300"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-sm text-gray-600">
                    <span>Upload {progress}% complete. Summarizing...</span>
                    <button 
                      onClick={cancelUpload}
                      className="text-red-500 hover:text-red-700"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {/* Error Message */}
              {error && (
                <div className="text-red-500 text-center text-sm">
                  {error}
                </div>
              )}

              {/* Results - Updated to show summary text */}
              {summary && (
                <div className="mt-8">
                  <div className="flex justify-between items-center mb-3">
                    <h3 className="text-lg font-semibold text-gray-800">
                      Summary:
                    </h3>
                    <div className="flex space-x-2">
                      <button
                        onClick={regenerateSummary}
                        disabled={isUploading}
                        className={`text-sm px-4 py-2 font-medium text-white bg-blue-600 rounded hover:bg-blue-700 flex items-center ${isUploading ? 'opacity-70 cursor-not-allowed' : ''}`}
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        {isUploading ? 'Regenerating...' : 'Regenerate Summary'}
                      </button>
                      <button
                        onClick={goToQuiz}
                        className="text-sm px-4 py-2 font-medium text-white bg-green-600 rounded hover:bg-green-700 flex items-center"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                        </svg>
                        Quiz Me
                      </button>
                      <button
                        onClick={clearResults}
                        className="text-sm text-red-600 hover:text-red-800"
                      >
                        Clear Results
                      </button>
                    </div>
                  </div>
                  <div className="border border-gray-200 rounded-lg overflow-hidden">
                    <div className="p-4 bg-white">
                      <p className="whitespace-pre-wrap text-gray-700 max-h-96 overflow-y-auto">
                        {summary}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Dashboard; 