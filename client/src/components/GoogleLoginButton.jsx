import React, { useEffect, useRef } from 'react';
import { Button, Box } from '@mui/material';
import GoogleIcon from '@mui/icons-material/Google';

const GoogleLoginButton = ({ onSuccess, onError, disabled = false }) => {
  const googleButtonRef = useRef(null);
  const initialized = useRef(false);

  useEffect(() => {
    // Load Google Identity Services script
    if (!window.google && !document.querySelector('#google-identity-script')) {
      const script = document.createElement('script');
      script.id = 'google-identity-script';
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.defer = true;
      script.onload = initializeGoogleSignIn;
      document.head.appendChild(script);
    } else if (window.google && !initialized.current) {
      initializeGoogleSignIn();
    }

    return () => {
      // Cleanup
      if (window.google && initialized.current) {
        try {
          window.google.accounts.id.cancel();
        } catch (error) {
          console.log('Google Sign-In cleanup error:', error);
        }
      }
    };
  }, []);

  const initializeGoogleSignIn = () => {
    if (window.google && !initialized.current) {
      try {
        window.google.accounts.id.initialize({
          client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
          callback: handleCredentialResponse,
          auto_select: false,
        });
        initialized.current = true;
      } catch (error) {
        console.error('Failed to initialize Google Sign-In:', error);
        onError?.(error);
      }
    }
  };

  const handleCredentialResponse = (response) => {
    try {
      // Decode the JWT token to get user info
      const credential = response.credential;
      const payload = JSON.parse(atob(credential.split('.')[1]));
      
      const googleUser = {
        id: payload.sub,
        email: payload.email,
        name: payload.name,
        picture: payload.picture,
        credential: credential
      };

      onSuccess?.(googleUser);
    } catch (error) {
      console.error('Error processing Google credential:', error);
      onError?.(error);
    }
  };

  const handleGoogleLogin = () => {
    if (window.google && initialized.current) {
      try {
        window.google.accounts.id.prompt();
      } catch (error) {
        console.error('Google Sign-In error:', error);
        onError?.(error);
      }
    } else {
      console.error('Google Sign-In not initialized');
      onError?.(new Error('Google Sign-In not available'));
    }
  };

  return (
    <Button
      ref={googleButtonRef}
      fullWidth
      variant="outlined"
      size="large"
      disabled={disabled}
      onClick={handleGoogleLogin}
      startIcon={<GoogleIcon />}
      sx={{
        borderColor: '#dadce0',
        color: '#3c4043',
        backgroundColor: '#fff',
        textTransform: 'none',
        fontWeight: 500,
        py: 1.5,
        '&:hover': {
          backgroundColor: '#f8f9fa',
          borderColor: '#dadce0',
          boxShadow: '0 1px 2px 0 rgba(60,64,67,.30), 0 1px 3px 1px rgba(60,64,67,.15)',
        },
        '&:disabled': {
          backgroundColor: '#f8f9fa',
          color: '#9aa0a6',
        }
      }}
    >
      Continue with Google
    </Button>
  );
};

export default GoogleLoginButton; 