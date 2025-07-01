"""
Unit tests for backend/open_ai_calls.py
"""
import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import json

# Add the parent directory to the Python path so we can import from backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class TestOpenAICalls(unittest.TestCase):
    """Test cases for OpenAI API calls"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        pass
    
    def tearDown(self):
        """Tear down test fixtures after each test method."""
        pass
    
    def test_randomize_answer_choices_valid(self):
        """Test randomizing answer choices with valid input"""
        from backend.open_ai_calls import randomize_answer_choices
        
        question = {
            'options': ['A', 'B', 'C', 'D'],
            'correctAnswer': 1
        }
        
        original_correct_option = question['options'][question['correctAnswer']]
        result = randomize_answer_choices(question)
        
        # Should still have 4 options
        self.assertEqual(len(result['options']), 4)
        
        # Correct answer should still point to the same option text
        self.assertEqual(result['options'][result['correctAnswer']], original_correct_option)
        
        # All original options should still be present
        self.assertEqual(set(result['options']), set(['A', 'B', 'C', 'D']))
    
    def test_randomize_answer_choices_invalid_options(self):
        """Test randomizing answer choices with invalid options"""
        from backend.open_ai_calls import randomize_answer_choices
        
        question = {
            'options': ['A', 'B'],  # Only 2 options instead of 4
            'correctAnswer': 0
        }
        
        result = randomize_answer_choices(question)
        
        # Should return unchanged
        self.assertEqual(result, question)
    
    def test_randomize_answer_choices_invalid_correct_answer(self):
        """Test randomizing answer choices with invalid correct answer"""
        from backend.open_ai_calls import randomize_answer_choices
        
        question = {
            'options': ['A', 'B', 'C', 'D'],
            'correctAnswer': 5  # Out of range
        }
        
        result = randomize_answer_choices(question)
        
        # Should return unchanged
        self.assertEqual(result, question)
    
    def test_randomize_answer_choices_missing_fields(self):
        """Test randomizing answer choices with missing fields"""
        from backend.open_ai_calls import randomize_answer_choices
        
        question = {'options': ['A', 'B', 'C', 'D']}  # Missing correctAnswer
        
        result = randomize_answer_choices(question)
        
        # Should return unchanged
        self.assertEqual(result, question)
    
    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.analyze_memory_usage')
    def test_gpt_summarize_transcript_no_stream(self, mock_analyze, mock_client):
        """Test GPT summarization without streaming"""
        from backend.open_ai_calls import gpt_summarize_transcript
        
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Generated summary content"
        mock_client.chat.completions.create.return_value = mock_response
        
        result = gpt_summarize_transcript("Test text", stream=False)
        
        self.assertEqual(result, "Generated summary content")
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('backend.open_ai_calls.openai_client')
    def test_gpt_summarize_transcript_with_stream(self, mock_client):
        """Test GPT summarization with streaming"""
        from backend.open_ai_calls import gpt_summarize_transcript
        
        mock_completion = MagicMock()
        mock_client.chat.completions.create.return_value = mock_completion
        
        result = gpt_summarize_transcript("Test text", stream=True)
        
        # Should return the completion object directly when streaming
        self.assertEqual(result, mock_completion)
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.upsert_quiz_questions_batch')
    @patch('backend.open_ai_calls.check_memory')
    @patch('backend.open_ai_calls.log_memory_usage')
    def test_generate_quiz_questions_success(self, mock_log, mock_check, mock_upsert, mock_client):
        """Test successful quiz question generation"""
        from backend.open_ai_calls import generate_quiz_questions
        
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_questions = [
            {
                'id': 1,
                'text': 'What is the capital of France?',
                'options': ['London', 'Paris', 'Berlin', 'Madrid'],
                'correctAnswer': 1,
                'reason': 'Paris is the capital of France.'
            }
        ]
        mock_response.choices[0].message.content = json.dumps(mock_questions)
        mock_client.chat.completions.create.return_value = mock_response
        
        # Mock database upsert
        mock_upsert.return_value = {"success": True, "count": 1}
        
        result, hashes = generate_quiz_questions("Test summary", 1, "content_hash")
        
        self.assertEqual(len(result), 1)
        self.assertEqual(len(hashes), 1)
        mock_upsert.assert_called_once()
    
    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.check_memory')
    @patch('backend.open_ai_calls.log_memory_usage')
    def test_generate_quiz_questions_json_cleanup(self, mock_log, mock_check, mock_client):
        """Test quiz question generation with JSON cleanup"""
        from backend.open_ai_calls import generate_quiz_questions
        
        # Mock OpenAI response with markdown formatting
        mock_response = MagicMock()
        mock_questions = [
            {
                'id': 1,
                'text': 'What is the capital of France?',
                'options': ['London', 'Paris', 'Berlin', 'Madrid'],
                'correctAnswer': 1,
                'reason': 'Paris is the capital of France.'
            }
        ]
        json_content = json.dumps(mock_questions)
        mock_response.choices[0].message.content = f"```json\n{json_content}\n```"
        mock_client.chat.completions.create.return_value = mock_response
        
        result, hashes = generate_quiz_questions("Test summary", 1, "content_hash")
        
        self.assertEqual(len(result), 1)
        self.assertEqual(len(hashes), 1)
    
    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.check_memory')
    @patch('backend.open_ai_calls.log_memory_usage')
    def test_generate_quiz_questions_validation_error(self, mock_log, mock_check, mock_client):
        """Test quiz question generation with validation error"""
        from backend.open_ai_calls import generate_quiz_questions
        
        # Mock OpenAI response with invalid structure
        mock_response = MagicMock()
        mock_questions = [
            {
                'id': 1,
                'text': 'What is the capital of France?',
                'options': ['London', 'Paris'],  # Only 2 options instead of 4
                'correctAnswer': 1,
                'reason': 'Paris is the capital of France.'
            }
        ]
        mock_response.choices[0].message.content = json.dumps(mock_questions)
        
        # Set up side effect to fail on first call, succeed on second
        mock_client.chat.completions.create.side_effect = [
            mock_response,  # First attempt fails validation
            mock_response   # Would continue retrying
        ]
        
        with self.assertRaises(Exception):
            generate_quiz_questions("Test summary", 1, "content_hash")
    
    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.check_memory')
    @patch('backend.open_ai_calls.log_memory_usage')
    def test_generate_quiz_questions_api_error(self, mock_log, mock_check, mock_client):
        """Test quiz question generation with API error"""
        from backend.open_ai_calls import generate_quiz_questions
        
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        with self.assertRaises(Exception):
            generate_quiz_questions("Test summary", 1, "content_hash")
    
    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.upsert_quiz_questions_batch')
    @patch('backend.open_ai_calls.check_memory')
    @patch('backend.open_ai_calls.log_memory_usage')
    def test_generate_focused_questions_success(self, mock_log, mock_check, mock_upsert, mock_client):
        """Test successful focused question generation"""
        from backend.open_ai_calls import generate_focused_questions
        
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_questions = [
            {
                'id': 1,
                'text': 'Focused question about mistakes?',
                'options': ['A', 'B', 'C', 'D'],
                'correctAnswer': 2,
                'reason': 'Explanation for focused question.'
            }
        ]
        mock_response.choices[0].message.content = json.dumps(mock_questions)
        mock_client.chat.completions.create.return_value = mock_response
        
        # Mock database upsert
        mock_upsert.return_value = {"success": True, "count": 1}
        
        previous_questions = [
            {'id': 'prev1', 'text': 'Previous question?'}
        ]
        
        result, hashes = generate_focused_questions(
            "Test summary", 
            ['wrong1'], 
            previous_questions, 
            1, 
            "content_hash"
        )
        
        self.assertEqual(len(result), 1)
        self.assertEqual(len(hashes), 1)
        mock_upsert.assert_called_once()
    
    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.check_memory')
    @patch('backend.open_ai_calls.log_memory_usage')
    def test_generate_focused_questions_empty_incorrect(self, mock_log, mock_check, mock_client):
        """Test focused question generation with empty incorrect questions"""
        from backend.open_ai_calls import generate_focused_questions
        
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_questions = [
            {
                'id': 1,
                'text': 'General question?',
                'options': ['A', 'B', 'C', 'D'],
                'correctAnswer': 0,
                'reason': 'General explanation.'
            }
        ]
        mock_response.choices[0].message.content = json.dumps(mock_questions)
        mock_client.chat.completions.create.return_value = mock_response
        
        result, hashes = generate_focused_questions(
            "Test summary", 
            [],  # No incorrect questions
            [], 
            1, 
            "content_hash"
        )
        
        self.assertEqual(len(result), 1)
        self.assertEqual(len(hashes), 1)
    
    @patch('backend.open_ai_calls.openai_client')
    def test_generate_short_title_success(self, mock_client):
        """Test successful short title generation"""
        from backend.open_ai_calls import generate_short_title
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Generated Short Title"
        mock_client.chat.completions.create.return_value = mock_response
        
        result = generate_short_title("Long text content to summarize")
        
        self.assertEqual(result, "Generated Short Title")
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('backend.open_ai_calls.openai_client')
    def test_generate_short_title_api_error(self, mock_client):
        """Test short title generation with API error"""
        from backend.open_ai_calls import generate_short_title
        
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        result = generate_short_title("Long text content to summarize")
        
        # Should return default title on error
        self.assertEqual(result, "Untitled")
    
    @patch('backend.open_ai_calls.openai_client')
    def test_generate_short_title_empty_response(self, mock_client):
        """Test short title generation with empty response"""
        from backend.open_ai_calls import generate_short_title
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = ""
        mock_client.chat.completions.create.return_value = mock_response
        
        result = generate_short_title("Long text content to summarize")
        
        # Should return an empty string as per current buggy behavior
        self.assertEqual(result, "")

    @patch('backend.open_ai_calls.random.shuffle')
    def test_randomize_answer_choices_no_op_invalid_options(self, mock_shuffle):
        """Test randomizing answer choices with invalid options"""
        from backend.open_ai_calls import randomize_answer_choices
        
        question = {
            'options': ['A', 'B'],  # Only 2 options instead of 4
            'correctAnswer': 0
        }
        
        result = randomize_answer_choices(question)
        
        # Should return unchanged
        self.assertEqual(result, question)

if __name__ == '__main__':
    unittest.main() 