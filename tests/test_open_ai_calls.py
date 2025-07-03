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
        mock_questions = {'questions': [
            {'id': 1, 'text': 'Q1', 'options': ['A', 'B', 'C', 'D'], 'correctAnswer': 1, 'reason': 'R1'}
        ]}
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
    def test_generate_quiz_questions_json_error(self, mock_log, mock_check, mock_client):
        """Test quiz question generation with JSON error"""
        from backend.open_ai_calls import generate_quiz_questions
        
        mock_response = MagicMock()
        # Return invalid JSON that will cause a JSON decode error
        mock_response.choices[0].message.content = "invalid json content"
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch('backend.open_ai_calls.upsert_quiz_questions_batch', return_value={"success": True, "count": 1}):
            with self.assertRaises(Exception) as context:
                generate_quiz_questions("Test summary", 1, "content_hash")
            self.assertIn("Failed to get valid JSON response from AI", str(context.exception))
    
    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.database.upsert_quiz_questions_batch')
    def test_generate_quiz_questions_validation_error(self, mock_upsert, mock_client):
        """Test quiz question generation with validation error"""
        from backend.open_ai_calls import generate_quiz_questions
        
        # Response is invalid - missing required fields
        invalid_response = MagicMock()
        invalid_response.choices[0].message.content = '{"questions": [{"id": 1}]}' # Missing fields
        
        mock_client.chat.completions.create.return_value = invalid_response
        mock_upsert.return_value = {"success": True, "count": 1}
        
        with patch('backend.open_ai_calls.check_memory'), patch('backend.open_ai_calls.log_memory_usage'):
            # It should raise an Exception wrapping the validation error
            with self.assertRaises(Exception) as context:
                generate_quiz_questions("Test summary", 1, "content_hash")
            self.assertIn("Failed to get valid JSON response from AI", str(context.exception))
            # Should only call the API once since there's no retry logic
            self.assertEqual(mock_client.chat.completions.create.call_count, 1)
        

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
        mock_questions = {'questions': [{'id': 1, 'text': 'Q1', 'options': ['A', 'B', 'C', 'D'], 'correctAnswer': 1, 'reason': 'R1'}]}
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
        
        result = generate_short_title("Text")
        self.assertEqual(result, "")  # Function returns empty string, not "Untitled Study Set"

    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.upsert_quiz_questions_batch')
    def test_generate_quiz_questions_with_none_parameters(self, mock_upsert, mock_client):
        """Test quiz question generation with None values for optional parameters"""
        from backend.open_ai_calls import generate_quiz_questions
        
        mock_response = MagicMock()
        mock_questions = {'questions': [{'id': 1, 'text': 'Q1', 'options': ['A', 'B', 'C', 'D'], 'correctAnswer': 1, 'reason': 'R1'}]}
        mock_response.choices[0].message.content = json.dumps(mock_questions)
        mock_client.chat.completions.create.return_value = mock_response
        mock_upsert.return_value = {"success": True, "count": 1}
        
        with patch('backend.open_ai_calls.check_memory'), patch('backend.open_ai_calls.log_memory_usage'):
            result, hashes = generate_quiz_questions("summary", 1, "hash", 
                                                   incorrect_question_ids=None, 
                                                   previous_questions=None)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(len(hashes), 1)
        # Verify the function used the general prompt (not focused)
        args, kwargs = mock_client.chat.completions.create.call_args
        prompt_content = kwargs['messages'][1]['content']  # User message, not system message
        self.assertIn("create 5 VERY challenging", prompt_content)
        self.assertNotIn("INCORRECTLY", prompt_content)

    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.upsert_quiz_questions_batch')
    def test_generate_quiz_questions_with_empty_lists(self, mock_upsert, mock_client):
        """Test quiz question generation with empty lists for optional parameters"""
        from backend.open_ai_calls import generate_quiz_questions
        
        mock_response = MagicMock()
        mock_questions = {'questions': [{'id': 1, 'text': 'Q1', 'options': ['A', 'B', 'C', 'D'], 'correctAnswer': 1, 'reason': 'R1'}]}
        mock_response.choices[0].message.content = json.dumps(mock_questions)
        mock_client.chat.completions.create.return_value = mock_response
        mock_upsert.return_value = {"success": True, "count": 1}
        
        with patch('backend.open_ai_calls.check_memory'), patch('backend.open_ai_calls.log_memory_usage'):
            result, hashes = generate_quiz_questions("summary", 1, "hash", 
                                                   incorrect_question_ids=[], 
                                                   previous_questions=[])
        
        self.assertEqual(len(result), 1)
        # Should use general prompt since lists are empty
        args, kwargs = mock_client.chat.completions.create.call_args
        prompt_content = kwargs['messages'][1]['content']  # User message
        self.assertIn("create 5 VERY challenging", prompt_content)
        self.assertNotIn("INCORRECTLY", prompt_content)

    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.upsert_quiz_questions_batch')
    def test_generate_quiz_questions_focused_with_both_parameters(self, mock_upsert, mock_client):
        """Test focused quiz question generation with both incorrect IDs and previous questions"""
        from backend.open_ai_calls import generate_quiz_questions
        
        mock_response = MagicMock()
        mock_questions = {'questions': [{'id': 1, 'text': 'Focused Q1', 'options': ['A', 'B', 'C', 'D'], 'correctAnswer': 1, 'reason': 'R1'}]}
        mock_response.choices[0].message.content = json.dumps(mock_questions)
        mock_client.chat.completions.create.return_value = mock_response
        mock_upsert.return_value = {"success": True, "count": 1}
        
        incorrect_ids = ['q1', 'q2']
        previous_questions = [
            {'id': 'q1', 'text': 'Previous Q1', 'options': ['A', 'B', 'C', 'D']},
            {'id': 'q2', 'text': 'Previous Q2', 'options': ['A', 'B', 'C', 'D']}
        ]
        
        with patch('backend.open_ai_calls.check_memory'), patch('backend.open_ai_calls.log_memory_usage'):
            result, hashes = generate_quiz_questions("summary", 1, "hash", 
                                                   incorrect_question_ids=incorrect_ids, 
                                                   previous_questions=previous_questions)
        
        self.assertEqual(len(result), 1)
        # Verify the function used the focused prompt
        args, kwargs = mock_client.chat.completions.create.call_args
        prompt_content = kwargs['messages'][1]['content']  # User message
        self.assertIn("INCORRECTLY", prompt_content)
        self.assertIn("Previous Q1", prompt_content)
        self.assertIn("Previous Q2", prompt_content)

    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.upsert_quiz_questions_batch')
    def test_generate_quiz_questions_with_incorrect_ids_only(self, mock_upsert, mock_client):
        """Test quiz question generation with only incorrect IDs (no previous questions)"""
        from backend.open_ai_calls import generate_quiz_questions
        
        mock_response = MagicMock()
        mock_questions = {'questions': [{'id': 1, 'text': 'Q1', 'options': ['A', 'B', 'C', 'D'], 'correctAnswer': 1, 'reason': 'R1'}]}
        mock_response.choices[0].message.content = json.dumps(mock_questions)
        mock_client.chat.completions.create.return_value = mock_response
        mock_upsert.return_value = {"success": True, "count": 1}
        
        with patch('backend.open_ai_calls.check_memory'), patch('backend.open_ai_calls.log_memory_usage'):
            result, hashes = generate_quiz_questions("summary", 1, "hash", 
                                                   incorrect_question_ids=['q1'], 
                                                   previous_questions=None)
        
        self.assertEqual(len(result), 1)
        # Should use general prompt since we don't have previous questions to reference
        args, kwargs = mock_client.chat.completions.create.call_args
        prompt_content = kwargs['messages'][1]['content']  # User message
        self.assertIn("create 5 VERY challenging", prompt_content)

    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.upsert_quiz_questions_batch')
    def test_generate_quiz_questions_with_previous_questions_only(self, mock_upsert, mock_client):
        """Test quiz question generation with only previous questions (no incorrect IDs)"""
        from backend.open_ai_calls import generate_quiz_questions
        
        mock_response = MagicMock()
        mock_questions = {'questions': [{'id': 1, 'text': 'Q1', 'options': ['A', 'B', 'C', 'D'], 'correctAnswer': 1, 'reason': 'R1'}]}
        mock_response.choices[0].message.content = json.dumps(mock_questions)
        mock_client.chat.completions.create.return_value = mock_response
        mock_upsert.return_value = {"success": True, "count": 1}
        
        previous_questions = [{'id': 'q1', 'text': 'Previous Q1'}]
        
        with patch('backend.open_ai_calls.check_memory'), patch('backend.open_ai_calls.log_memory_usage'):
            result, hashes = generate_quiz_questions("summary", 1, "hash", 
                                                   incorrect_question_ids=None, 
                                                   previous_questions=previous_questions)
        
        self.assertEqual(len(result), 1)
        # Should use general prompt since we don't have incorrect IDs
        args, kwargs = mock_client.chat.completions.create.call_args
        prompt_content = kwargs['messages'][1]['content']  # User message
        self.assertIn("create 5 VERY challenging", prompt_content)

    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.upsert_quiz_questions_batch')
    def test_generate_quiz_questions_focused_prompt_construction(self, mock_upsert, mock_client):
        """Test that focused prompt is constructed correctly with all necessary information"""
        from backend.open_ai_calls import generate_quiz_questions
        
        mock_response = MagicMock()
        mock_questions = {'questions': [{'id': 1, 'text': 'Q1', 'options': ['A', 'B', 'C', 'D'], 'correctAnswer': 1, 'reason': 'R1'}]}
        mock_response.choices[0].message.content = json.dumps(mock_questions)
        mock_client.chat.completions.create.return_value = mock_response
        mock_upsert.return_value = {"success": True, "count": 1}
        
        incorrect_ids = ['q1']
        previous_questions = [
            {'id': 'q1', 'text': 'What is photosynthesis?', 'options': ['Process A', 'Process B', 'Process C', 'Process D']},
            {'id': 'q2', 'text': 'What is respiration?', 'options': ['Process X', 'Process Y', 'Process Z', 'Process W']}
        ]
        
        with patch('backend.open_ai_calls.check_memory'), patch('backend.open_ai_calls.log_memory_usage'):
            result, hashes = generate_quiz_questions("Biology summary", 1, "hash", 
                                                   incorrect_question_ids=incorrect_ids, 
                                                   previous_questions=previous_questions)
        
        # Verify the prompt contains all expected elements
        args, kwargs = mock_client.chat.completions.create.call_args
        prompt_content = kwargs['messages'][1]['content']  # User message
        
        # Check for focused prompt elements
        self.assertIn("INCORRECTLY", prompt_content)
        self.assertIn("What is photosynthesis?", prompt_content)
        self.assertIn("What is respiration?", prompt_content)
        self.assertIn("Biology summary", prompt_content)  # Summary should be included

    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.upsert_quiz_questions_batch')
    def test_generate_quiz_questions_randomization_applied(self, mock_upsert, mock_client):
        """Test that answer choice randomization is applied to generated questions"""
        from backend.open_ai_calls import generate_quiz_questions
        
        mock_response = MagicMock()
        mock_questions = {'questions': [
            {'id': 1, 'text': 'Q1', 'options': ['Option A', 'Option B', 'Option C', 'Option D'], 'correctAnswer': 0, 'reason': 'R1'}
        ]}
        mock_response.choices[0].message.content = json.dumps(mock_questions)
        mock_client.chat.completions.create.return_value = mock_response
        mock_upsert.return_value = {"success": True, "count": 1}
        
        with patch('backend.open_ai_calls.check_memory'), patch('backend.open_ai_calls.log_memory_usage'):
            with patch('backend.open_ai_calls.randomize_answer_choices') as mock_randomize:
                # Mock randomization to change the correct answer
                def side_effect(q):
                    q_copy = q.copy()
                    q_copy['correctAnswer'] = 2  # Change from 0 to 2
                    return q_copy
                mock_randomize.side_effect = side_effect
                
                result, hashes = generate_quiz_questions("summary", 1, "hash")
        
        # Verify randomization was called
        mock_randomize.assert_called_once()
        self.assertEqual(len(result), 1)

    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.upsert_quiz_questions_batch')
    def test_generate_quiz_questions_hash_generation(self, mock_upsert, mock_client):
        """Test that question hashes are generated correctly"""
        from backend.open_ai_calls import generate_quiz_questions
        
        mock_response = MagicMock()
        mock_questions = {'questions': [
            {'id': 1, 'text': 'Q1', 'options': ['A', 'B', 'C', 'D'], 'correctAnswer': 1, 'reason': 'R1'},
            {'id': 2, 'text': 'Q2', 'options': ['W', 'X', 'Y', 'Z'], 'correctAnswer': 2, 'reason': 'R2'}
        ]}
        mock_response.choices[0].message.content = json.dumps(mock_questions)
        mock_client.chat.completions.create.return_value = mock_response
        mock_upsert.return_value = {"success": True, "count": 2}
        
        with patch('backend.open_ai_calls.check_memory'), patch('backend.open_ai_calls.log_memory_usage'):
            result, hashes = generate_quiz_questions("summary", 1, "hash")
        
        self.assertEqual(len(result), 2)
        self.assertEqual(len(hashes), 2)
        # Each question should have a hash field
        for question in result:
            self.assertIn('hash', question)
            self.assertIsInstance(question['hash'], str)
            self.assertEqual(len(question['hash']), 64)  # SHA256 hash length

    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.upsert_quiz_questions_batch')
    def test_generate_quiz_questions_database_upsert_called(self, mock_upsert, mock_client):
        """Test that database upsert is called with correct parameters"""
        from backend.open_ai_calls import generate_quiz_questions
        
        mock_response = MagicMock()
        mock_questions = {'questions': [{'id': 1, 'text': 'Q1', 'options': ['A', 'B', 'C', 'D'], 'correctAnswer': 1, 'reason': 'R1'}]}
        mock_response.choices[0].message.content = json.dumps(mock_questions)
        mock_client.chat.completions.create.return_value = mock_response
        mock_upsert.return_value = {"success": True, "count": 1}
        
        with patch('backend.open_ai_calls.check_memory'), patch('backend.open_ai_calls.log_memory_usage'):
            result, hashes = generate_quiz_questions("summary", 123, "content_hash")
        
        # Verify upsert was called with correct structure
        mock_upsert.assert_called_once()
        call_args = mock_upsert.call_args[0][0]  # First positional argument
        
        self.assertEqual(len(call_args), 1)
        self.assertIn('hash', call_args[0])
        self.assertIn('question', call_args[0])
        self.assertEqual(call_args[0]['user_id'], 123)
        self.assertEqual(call_args[0]['question_set_hash'], "content_hash")  # Correct field name

    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.upsert_quiz_questions_batch')
    def test_generate_quiz_questions_with_custom_num_questions(self, mock_upsert, mock_client):
        """Test quiz generation with custom number of questions"""
        from backend.open_ai_calls import generate_quiz_questions
        
        mock_response = MagicMock()
        mock_questions = {'questions': [
            {'id': i, 'text': f'Q{i}', 'options': ['A', 'B', 'C', 'D'], 'correctAnswer': 1, 'reason': f'R{i}'}
            for i in range(1, 11)  # 10 questions
        ]}
        mock_response.choices[0].message.content = json.dumps(mock_questions)
        mock_client.chat.completions.create.return_value = mock_response
        mock_upsert.return_value = {"success": True, "count": 10}
        
        with patch('backend.open_ai_calls.check_memory'), patch('backend.open_ai_calls.log_memory_usage'):
            result, hashes = generate_quiz_questions("summary", 1, "hash", num_questions=10)
        
        # Verify that the prompt includes the custom number
        args, kwargs = mock_client.chat.completions.create.call_args
        prompt_content = kwargs['messages'][1]['content']
        self.assertIn("create 10 VERY challenging", prompt_content)
        
        self.assertEqual(len(result), 10)
        self.assertEqual(len(hashes), 10)

    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.upsert_quiz_questions_batch')
    def test_generate_quiz_questions_with_default_num_questions(self, mock_upsert, mock_client):
        """Test quiz generation uses default of 5 questions when not specified"""
        from backend.open_ai_calls import generate_quiz_questions
        
        mock_response = MagicMock()
        mock_questions = {'questions': [
            {'id': i, 'text': f'Q{i}', 'options': ['A', 'B', 'C', 'D'], 'correctAnswer': 1, 'reason': f'R{i}'}
            for i in range(1, 6)  # 5 questions
        ]}
        mock_response.choices[0].message.content = json.dumps(mock_questions)
        mock_client.chat.completions.create.return_value = mock_response
        mock_upsert.return_value = {"success": True, "count": 5}
        
        with patch('backend.open_ai_calls.check_memory'), patch('backend.open_ai_calls.log_memory_usage'):
            # Call without num_questions parameter
            result, hashes = generate_quiz_questions("summary", 1, "hash")
        
        # Verify that the prompt includes the default number (5)
        args, kwargs = mock_client.chat.completions.create.call_args
        prompt_content = kwargs['messages'][1]['content']
        self.assertIn("create 5 VERY challenging", prompt_content)
        
        self.assertEqual(len(result), 5)
        self.assertEqual(len(hashes), 5)

    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.upsert_quiz_questions_batch')
    def test_generate_quiz_questions_num_questions_in_focused_prompt(self, mock_upsert, mock_client):
        """Test that custom num_questions is used in focused prompt"""
        from backend.open_ai_calls import generate_quiz_questions
        
        mock_response = MagicMock()
        mock_questions = {'questions': [
            {'id': i, 'text': f'Q{i}', 'options': ['A', 'B', 'C', 'D'], 'correctAnswer': 1, 'reason': f'R{i}'}
            for i in range(1, 9)  # 8 questions
        ]}
        mock_response.choices[0].message.content = json.dumps(mock_questions)
        mock_client.chat.completions.create.return_value = mock_response
        mock_upsert.return_value = {"success": True, "count": 8}
        
        incorrect_ids = ['q1', 'q2']
        previous_questions = [
            {'id': 'q1', 'text': 'Previous Q1', 'options': ['A', 'B', 'C', 'D']},
            {'id': 'q2', 'text': 'Previous Q2', 'options': ['A', 'B', 'C', 'D']}
        ]
        
        with patch('backend.open_ai_calls.check_memory'), patch('backend.open_ai_calls.log_memory_usage'):
            result, hashes = generate_quiz_questions("summary", 1, "hash", 
                                                   incorrect_question_ids=incorrect_ids, 
                                                   previous_questions=previous_questions,
                                                   num_questions=8)
        
        # Verify the focused prompt includes the custom number
        args, kwargs = mock_client.chat.completions.create.call_args
        prompt_content = kwargs['messages'][1]['content']
        self.assertIn("INCORRECTLY", prompt_content)  # Confirm it's focused prompt
        self.assertIn("create 8", prompt_content)  # Should include custom number
        
        self.assertEqual(len(result), 8)
        self.assertEqual(len(hashes), 8)

    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.upsert_quiz_questions_batch')
    def test_generate_quiz_questions_boundary_num_questions(self, mock_upsert, mock_client):
        """Test quiz generation with boundary values for num_questions"""
        from backend.open_ai_calls import generate_quiz_questions
        
        # Test with minimum value (1)
        mock_response = MagicMock()
        mock_questions = {'questions': [
            {'id': 1, 'text': 'Q1', 'options': ['A', 'B', 'C', 'D'], 'correctAnswer': 1, 'reason': 'R1'}
        ]}
        mock_response.choices[0].message.content = json.dumps(mock_questions)
        mock_client.chat.completions.create.return_value = mock_response
        mock_upsert.return_value = {"success": True, "count": 1}
        
        with patch('backend.open_ai_calls.check_memory'), patch('backend.open_ai_calls.log_memory_usage'):
            result, hashes = generate_quiz_questions("summary", 1, "hash", num_questions=1)
        
        # Verify that the prompt includes num_questions=1
        args, kwargs = mock_client.chat.completions.create.call_args
        prompt_content = kwargs['messages'][1]['content']
        self.assertIn("create 1 VERY challenging", prompt_content)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(len(hashes), 1)

    @patch('backend.open_ai_calls.openai_client')
    @patch('backend.open_ai_calls.upsert_quiz_questions_batch')
    def test_generate_quiz_questions_max_num_questions(self, mock_upsert, mock_client):
        """Test quiz generation with maximum number of questions (20)"""
        from backend.open_ai_calls import generate_quiz_questions
        
        mock_response = MagicMock()
        mock_questions = {'questions': [
            {'id': i, 'text': f'Q{i}', 'options': ['A', 'B', 'C', 'D'], 'correctAnswer': 1, 'reason': f'R{i}'}
            for i in range(1, 21)  # 20 questions
        ]}
        mock_response.choices[0].message.content = json.dumps(mock_questions)
        mock_client.chat.completions.create.return_value = mock_response
        mock_upsert.return_value = {"success": True, "count": 20}
        
        with patch('backend.open_ai_calls.check_memory'), patch('backend.open_ai_calls.log_memory_usage'):
            result, hashes = generate_quiz_questions("summary", 1, "hash", num_questions=20)
        
        # Verify that the prompt includes num_questions=20
        args, kwargs = mock_client.chat.completions.create.call_args
        prompt_content = kwargs['messages'][1]['content']
        self.assertIn("create 20 VERY challenging", prompt_content)
        
        self.assertEqual(len(result), 20)
        self.assertEqual(len(hashes), 20)

if __name__ == '__main__':
    unittest.main() 