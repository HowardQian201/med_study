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