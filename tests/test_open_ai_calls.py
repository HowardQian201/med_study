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

# Since we are testing functions in open_ai_calls, we need to make sure
# the functions are imported *after* the mocks are in place for some tests.
# Therefore, we will import them inside each test function.

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
        
        self.assertEqual(len(result['options']), 4)
        self.assertEqual(result['options'][result['correctAnswer']], original_correct_option)
        self.assertEqual(set(result['options']), set(['A', 'B', 'C', 'D']))
    
    def test_randomize_answer_choices_invalid_options(self):
        """Test randomizing with invalid options (should not change)"""
        from backend.open_ai_calls import randomize_answer_choices
        question = {'options': ['A', 'B'], 'correctAnswer': 0}
        result = randomize_answer_choices(question)
        self.assertEqual(result, question)

    def test_randomize_answer_choices_invalid_correct_answer(self):
        """Test randomizing with invalid correct answer (should not change)"""
        from backend.open_ai_calls import randomize_answer_choices
        question = {'options': ['A', 'B', 'C', 'D'], 'correctAnswer': 5}
        result = randomize_answer_choices(question)
        self.assertEqual(result, question)

    def test_randomize_answer_choices_missing_fields(self):
        """Test randomizing with missing fields (should not change)"""
        from backend.open_ai_calls import randomize_answer_choices
        question = {'options': ['A', 'B', 'C', 'D']}
        result = randomize_answer_choices(question)
        self.assertEqual(result, question)

    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.analyze_memory_usage')
    def test_gpt_summarize_transcript_no_stream(self, mock_analyze, mock_client):
        """Test GPT summarization without streaming"""
        from backend.open_ai_calls import gpt_summarize_transcript
        
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
        
        self.assertEqual(result, mock_completion)
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.upsert_quiz_questions_batch')
    @patch('backend.open_ai_calls.check_memory')
    @patch('backend.open_ai_calls.log_memory_usage')
    def test_generate_quiz_questions_success(self, mock_log, mock_check, mock_upsert, mock_client):
        """Test successful quiz question generation"""
        from backend.open_ai_calls import generate_quiz_questions

        mock_response = MagicMock()
        # The actual code expects a list, not an object with "questions" key
        mock_questions = [
            {'id': 1, 'text': 'Q1', 'options': ['A', 'B', 'C', 'D'], 'correctAnswer': 1, 'reason': 'R1'}
        ]
        mock_response.choices[0].message.content = json.dumps(mock_questions)
        mock_client.chat.completions.create.return_value = mock_response
        
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
        
        mock_response = MagicMock()
        mock_questions = [{'id': 1, 'text': 'Q1', 'options': ['A', 'B', 'C', 'D'], 'correctAnswer': 1, 'reason': 'R1'}]
        json_content = json.dumps(mock_questions)
        mock_response.choices[0].message.content = f"```json\n{json_content}\n```"
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch('backend.open_ai_calls.upsert_quiz_questions_batch', return_value={"success": True, "count": 1}):
            result, hashes = generate_quiz_questions("Test summary", 1, "content_hash")
        
        self.assertEqual(len(result), 1)
    
    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.database.upsert_quiz_questions_batch')
    def test_generate_quiz_questions_validation_error_retry(self, mock_upsert, mock_client):
        """Test quiz question generation with validation error retry"""
        from backend.open_ai_calls import generate_quiz_questions
        
        # First response is invalid, second is valid
        invalid_response = MagicMock()
        invalid_response.choices[0].message.content = '[{"id": 1}]' # Missing fields
        
        valid_response = MagicMock()
        valid_response.choices[0].message.content = json.dumps([{
            "id": 1, "text": "Q1", "options": ["A", "B", "C", "D"],
            "correctAnswer": 0, "reason": "R"
        }])
        
        mock_client.chat.completions.create.side_effect = [invalid_response, valid_response]
        mock_upsert.return_value = {"success": True, "count": 1}
        
        with patch('backend.open_ai_calls.check_memory'), patch('backend.open_ai_calls.log_memory_usage'):
            # It should retry and eventually succeed
            generate_quiz_questions("Test summary", 1, "content_hash")
            # The current implementation should retry on validation error
            self.assertEqual(mock_client.chat.completions.create.call_count, 2)
        

    @patch('backend.open_ai_calls.openai_client')
    def test_generate_quiz_questions_api_error(self, mock_client):
        """Test quiz question generation with API error"""
        from backend.open_ai_calls import generate_quiz_questions
        
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        with patch('backend.open_ai_calls.check_memory'), patch('backend.open_ai_calls.log_memory_usage'):
            with self.assertRaises(Exception) as context:
                generate_quiz_questions("Test summary", 1, "content_hash")
            # The actual exception message is "API Error" not the retry message
            self.assertIn("API Error", str(context.exception))
    
    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.upsert_quiz_questions_batch')
    def test_generate_focused_questions_success(self, mock_upsert, mock_client):
        """Test successful focused question generation using generate_quiz_questions with optional parameters"""
        from backend.open_ai_calls import generate_quiz_questions
        
        mock_response = MagicMock()
        mock_questions = [{'id': 1, 'text': 'Q1', 'options': ['A', 'B', 'C', 'D'], 'correctAnswer': 1, 'reason': 'R1'}]
        mock_response.choices[0].message.content = json.dumps(mock_questions)
        mock_client.chat.completions.create.return_value = mock_response
        
        mock_upsert.return_value = {"success": True, "count": 1}
        
        with patch('backend.open_ai_calls.check_memory'), patch('backend.open_ai_calls.log_memory_usage'):
            result, hashes = generate_quiz_questions("summary", 1, "hash", 
                                                   incorrect_question_ids=['id1'], 
                                                   previous_questions=[{'id': 'id1', 'text': 'prevQ'}])
        
        self.assertEqual(len(result), 1)
        mock_upsert.assert_called_once()
    
    @patch('backend.open_ai_calls.openai_client')
    def test_generate_short_title_success(self, mock_client):
        """Test successful short title generation"""
        from backend.open_ai_calls import generate_short_title
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = 'A Short Title'
        mock_client.chat.completions.create.return_value = mock_response
        
        result = generate_short_title("Long summary text...")
        self.assertEqual(result, "A Short Title")

    @patch('backend.open_ai_calls.openai_client')
    def test_generate_short_title_api_error(self, mock_client):
        """Test short title generation with API error"""
        from backend.open_ai_calls import generate_short_title
        
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        result = generate_short_title("Long summary text...")
        self.assertEqual(result, "Untitled")

    @patch('backend.open_ai_calls.openai_client')
    def test_generate_short_title_empty_response(self, mock_client):
        """Test short title generation with empty response"""
        from backend.open_ai_calls import generate_short_title
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = ""
        mock_client.chat.completions.create.return_value = mock_response
        
        result = generate_short_title("Long summary text...")
        self.assertEqual(result, "")

if __name__ == '__main__':
    unittest.main() 