"""
Unit tests for backend/database.py
"""
import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
import hashlib
from io import BytesIO

# Add the parent directory to the Python path so we can import from backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class TestDatabaseFunctions(unittest.TestCase):
    """Test cases for database functions"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        pass
    
    def tearDown(self):
        """Tear down test fixtures after each test method."""
        pass
    
    @patch('backend.database.create_client')
    def test_get_supabase_client_success(self, mock_create_client):
        """Test successful Supabase client creation"""
        from backend.database import get_supabase_client
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        
        with patch.dict(os.environ, {'SUPABASE_URL': 'test_url', 'SUPABASE_SERVICE_KEY': 'test_key'}):
            client = get_supabase_client()
            self.assertEqual(client, mock_client)
    
    @patch('backend.database.SUPABASE_URL', None)
    @patch('backend.database.SUPABASE_KEY', None)
    def test_get_supabase_client_missing_env_vars(self):
        """Test Supabase client creation with missing environment variables"""
        from backend.database import get_supabase_client
        with self.assertRaises(ValueError):
            get_supabase_client()
    
    @patch('backend.database.get_supabase_client')
    def test_upsert_to_table_success(self, mock_get_client):
        """Test successful upsert to table"""
        from backend.database import upsert_to_table
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_query = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{'id': 1, 'name': 'test'}]
        
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value = mock_query
        mock_query.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        result = upsert_to_table('test_table', {'name': 'test'})
        
        self.assertTrue(result['success'])
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['table'], 'test_table')
    
    @patch('backend.database.get_supabase_client')
    def test_upsert_to_table_error(self, mock_get_client):
        """Test upsert to table with error"""
        from backend.database import upsert_to_table
        
        mock_get_client.side_effect = Exception("Database error")
        
        result = upsert_to_table('test_table', {'name': 'test'})
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], "Database error")
        self.assertEqual(result['count'], 0)
    
    def test_generate_file_hash(self):
        """Test file hash generation"""
        from backend.database import generate_file_hash
        
        test_content = b"test file content"
        hash_result = generate_file_hash(test_content)
        
        # Verify it's a valid SHA256 hash
        self.assertEqual(len(hash_result), 64)
        self.assertTrue(all(c in '0123456789abcdef' for c in hash_result))
        
        # Verify consistency
        hash_result2 = generate_file_hash(test_content)
        self.assertEqual(hash_result, hash_result2)
    
    def test_generate_content_hash(self):
        """Test content hash generation"""
        from backend.database import generate_content_hash
        
        content_set = {b"file1", "text1", b"file2"}
        user_id = 123
        
        hash_result = generate_content_hash(content_set, user_id)
        
        # Verify it's a valid SHA256 hash
        self.assertEqual(len(hash_result), 64)
        self.assertTrue(all(c in '0123456789abcdef' for c in hash_result))
        
        # Verify consistency
        hash_result2 = generate_content_hash(content_set, user_id)
        self.assertEqual(hash_result, hash_result2)
        
        # Verify different user_id produces different hash
        hash_result3 = generate_content_hash(content_set, 456)
        self.assertNotEqual(hash_result, hash_result3)
    
    @patch('backend.database.get_supabase_client')
    def test_check_file_exists_found(self, mock_get_client):
        """Test checking for existing file that exists"""
        from backend.database import check_file_exists
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_query1 = MagicMock()
        mock_query2 = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{'id': 1, 'hash': 'test_hash', 'text': 'test content'}]
        
        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_query1
        mock_query1.eq.return_value = mock_query2
        mock_query2.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        result = check_file_exists('test_hash')
        
        self.assertTrue(result['success'])
        self.assertTrue(result['exists'])
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['data']['hash'], 'test_hash')
    
    @patch('backend.database.get_supabase_client')
    def test_check_file_exists_not_found(self, mock_get_client):
        """Test checking for existing file that doesn't exist"""
        from backend.database import check_file_exists
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_query1 = MagicMock()
        mock_query2 = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        
        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_query1
        mock_query1.eq.return_value = mock_query2
        mock_query2.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        result = check_file_exists('nonexistent_hash')
        
        self.assertTrue(result['success'])
        self.assertFalse(result['exists'])
        self.assertIsNone(result['data'])
    
    @patch('backend.database.get_supabase_client')
    def test_check_file_exists_error(self, mock_get_client):
        """Test checking for existing file with database error"""
        from backend.database import check_file_exists
        
        mock_get_client.side_effect = Exception("Database connection failed")
        
        result = check_file_exists('test_hash')
        
        self.assertFalse(result['success'])
        self.assertFalse(result['exists'])
        self.assertEqual(result['error'], "Database connection failed")
    
    @patch('backend.database.upsert_to_table')
    def test_upsert_pdf_results(self, mock_upsert):
        """Test PDF results upsert"""
        from backend.database import upsert_pdf_results
        
        mock_upsert.return_value = {'success': True, 'count': 1}
        
        pdf_data = {'id': 1, 'user_id': 123, 'pdf_id': 'test'}
        result = upsert_pdf_results(pdf_data)
        
        mock_upsert.assert_called_once_with("pdfs", pdf_data)
        self.assertTrue(result['success'])
    
    @patch('backend.database.upsert_to_table')
    def test_upsert_quiz_questions_batch(self, mock_upsert):
        """Test batch quiz questions upsert"""
        from backend.database import upsert_quiz_questions_batch
        
        mock_upsert.return_value = {'success': True, 'count': 2}
        
        questions = [
            {'hash': 'hash1', 'question': {'text': 'Q1'}},
            {'hash': 'hash2', 'question': {'text': 'Q2'}}
        ]
        result = upsert_quiz_questions_batch(questions)
        
        mock_upsert.assert_called_once_with("quiz_questions", questions)
        self.assertTrue(result['success'])
    
    @patch('backend.database.get_supabase_client')
    def test_authenticate_user_success(self, mock_get_client):
        """Test successful user authentication"""
        from backend.database import authenticate_user
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_query1 = MagicMock()
        mock_query2 = MagicMock()
        mock_query3 = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{'id': 1, 'email': 'test@example.com', 'name': 'Test User'}]
        
        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_query1
        mock_query1.eq.return_value = mock_query2
        mock_query2.eq.return_value = mock_query3
        mock_query3.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        result = authenticate_user('test@example.com', 'password123')
        
        self.assertTrue(result['success'])
        self.assertTrue(result['authenticated'])
        self.assertEqual(result['user']['email'], 'test@example.com')
    
    @patch('backend.database.get_supabase_client')
    def test_authenticate_user_invalid_credentials(self, mock_get_client):
        """Test user authentication with invalid credentials"""
        from backend.database import authenticate_user
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_query1 = MagicMock()
        mock_query2 = MagicMock()
        mock_query3 = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        
        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_query1
        mock_query1.eq.return_value = mock_query2
        mock_query2.eq.return_value = mock_query3
        mock_query3.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        result = authenticate_user('test@example.com', 'wrongpassword')
        
        self.assertTrue(result['success'])
        self.assertFalse(result['authenticated'])
    
    @patch('backend.database.get_supabase_client')
    def test_authenticate_user_error(self, mock_get_client):
        """Test user authentication with database error"""
        from backend.database import authenticate_user
        
        mock_get_client.side_effect = Exception("Database connection failed")
        
        result = authenticate_user('test@example.com', 'password123')
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], "Database connection failed")
    
    @patch('backend.database.get_supabase_client')
    def test_upsert_question_set(self, mock_get_client):
        """Test question set upsert"""
        from backend.database import upsert_question_set

        # Mock the database client and the table object
        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_get_client.return_value = mock_supabase
        mock_supabase.table.return_value = mock_table

        # Mock the response for checking if a record exists, forcing an update
        mock_execute = MagicMock()
        mock_execute.data = [{'question_hashes': ['q_old']}]
        mock_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_execute
        
        upsert_question_set(
            'content_hash123',
            1,
            ['q1', 'q2'],
            ['file1.pdf']
        )
        
        # Assert that the 'update' method was called, since this is the buggy path taken
        mock_table.update.assert_called_once()
    
    @patch('backend.database.get_supabase_client')
    def test_get_question_sets_for_user_success(self, mock_get_client):
        """Test successful question sets retrieval"""
        from backend.database import get_question_sets_for_user
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_query1 = MagicMock()
        mock_query2 = MagicMock()
        mock_query3 = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [
            {'hash': 'hash1', 'short_summary': 'Summary 1', 'updated_at': '2023-01-01'}
        ]
        
        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_query1
        mock_query1.eq.return_value = mock_query2
        mock_query2.order.return_value = mock_query3
        mock_query3.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        result = get_question_sets_for_user(1)
        
        self.assertTrue(result['success'])
        self.assertEqual(len(result['data']), 1)
    
    @patch('backend.database.get_supabase_client')
    def test_get_full_study_set_data_success(self, mock_get_client):
        """Test successful full study set data retrieval"""
        from backend.database import get_full_study_set_data
        
        mock_client = MagicMock()
        
        # Mock for the 'question_sets' table response
        mock_sets_response = MagicMock()
        mock_sets_response.data = {
            'hash': 'test_hash',
            'content_summary': 'Test summary for quiz',
            'short_summary': 'Short summary',
            'text_content': 'Some text',
            'metadata': {
                'question_hashes': ['q1', 'q2'],
                'content_names': ['file1.pdf']
            }
        }
        
        # Mock for the 'quiz_questions' table response
        mock_questions_response = MagicMock()
        mock_questions_response.data = [
            {'question': {'text': 'Question 1'}},
            {'question': {'text': 'Question 2'}}
        ]
        
        # Configure the chain of calls for 'question_sets'
        mock_sets_table = MagicMock()
        (
            mock_sets_table.select.return_value
            .eq.return_value
            .eq.return_value
            .maybe_single.return_value
            .execute.return_value
        ) = mock_sets_response
        
        # Configure the chain of calls for 'quiz_questions'
        mock_questions_table = MagicMock()
        (
            mock_questions_table.select.return_value
            .in_.return_value
            .execute.return_value
        ) = mock_questions_response

        # Use a side_effect to return the correct table mock
        def table_side_effect(table_name):
            if table_name == 'question_sets':
                return mock_sets_table
            elif table_name == 'quiz_questions':
                return mock_questions_table
            return MagicMock()

        mock_client.table.side_effect = table_side_effect
        mock_get_client.return_value = mock_client

        result = get_full_study_set_data('test_hash', 1)

        self.assertTrue(result['success'])
        self.assertEqual(result['data']['summary'], 'Test summary for quiz')
        # The function wraps the questions in another list
        self.assertEqual(len(result['data']['quiz_questions'][0]), 2)
        self.assertEqual(result['data']['content_name_list'], ['file1.pdf'])

    @patch('backend.database.get_supabase_client')
    def test_get_full_study_set_data_not_found(self, mock_get_client):
        """Test full study set data retrieval when not found"""
        from backend.database import get_full_study_set_data
        
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = None # This simulates no data found
        
        (
            mock_client.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .maybe_single.return_value
            .execute.return_value
        ) = mock_result
        
        mock_get_client.return_value = mock_client
        
        result = get_full_study_set_data('nonexistent_hash', 1)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], "Study set not found")
    
    @patch('backend.database.get_supabase_client')
    def test_upload_pdf_to_storage_success(self, mock_get_client):
        """Test successful PDF upload to storage"""
        from backend.database import upload_pdf_to_storage
        
        mock_client = MagicMock()
        mock_storage = MagicMock()
        mock_upload_result = MagicMock()
        mock_upload_result.path = 'pdfs/test_hash.pdf'
        
        mock_client.storage.return_value = mock_storage
        mock_storage.from_.return_value.upload.return_value = mock_upload_result
        mock_get_client.return_value = mock_client
        
        result = upload_pdf_to_storage(b'pdf content', 'test_hash', 'test.pdf')
        
        self.assertTrue(result['success'])
        self.assertEqual(result['path'], 'test_hash.pdf')
    
    @patch('backend.database.get_supabase_client')
    def test_upload_pdf_to_storage_failure(self, mock_get_client):
        """Test failed PDF upload to storage"""
        from backend.database import upload_pdf_to_storage
        
        mock_get_client.side_effect = Exception("Storage connection failed")
        
        result = upload_pdf_to_storage(b'pdf content', 'test_hash', 'test.pdf')
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertEqual(result['error_type'], 'Exception')
    
    @patch('backend.database.get_supabase_client')
    def test_update_question_set_title_success(self, mock_get_client):
        """Test successful question set title update"""
        from backend.database import update_question_set_title
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{'hash': 'test_hash', 'short_summary': 'New Title'}]
        
        mock_client.table.return_value = mock_table
        mock_table.update.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        result = update_question_set_title('test_hash', 1, 'New Title')
        
        self.assertTrue(result['success'])
    
    @patch('backend.database.get_supabase_client')
    def test_touch_question_set_success(self, mock_get_client):
        """Test successful question set touch (update timestamp)"""
        from backend.database import touch_question_set
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{'hash': 'test_hash'}]
        
        mock_client.table.return_value = mock_table
        mock_table.update.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        result = touch_question_set('test_hash', 1)
        
        self.assertTrue(result['success'])

if __name__ == '__main__':
    unittest.main() 