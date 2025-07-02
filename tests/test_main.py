"""
Unit tests for backend/main.py
"""
import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
import json
from io import BytesIO

# Add the parent directory to the Python path so we can import from backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class TestMainRoutes(unittest.TestCase):
    """Test cases for main Flask routes"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Import app after path setup
        from backend.main import app
        self.app = app
        self.client = app.test_client()
        self.app.config['TESTING'] = True
        
    def tearDown(self):
        """Tear down test fixtures after each test method."""
        pass
    
    @patch('backend.main.authenticate_user')
    def test_login_success(self, mock_auth):
        """Test successful login"""
        mock_auth.return_value = {
            "success": True,
            "authenticated": True,
            "user": {"id": 1, "name": "Test User", "email": "test@example.com"}
        }
        
        response = self.client.post('/api/auth/login',
                                  data=json.dumps({
                                      'email': 'test@example.com',
                                      'password': 'password123'
                                  }),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
    
    @patch('backend.main.authenticate_user')
    def test_login_invalid_credentials(self, mock_auth):
        """Test login with invalid credentials"""
        mock_auth.return_value = {
            "success": True,
            "authenticated": False
        }
        
        response = self.client.post('/api/auth/login',
                                  data=json.dumps({
                                      'email': 'test@example.com',
                                      'password': 'wrongpassword'
                                  }),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 401)
    
    def test_login_missing_fields(self):
        """Test login with missing email or password"""
        response = self.client.post('/api/auth/login',
                                  data=json.dumps({'email': 'test@example.com'}),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
    
    def test_login_invalid_email_format(self):
        """Test login with invalid email format"""
        response = self.client.post('/api/auth/login',
                                  data=json.dumps({
                                      'email': 'invalid-email',
                                      'password': 'password123'
                                  }),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
    
    @patch('backend.main.authenticate_user')
    def test_login_database_error(self, mock_auth):
        """Test login with database error"""
        mock_auth.return_value = {
            "success": False,
            "error": "Database connection failed"
        }
        
        response = self.client.post('/api/auth/login',
                                  data=json.dumps({
                                      'email': 'test@example.com',
                                      'password': 'password123'
                                  }),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 500)
    
    def test_logout(self):
        """Test logout functionality"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['name'] = 'Test User'
            sess['email'] = 'test@example.com'
        
        response = self.client.post('/api/auth/logout')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
    
    def test_check_auth_authenticated(self):
        """Test auth check for authenticated user"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['name'] = 'Test User'
            sess['email'] = 'test@example.com'
            sess['summary'] = 'Test summary'
        
        response = self.client.get('/api/auth/check')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['authenticated'])
        self.assertEqual(data['user']['name'], 'Test User')
    
    def test_check_auth_not_authenticated(self):
        """Test auth check for unauthenticated user"""
        response = self.client.get('/api/auth/check')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data['authenticated'])
    
    def test_upload_multiple_unauthorized(self):
        """Test upload without authentication"""
        response = self.client.post('/api/upload-multiple')
        self.assertEqual(response.status_code, 401)
    
    @patch('backend.main.get_container_memory_limit')
    @patch('backend.main.set_process_priority')
    @patch('backend.main.log_memory_usage')
    @patch('backend.main.extract_text_from_pdf_memory')
    @patch('backend.main.generate_file_hash')
    @patch('backend.main.check_file_exists')
    @patch('backend.main.generate_content_hash')
    @patch('backend.main.gpt_summarize_transcript')
    def test_upload_multiple_success(self, mock_gpt, mock_content_hash, mock_check_file,
                                    mock_file_hash, mock_extract, mock_log, mock_priority, mock_memory):
        """Test successful file upload and processing"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1

        mock_memory.return_value = 1024 * 1024 * 1024  # 1GB
        mock_check_file.return_value = {"exists": False, "data": None}
        mock_file_hash.return_value = "test_hash"
        mock_extract.return_value = "Extracted text content"
        mock_content_hash.return_value = "content_hash"

        # Mock the streaming response from GPT
        def mock_stream_generator(text, stream=False):
            class MockDelta:
                content = "Generated summary"
            class MockChoice:
                delta = MockDelta()
            class MockChunk:
                choices = [MockChoice()]
            
            yield MockChunk()

        mock_gpt.side_effect = mock_stream_generator
        
        # Create a mock PDF file
        data = {
            'files': (BytesIO(b'fake pdf content'), 'test.pdf')
        }
        
        response = self.client.post('/api/upload-multiple',
                                  data=data,
                                  content_type='multipart/form-data')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("Generated summary", response.get_data(as_text=True))
    
    def test_upload_multiple_no_files_or_text(self):
        """Test upload with no files or text provided"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
        
        response = self.client.post('/api/upload-multiple')
        self.assertEqual(response.status_code, 500)
    
    def test_generate_quiz_unauthorized(self):
        """Test quiz generation without authentication"""
        response = self.client.post('/api/generate-quiz',
                                   data=json.dumps({'type': 'initial'}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 401)
    
    @patch('backend.main.generate_quiz_questions')
    def test_generate_quiz_success(self, mock_generate):
        """Test successful quiz generation"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['total_extracted_text'] = 'Test content'
            sess['content_hash'] = 'test_hash'
            sess['summary'] = 'Test summary for quiz'
        
        mock_generate.return_value = (
            [
                {
                    "id": "1",
                    "text": "Test question?",
                    "options": ["A", "B", "C", "D"],
                    "correctAnswer": 0,
                    "reason": "Test reason"
                }
            ], ['hash1']
        )
        
        response = self.client.post('/api/generate-quiz',
                                   data=json.dumps({'type': 'initial'}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 200)
        # Check that the expected text exists in the response data
        response_data = json.loads(response.data)
        self.assertTrue(response_data['success'])
        self.assertIn("Test question?", str(response_data['questions']))
    
    def test_generate_quiz_no_content(self):
        """Test quiz generation without content"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
        
        response = self.client.post('/api/generate-quiz',
                                   data=json.dumps({'type': 'initial'}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 400)
    
    @patch('backend.main.generate_quiz_questions')
    def test_generate_focused_quiz_success(self, mock_generate):
        """Test successful focused quiz generation"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['content_hash'] = 'test_hash'
            sess['summary'] = 'Test summary for quiz'
        
        mock_generate.return_value = (
            [
                {
                    "id": "2",
                    "text": "Focused question?",
                    "options": ["A", "B", "C", "D"],
                    "correctAnswer": 1,
                    "reason": "Focused reason"
                }
            ], ['hash2']
        )
        
        response = self.client.post('/api/generate-quiz',
                                   data=json.dumps({
                                       'type': 'focused',
                                       'incorrectQuestionIds': ['1'],
                                       'previousQuestions': [{'id': '1', 'text': 'prev'}],
                                       'isPreviewing': False
                                   }),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertTrue(response_data['success'])
        self.assertIn("Focused question?", str(response_data['questions']))
    
    @patch('backend.main.generate_quiz_questions')
    def test_generate_additional_quiz_success(self, mock_generate):
        """Test successful additional quiz generation"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['content_hash'] = 'test_hash'
            sess['summary'] = 'Test summary for quiz'
        
        mock_generate.return_value = (
            [
                {
                    "id": "3",
                    "text": "Additional question?",
                    "options": ["A", "B", "C", "D"],
                    "correctAnswer": 2,
                    "reason": "Additional reason"
                }
            ], ['hash3']
        )
        
        response = self.client.post('/api/generate-quiz',
                                   data=json.dumps({
                                       'type': 'additional',
                                       'incorrectQuestionIds': [],
                                       'previousQuestions': [{'id': '1', 'text': 'prev'}],
                                       'isPreviewing': True
                                   }),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertTrue(response_data['success'])
        self.assertIn("Additional question?", str(response_data['questions']))
    
    def test_get_quiz_unauthorized(self):
        """Test get quiz without authentication"""
        response = self.client.get('/api/get-quiz')
        self.assertEqual(response.status_code, 401)
    
    def test_get_quiz_success(self):
        """Test successful quiz retrieval"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['quiz_questions'] = [{'id': '1', 'text': 'Test?'}]
        
        response = self.client.get('/api/get-quiz')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
    
    def test_save_quiz_answers_unauthorized(self):
        """Test save quiz answers without authentication"""
        response = self.client.post('/api/save-quiz-answers')
        self.assertEqual(response.status_code, 401)
    
    @patch('backend.database.upsert_to_table')
    def test_save_quiz_answers_success(self, mock_db_upsert):
        """Test successful quiz answers saving"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['quiz_questions'] = [[{'id': '1', 'text': 'q1'}]]

        response = self.client.post('/api/save-quiz-answers',
                                  data=json.dumps({
                                      'userAnswers': {'1': 0},
                                      'submittedAnswers': {'1': True}
                                  }),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['success'])
    
    def test_clear_session_content_unauthorized(self):
        """Test clear session content without authentication"""
        response = self.client.post('/api/clear-session-content')
        self.assertEqual(response.status_code, 401)
    
    def test_clear_session_content_success(self):
        """Test successful session content clearing"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['summary'] = 'test'
            sess['quiz_questions'] = []
        
        response = self.client.post('/api/clear-session-content')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
    
    @patch('backend.main.get_question_sets_for_user')
    def test_get_question_sets_success(self, mock_get_sets):
        """Test successful question sets retrieval"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
        
        mock_get_sets.return_value = {
            "success": True,
            "data": [{"hash": "test", "short_summary": "Test"}]
        }
        
        response = self.client.get('/api/get-question-sets')
        self.assertEqual(response.status_code, 200)
    
    @patch('backend.main.get_full_study_set_data')
    def test_load_study_set_success(self, mock_load):
        """Test successful study set loading"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
        
        mock_load.return_value = {
            "success": True,
            "data": {
                "summary": "Test summary",
                "quiz_questions": []
            }
        }
        
        response = self.client.post('/api/load-study-set',
                                  data=json.dumps({'content_hash': 'test_hash'}),
                                  content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['success'])
    
    def test_get_all_quiz_questions_unauthorized(self):
        """Test get all quiz questions without authentication"""
        response = self.client.get('/api/get-all-quiz-questions')
        self.assertEqual(response.status_code, 401)

    def test_get_all_quiz_questions_success(self):
        """Test successful retrieval of all quiz questions"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['quiz_questions'] = [
                [{'id': '1', 'text': 'Q1', 'starred': False}],
                [{'id': '2', 'text': 'Q2', 'starred': True}]
            ]
        
        response = self.client.get('/api/get-all-quiz-questions')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['questions']), 2)

    def test_get_all_quiz_questions_empty(self):
        """Test retrieval of all quiz questions when none exist"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['quiz_questions'] = []
        
        response = self.client.get('/api/get-all-quiz-questions')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['questions']), 0)

    def test_toggle_star_question_unauthorized(self):
        """Test toggle star question without authentication"""
        response = self.client.post('/api/toggle-star-question',
                                   data=json.dumps({'questionId': 'test_id'}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 401)

    def test_toggle_star_question_missing_question_id(self):
        """Test toggle star question without questionId"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
        
        response = self.client.post('/api/toggle-star-question',
                                   data=json.dumps({}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Question ID is required')

    @patch('backend.main.update_question_starred_status')
    def test_toggle_star_question_success(self, mock_update_db):
        """Test successful star toggle"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['quiz_questions'] = [[
                {
                    'id': 'test_id',
                    'text': 'Test question',
                    'starred': False,
                    'hash': 'test_hash'
                }
            ]]
        
        mock_update_db.return_value = {'success': True}
        
        response = self.client.post('/api/toggle-star-question',
                                   data=json.dumps({'questionId': 'test_id'}),
                                   content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertTrue(data['question']['starred'])
        mock_update_db.assert_called_once_with('test_hash', True)

    @patch('backend.main.update_question_starred_status')
    def test_toggle_star_question_no_hash(self, mock_update_db):
        """Test star toggle for question without hash"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['quiz_questions'] = [[
                {
                    'id': 'test_id',
                    'text': 'Test question',
                    'starred': False
                    # No hash field
                }
            ]]
        
        response = self.client.post('/api/toggle-star-question',
                                   data=json.dumps({'questionId': 'test_id'}),
                                   content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertTrue(data['question']['starred'])
        # Should not call database update since no hash
        mock_update_db.assert_not_called()

    def test_toggle_star_question_not_found(self):
        """Test star toggle for non-existent question"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['quiz_questions'] = [[
                {'id': 'other_id', 'text': 'Other question'}
            ]]
        
        response = self.client.post('/api/toggle-star-question',
                                   data=json.dumps({'questionId': 'test_id'}),
                                   content_type='application/json')
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Question not found')

    @patch('backend.main.update_question_starred_status')
    def test_toggle_star_question_db_error(self, mock_update_db):
        """Test star toggle with database error"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['quiz_questions'] = [[
                {
                    'id': 'test_id',
                    'text': 'Test question',
                    'starred': False,
                    'hash': 'test_hash'
                }
            ]]
        
        mock_update_db.return_value = {'success': False, 'error': 'DB connection failed'}
        
        response = self.client.post('/api/toggle-star-question',
                                   data=json.dumps({'questionId': 'test_id'}),
                                   content_type='application/json')
        
        # Should still succeed since local state is updated
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertTrue(data['question']['starred'])

    def test_shuffle_quiz_unauthorized(self):
        """Test shuffle quiz without authentication"""
        response = self.client.post('/api/shuffle-quiz')
        self.assertEqual(response.status_code, 401)

    @patch('backend.main.random.shuffle')
    def test_shuffle_quiz_success(self, mock_shuffle):
        """Test successful quiz shuffle"""
        questions = [
            {'id': '1', 'text': 'Q1'},
            {'id': '2', 'text': 'Q2'},
            {'id': '3', 'text': 'Q3'}
        ]
        
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['quiz_questions'] = [questions.copy()]
        
        # Mock shuffle to reverse the list for predictable testing
        def mock_shuffle_func(lst):
            lst.reverse()
        mock_shuffle.side_effect = mock_shuffle_func
        
        response = self.client.post('/api/shuffle-quiz')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['questions']), 3)
        # Verify shuffle was called
        mock_shuffle.assert_called_once()

    def test_shuffle_quiz_empty(self):
        """Test shuffle quiz with no questions"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['quiz_questions'] = []
        
        response = self.client.post('/api/shuffle-quiz')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['questions']), 0)

    def test_start_starred_quiz_unauthorized(self):
        """Test start starred quiz without authentication"""
        response = self.client.post('/api/start-starred-quiz')
        self.assertEqual(response.status_code, 401)

    def test_start_starred_quiz_success(self):
        """Test successful starred quiz start"""
        questions = [
            {'id': '1', 'text': 'Q1', 'starred': True},
            {'id': '2', 'text': 'Q2', 'starred': False},
            {'id': '3', 'text': 'Q3', 'starred': True}
        ]
        
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['quiz_questions'] = [questions.copy()]
        
        response = self.client.post('/api/start-starred-quiz')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['questions']), 2)
        # Verify only starred questions are returned
        for question in data['questions']:
            self.assertTrue(question.get('starred', False))

    def test_start_starred_quiz_no_starred_questions(self):
        """Test starred quiz start with no starred questions"""
        questions = [
            {'id': '1', 'text': 'Q1', 'starred': False},
            {'id': '2', 'text': 'Q2', 'starred': False}
        ]
        
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['quiz_questions'] = [questions.copy()]
        
        response = self.client.post('/api/start-starred-quiz')
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'No starred questions found to start a quiz.')

    def test_start_starred_quiz_empty_session(self):
        """Test starred quiz start with empty session"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['quiz_questions'] = []
        
        response = self.client.post('/api/start-starred-quiz')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['questions']), 0)

    def test_start_starred_quiz_default_starred_value(self):
        """Test starred quiz start with questions missing starred field"""
        questions = [
            {'id': '1', 'text': 'Q1'},  # No starred field
            {'id': '2', 'text': 'Q2', 'starred': True}
        ]
        
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['quiz_questions'] = [questions.copy()]
        
        response = self.client.post('/api/start-starred-quiz')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['questions']), 1)
        self.assertEqual(data['questions'][0]['id'], '2')

    @patch('backend.database.star_all_questions_by_hashes')
    def test_star_all_questions_success(self, mock_star_all):
        """Test successfully starring all questions"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['quiz_questions'] = [[
                {'id': '1', 'starred': False, 'text': 'Question 1', 'hash': 'hash1'},
                {'id': '2', 'starred': False, 'text': 'Question 2', 'hash': 'hash2'}
            ]]
        
        mock_star_all.return_value = {'success': True, 'updated_count': 2}
        
        response = self.client.post('/api/star-all-questions',
                                   data=json.dumps({'action': 'star'}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['questions']), 2)
        self.assertTrue(all(q['starred'] for q in data['questions']))
        mock_star_all.assert_called_once_with(['hash1', 'hash2'], True)

    def test_star_all_questions_unauthorized(self):
        """Test starring all questions without authentication"""
        response = self.client.post('/api/star-all-questions',
                                   data=json.dumps({'action': 'star'}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Unauthorized')

    def test_star_all_questions_invalid_action(self):
        """Test starring all questions with invalid action"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['quiz_questions'] = [[]]
        
        response = self.client.post('/api/star-all-questions',
                                   data=json.dumps({'action': 'invalid'}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Invalid action. Must be "star" or "unstar"')

    def test_star_all_questions_default_action(self):
        """Test starring all questions with default action (star)"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['quiz_questions'] = [[
                {'id': '1', 'starred': False, 'text': 'Question 1', 'hash': 'hash1'}
            ]]
        
        response = self.client.post('/api/star-all-questions',
                                   data=json.dumps({}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertTrue(data['questions'][0]['starred'])

    def test_star_all_questions_empty_quiz(self):
        """Test starring all questions with no quiz questions"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['quiz_questions'] = []
        
        response = self.client.post('/api/star-all-questions',
                                   data=json.dumps({'action': 'star'}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['questions'], [])

    @patch('backend.database.star_all_questions_by_hashes')
    def test_star_all_questions_database_error(self, mock_star_all):
        """Test starring all questions with database error"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['quiz_questions'] = [[
                {'id': '1', 'starred': False, 'text': 'Question 1', 'hash': 'hash1'}
            ]]
        
        mock_star_all.return_value = {'success': False, 'error': 'Database error'}
        
        response = self.client.post('/api/star-all-questions',
                                   data=json.dumps({'action': 'star'}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])  # Should still succeed in session even if DB fails
        self.assertTrue(data['questions'][0]['starred'])

    @patch('backend.database.star_all_questions_by_hashes')
    def test_unstar_all_questions_success(self, mock_star_all):
        """Test successfully unstarring all questions"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['quiz_questions'] = [[
                {'id': '1', 'starred': True, 'text': 'Question 1', 'hash': 'hash1'},
                {'id': '2', 'starred': True, 'text': 'Question 2', 'hash': 'hash2'}
            ]]
        
        mock_star_all.return_value = {'success': True, 'updated_count': 2}
        
        response = self.client.post('/api/star-all-questions',
                                   data=json.dumps({'action': 'unstar'}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['questions']), 2)
        self.assertTrue(all(not q['starred'] for q in data['questions']))
        mock_star_all.assert_called_once_with(['hash1', 'hash2'], False)

    @patch('backend.database.star_all_questions_by_hashes')
    def test_unstar_all_questions_no_hashes(self, mock_star_all):
        """Test unstarring all questions when questions have no hashes"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['quiz_questions'] = [[
                {'id': '1', 'starred': True, 'text': 'Question 1'},  # No hash
                {'id': '2', 'starred': True, 'text': 'Question 2'}   # No hash
            ]]
        
        response = self.client.post('/api/star-all-questions',
                                   data=json.dumps({'action': 'unstar'}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertTrue(all(not q['starred'] for q in data['questions']))
        mock_star_all.assert_not_called()  # Should not be called if no hashes

    def test_serve_index(self):
        """Test serving index page"""
        with patch('backend.main.send_from_directory') as mock_send:
            mock_send.return_value = "index.html content"
            response = self.client.get('/')
            self.assertEqual(response.status_code, 200)
    
    def test_serve_favicon(self):
        """Test serving favicon"""
        with patch('backend.main.send_from_directory') as mock_send:
            mock_send.return_value = "favicon content"
            response = self.client.get('/favicon.png')
            self.assertEqual(response.status_code, 200)
            mock_send.assert_called_with(self.app.static_folder, 'favicon.png', mimetype='image/png')
    
    def test_serve_static(self):
        """Test serving static files"""
        with patch('backend.main.send_from_directory') as mock_send:
            mock_send.return_value = "static content"
            # Request a path that doesn't exist to test the fallback to index.html
            response = self.client.get('/some/react/route')
            self.assertEqual(response.status_code, 200)
            mock_send.assert_called_with(self.app.static_folder, 'index.html')

if __name__ == '__main__':
    unittest.main() 