import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const Dashboard = ({ setIsAuthenticated, user, transcription, setTranscription }) => {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
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

  const handleFileSelect = (e) => {
    console.log("selecting file")
    const selectedFile = e.target.files[0];
    if (selectedFile && selectedFile.type === 'video/mp4') {
      setFile(selectedFile);
      setError('');
      console.log("set file success")
    } else {
      setError('Please select an MP4 file');
      setFile(null);
    }
  };

  const uploadVideo = async () => {
    if (!file) {
      setError('Please select a file first');
      return;
    }
  
    try {
      console.log("uploading video");
      setIsUploading(true);
      setProgress(0);
      setError('');
      setTranscription('');
      
      abortController.current = new AbortController();
  
      // Create FormData and append the file
      const formData = new FormData();
      formData.append('file', file);
  
      const response = await axios.post('/api/upload-and-extract', formData, {
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
        console.log("transcription success")
        console.log(response.data.transcription)
        setTranscription(response.data.transcription);
      } else {
        setError('Transcription failed');
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
              Video Transcription
            </h2>

            {/* File Selection Area */}
            <div className="space-y-6">
              <div className="flex flex-col items-center justify-center border-2 border-dashed border-gray-300 rounded-lg p-8 bg-gray-50 hover:bg-gray-100 transition-colors">
                <input
                  type="file"
                  accept="video/mp4"
                  onChange={handleFileSelect}
                  className="block w-full text-sm text-gray-500
                    file:mr-4 file:py-2 file:px-4
                    file:rounded-full file:border-0
                    file:text-sm file:font-semibold
                    file:bg-blue-50 file:text-blue-700
                    hover:file:bg-blue-100
                    cursor-pointer"
                />
                {file && (
                  <div className="mt-4 text-sm text-gray-600">
                    Selected: {file.name}
                  </div>
                )}
              </div>

              {/* Submit Button */}
              <div className="flex justify-center">
                <button
                  onClick={uploadVideo}
                  disabled={!file || isUploading}
                  className={`px-6 py-3 rounded-lg font-medium text-white 
                    ${!file || isUploading 
                      ? 'bg-gray-400 cursor-not-allowed' 
                      : 'bg-blue-500 hover:bg-blue-600 transition-colors'
                    }`}
                >
                  {isUploading ? 'Transcribing...' : 'Start Transcription'}
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
                    <span>{progress}% complete</span>
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

              {/* Transcription Result */}
              {transcription && (
                <div className="mt-8">
                  <h3 className="text-lg font-semibold mb-3 text-gray-800">
                    Transcription Result:
                  </h3>
                  <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                    <p className="whitespace-pre-wrap text-gray-700">
                      {transcription}
                    </p>
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