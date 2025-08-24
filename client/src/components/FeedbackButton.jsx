import React, { useState } from 'react';
import { Box, Fab, Modal, Typography, TextField, Button, IconButton, Paper, Tooltip } from '@mui/material';
import { Feedback as FeedbackIcon, Close as CloseIcon } from '@mui/icons-material';
import axios from 'axios';

const FeedbackButton = () => {
  const [open, setOpen] = useState(false);
  const [feedbackText, setFeedbackText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [submitError, setSubmitError] = useState('');

  const handleOpen = () => {
    setOpen(true);
    setSubmitSuccess(false);
    setSubmitError('');
  };
  const handleClose = () => {
    setOpen(false);
    setFeedbackText('');
    setSubmitSuccess(false);
    setSubmitError('');
  };

  const handleSubmitFeedback = async () => {
    if (!feedbackText.trim()) return;
    setIsSubmitting(true);
    setSubmitError('');
    setSubmitSuccess(false);

    try {
      const response = await axios.post('/api/submit-feedback', {
        feedback: feedbackText,
      }, {
        withCredentials: true,
      });

      if (response.data.success) {
        setSubmitSuccess(true);
        setFeedbackText('');
      } else {
        setSubmitError(response.data.error || 'Failed to submit feedback.');
      }
    } catch (error) {
      console.error('Error submitting feedback:', error);
      setSubmitError('An error occurred. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <Tooltip title="Submit Feedback" arrow placement="left">
        <Fab
          color="primary"
          aria-label="feedback"
          sx={{
            position: 'fixed',
            bottom: 16,
            right: 16,
            zIndex: 1300,
          }}
          onClick={handleOpen}
        >
          <FeedbackIcon />
        </Fab>
      </Tooltip>

      <Modal
        open={open}
        onClose={handleClose}
        aria-labelledby="feedback-modal-title"
        aria-describedby="feedback-modal-description"
      >
        <Paper 
          sx={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            width: 400,
            bgcolor: 'background.paper',
            boxShadow: 24,
            p: 4,
            borderRadius: 2,
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
          }}
        >
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography id="feedback-modal-title" variant="h6" component="h2">
              Submit Feedback
            </Typography>
            <IconButton onClick={handleClose} size="small">
              <CloseIcon />
            </IconButton>
          </Box>
          <TextField
            id="feedback-modal-description"
            label="Your suggestions or issues"
            multiline
            rows={6}
            fullWidth
            variant="outlined"
            value={feedbackText}
            onChange={(e) => setFeedbackText(e.target.value)}
            placeholder="Tell us what you think..."
            disabled={isSubmitting}
          />
          {submitSuccess && (
            <Typography color="success.main" variant="body2">
              Feedback submitted successfully!
            </Typography>
          )}
          {submitError && (
            <Typography color="error.main" variant="body2">
              {submitError}
            </Typography>
          )}
          <Button
            variant="contained"
            color="primary"
            onClick={handleSubmitFeedback}
            disabled={!feedbackText.trim() || isSubmitting}
          >
            {isSubmitting ? 'Submitting...' : 'Submit'}
          </Button>
        </Paper>
      </Modal>
    </>
  );
};

export default FeedbackButton; 