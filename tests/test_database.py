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

        # Test with is_quiz_mode = True
        hash_result_quiz = generate_content_hash(content_set, user_id, is_quiz_mode=True)
        self.assertEqual(len(hash_result_quiz), 64)
        self.assertTrue(all(c in '0123456789abcdef' for c in hash_result_quiz))
        self.assertNotEqual(hash_result, hash_result_quiz)

        # Test with is_quiz_mode = False explicitly
        hash_result_learning = generate_content_hash(content_set, user_id, is_quiz_mode=False)
        self.assertEqual(len(hash_result_learning), 64)
        self.assertTrue(all(c in '0123456789abcdef' for c in hash_result_learning))
        self.assertEqual(hash_result, hash_result_learning)
    
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
            ['file1.pdf'],
            'Test summary',
            'Short Test Summary',
            'Full Test Summary',
            True # is_quiz
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
            {'hash': 'hash1', 'short_summary': 'Summary 1', 'created_at': '2023-01-01', 'is_quiz': True},
            {'hash': 'hash2', 'short_summary': 'Summary 2', 'created_at': '2023-01-02', 'is_quiz': False}
        ]
        
        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_query1
        mock_query1.eq.return_value = mock_query2
        mock_query2.order.return_value = mock_query3
        mock_query3.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        result = get_question_sets_for_user(1)
        
        self.assertTrue(result['success'])
        self.assertEqual(len(result['data']), 2)
    
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
            },
            'is_quiz': True
        }
        
        # Mock for the 'quiz_questions' table response
        mock_questions_response = MagicMock()
        mock_questions_response.data = [
            {'question': {'text': 'Question 1'}, 'starred': True, 'hash': 'q1'},
            {'question': {'text': 'Question 2'}, 'starred': False, 'hash': 'q2'}
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
        print(result)

        self.assertTrue(result['success'])
        self.assertEqual(result['data']['summary'], 'Test summary for quiz')
        # The function wraps the questions in another list
        self.assertEqual(len(result['data']['quiz_questions'][0]), 2)
        self.assertEqual(result['data']['content_name_list'], ['file1.pdf'])
        self.assertEqual(result['data']['is_quiz'], True)

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
        """Test successful question set touch"""
        from backend.database import touch_question_set
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{'id': 1, 'hash': 'test_hash'}]
        
        mock_client.table.return_value = mock_table
        # Mock the complete chain: update().eq().eq().execute()
        mock_table.update.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        result = touch_question_set('test_hash', 1)
        
        self.assertTrue(result['success'])
        self.assertIn('data', result)  # Function returns 'data', not 'count'

    @patch('backend.database.get_supabase_client')
    def test_update_question_starred_status_success_star(self, mock_get_client):
        """Test successful update of question starred status to True"""
        from backend.database import update_question_starred_status
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_query1 = MagicMock()
        mock_query2 = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{'hash': 'test_hash', 'starred': True}]
        
        mock_client.table.return_value = mock_table
        mock_table.update.return_value = mock_query1
        mock_query1.eq.return_value = mock_query2
        mock_query2.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        result = update_question_starred_status('test_hash', True)
        
        self.assertTrue(result['success'])
        self.assertTrue(result['data']['starred'])
        mock_table.update.assert_called_once_with({'starred': True})
        mock_query1.eq.assert_called_once_with('hash', 'test_hash')

    @patch('backend.database.get_supabase_client')
    def test_update_question_starred_status_success_unstar(self, mock_get_client):
        """Test successful update of question starred status to False"""
        from backend.database import update_question_starred_status
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_query1 = MagicMock()
        mock_query2 = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{'hash': 'test_hash', 'starred': False}]
        
        mock_client.table.return_value = mock_table
        mock_table.update.return_value = mock_query1
        mock_query1.eq.return_value = mock_query2
        mock_query2.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        result = update_question_starred_status('test_hash', False)
        
        self.assertTrue(result['success'])
        self.assertFalse(result['data']['starred'])
        mock_table.update.assert_called_once_with({'starred': False})

    @patch('backend.database.get_supabase_client')
    def test_update_question_starred_status_not_found(self, mock_get_client):
        """Test update of question starred status for non-existent question"""
        from backend.database import update_question_starred_status
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_query1 = MagicMock()
        mock_query2 = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []  # No data returned means question not found
        
        mock_client.table.return_value = mock_table
        mock_table.update.return_value = mock_query1
        mock_query1.eq.return_value = mock_query2
        mock_query2.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        result = update_question_starred_status('nonexistent_hash', True)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Question not found or status already set.')

    @patch('backend.database.get_supabase_client')
    def test_update_question_starred_status_database_error(self, mock_get_client):
        """Test update of question starred status with database error"""
        from backend.database import update_question_starred_status
        
        mock_get_client.side_effect = Exception("Database connection failed")
        
        result = update_question_starred_status('test_hash', True)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Database connection failed')

    @patch('backend.database.get_supabase_client')
    def test_update_question_starred_status_empty_hash(self, mock_get_client):
        """Test update of question starred status with empty hash"""
        from backend.database import update_question_starred_status
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_query1 = MagicMock()
        mock_query2 = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        
        mock_client.table.return_value = mock_table
        mock_table.update.return_value = mock_query1
        mock_query1.eq.return_value = mock_query2
        mock_query2.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        result = update_question_starred_status('', True)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Question not found or status already set.')

    @patch('backend.database.get_supabase_client')
    def test_update_question_starred_status_none_hash(self, mock_get_client):
        """Test update of question starred status with None hash"""
        from backend.database import update_question_starred_status
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_query1 = MagicMock()
        mock_query2 = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        
        mock_client.table.return_value = mock_table
        mock_table.update.return_value = mock_query1
        mock_query1.eq.return_value = mock_query2
        mock_query2.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        result = update_question_starred_status(None, True)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Question not found or status already set.')

    @patch('backend.database.get_supabase_client')
    def test_update_question_starred_status_with_starred_field_in_data(self, mock_get_client):
        """Test update of question starred status with starred field verification"""
        from backend.database import update_question_starred_status
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_query1 = MagicMock()
        mock_query2 = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{'hash': 'test_hash', 'starred': True, 'question': {'text': 'Test Q'}}]
        
        mock_client.table.return_value = mock_table
        mock_table.update.return_value = mock_query1
        mock_query1.eq.return_value = mock_query2
        mock_query2.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        result = update_question_starred_status('test_hash', True)
        
        self.assertTrue(result['success'])
        self.assertIn('data', result)
        self.assertEqual(result['data']['hash'], 'test_hash')
        self.assertTrue(result['data']['starred'])

    @patch('backend.database.get_supabase_client')
    def test_star_all_questions_by_hashes_success(self, mock_get_client):
        """Test successfully updating starred status for multiple questions"""
        from backend.database import star_all_questions_by_hashes
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_query1 = MagicMock()
        mock_query2 = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [
            {'hash': 'hash1', 'starred': True},
            {'hash': 'hash2', 'starred': True}
        ]
        
        mock_client.table.return_value = mock_table
        mock_table.update.return_value = mock_query1
        mock_query1.in_.return_value = mock_query2
        mock_query2.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        result = star_all_questions_by_hashes(['hash1', 'hash2'], True)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['updated_count'], 2)
        self.assertEqual(result['requested_count'], 2)
        mock_table.update.assert_called_once_with({'starred': True})
        mock_query1.in_.assert_called_once_with('hash', ['hash1', 'hash2'])

    @patch('backend.database.get_supabase_client')
    def test_star_all_questions_by_hashes_empty_list(self, mock_get_client):
        """Test bulk star update with empty hash list"""
        from backend.database import star_all_questions_by_hashes
        
        result = star_all_questions_by_hashes([], True)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['updated_count'], 0)
        self.assertEqual(result['requested_count'], 0)
        self.assertEqual(result['data'], [])
        mock_get_client.assert_not_called()

    @patch('backend.database.get_supabase_client')
    def test_star_all_questions_by_hashes_unstar(self, mock_get_client):
        """Test successfully unstarring multiple questions"""
        from backend.database import star_all_questions_by_hashes
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_query1 = MagicMock()
        mock_query2 = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [
            {'hash': 'hash1', 'starred': False},
            {'hash': 'hash2', 'starred': False},
            {'hash': 'hash3', 'starred': False}
        ]
        
        mock_client.table.return_value = mock_table
        mock_table.update.return_value = mock_query1
        mock_query1.in_.return_value = mock_query2
        mock_query2.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        result = star_all_questions_by_hashes(['hash1', 'hash2', 'hash3'], False)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['updated_count'], 3)
        self.assertEqual(result['requested_count'], 3)
        mock_table.update.assert_called_once_with({'starred': False})

    @patch('backend.database.get_supabase_client')
    def test_star_all_questions_by_hashes_partial_update(self, mock_get_client):
        """Test bulk star update where only some questions are found"""
        from backend.database import star_all_questions_by_hashes
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_query1 = MagicMock()
        mock_query2 = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{'hash': 'hash1', 'starred': True}]  # Only 1 of 3 found
        
        mock_client.table.return_value = mock_table
        mock_table.update.return_value = mock_query1
        mock_query1.in_.return_value = mock_query2
        mock_query2.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        result = star_all_questions_by_hashes(['hash1', 'hash2', 'hash3'], True)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['updated_count'], 1)
        self.assertEqual(result['requested_count'], 3)

    @patch('backend.database.get_supabase_client')
    def test_star_all_questions_by_hashes_exception(self, mock_get_client):
        """Test bulk star update with database exception"""
        from backend.database import star_all_questions_by_hashes
        
        mock_get_client.side_effect = Exception('Database connection failed')
        
        result = star_all_questions_by_hashes(['hash1', 'hash2'], True)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Database connection failed')
        self.assertEqual(result['updated_count'], 0)
        self.assertEqual(result['requested_count'], 2)

    @patch('backend.database.get_supabase_client')
    def test_star_all_questions_by_hashes_no_data_response(self, mock_get_client):
        """Test bulk star update with None response data"""
        from backend.database import star_all_questions_by_hashes
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_query1 = MagicMock()
        mock_query2 = MagicMock()
        mock_result = MagicMock()
        mock_result.data = None
        
        mock_client.table.return_value = mock_table
        mock_table.update.return_value = mock_query1
        mock_query1.in_.return_value = mock_query2
        mock_query2.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        result = star_all_questions_by_hashes(['hash1'], True)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['updated_count'], 0)
        self.assertEqual(result['requested_count'], 1)

    @patch('backend.database.get_supabase_client')
    def test_star_all_questions_by_hashes_no_data_response(self, mock_get_client):
        """Test star_all_questions_by_hashes when database returns no data"""
        from backend.database import star_all_questions_by_hashes
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_query1 = MagicMock()
        mock_query2 = MagicMock()
        mock_result = MagicMock()
        mock_result.data = None
        
        mock_client.table.return_value = mock_table
        mock_table.update.return_value = mock_query1
        mock_query1.in_.return_value = mock_query2
        mock_query2.execute.return_value = mock_result
        mock_get_client.return_value = mock_client
        
        result = star_all_questions_by_hashes(['hash1', 'hash2'], True)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['updated_count'], 0)
        self.assertEqual(result['requested_count'], 2)

    @patch('backend.database.get_supabase_client')
    def test_delete_question_set_and_questions_success(self, mock_get_client):
        """Test successful deletion of question set and associated questions"""
        from backend.database import delete_question_set_and_questions
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        
        # Mock the question set retrieval
        mock_select_query = MagicMock()
        mock_eq_query1 = MagicMock()
        mock_eq_query2 = MagicMock()
        mock_maybe_single_query = MagicMock()
        mock_set_result = MagicMock()
        mock_set_result.data = {
            'metadata': {
                'question_hashes': ['q_hash1', 'q_hash2', 'q_hash3']
            }
        }
        
        # Mock the questions deletion
        mock_questions_delete_query = MagicMock()
        mock_questions_in_query = MagicMock()
        mock_questions_result = MagicMock()
        mock_questions_result.data = [{'hash': 'q_hash1'}, {'hash': 'q_hash2'}, {'hash': 'q_hash3'}]
        
        # Mock the question set deletion
        mock_set_delete_query = MagicMock()
        mock_set_eq_query1 = MagicMock()
        mock_set_eq_query2 = MagicMock()
        mock_set_delete_result = MagicMock()
        mock_set_delete_result.data = [{'hash': 'test_hash'}]
        
        def table_side_effect(table_name):
            if table_name == 'question_sets':
                mock_table.select.return_value = mock_select_query
                mock_select_query.eq.return_value = mock_eq_query1
                mock_eq_query1.eq.return_value = mock_eq_query2
                mock_eq_query2.maybe_single.return_value = mock_maybe_single_query
                mock_maybe_single_query.execute.return_value = mock_set_result
                
                mock_table.delete.return_value = mock_set_delete_query
                mock_set_delete_query.eq.return_value = mock_set_eq_query1
                mock_set_eq_query1.eq.return_value = mock_set_eq_query2
                mock_set_eq_query2.execute.return_value = mock_set_delete_result
                
            elif table_name == 'quiz_questions':
                mock_table.delete.return_value = mock_questions_delete_query
                mock_questions_delete_query.in_.return_value = mock_questions_in_query
                mock_questions_in_query.execute.return_value = mock_questions_result
                
            return mock_table
        
        mock_client.table.side_effect = table_side_effect
        mock_get_client.return_value = mock_client
        
        result = delete_question_set_and_questions('test_hash', 123)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['deleted_questions'], 3)
        self.assertEqual(result['deleted_sets'], 1)

    @patch('backend.database.get_supabase_client')
    def test_delete_question_set_and_questions_not_found(self, mock_get_client):
        """Test deletion when question set is not found"""
        from backend.database import delete_question_set_and_questions
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_select_query = MagicMock()
        mock_eq_query1 = MagicMock()
        mock_eq_query2 = MagicMock()
        mock_maybe_single_query = MagicMock()
        mock_set_result = MagicMock()
        mock_set_result.data = None  # No question set found
        
        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select_query
        mock_select_query.eq.return_value = mock_eq_query1
        mock_eq_query1.eq.return_value = mock_eq_query2
        mock_eq_query2.maybe_single.return_value = mock_maybe_single_query
        mock_maybe_single_query.execute.return_value = mock_set_result
        mock_get_client.return_value = mock_client
        
        result = delete_question_set_and_questions('nonexistent_hash', 123)
        
        self.assertFalse(result['success'])
        self.assertIn("Question set not found", result['error'])

    @patch('backend.database.get_supabase_client')
    def test_delete_question_set_and_questions_no_questions(self, mock_get_client):
        """Test deletion of question set with no associated questions"""
        from backend.database import delete_question_set_and_questions
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        
        # Mock the question set retrieval with empty question_hashes
        mock_select_query = MagicMock()
        mock_eq_query1 = MagicMock()
        mock_eq_query2 = MagicMock()
        mock_maybe_single_query = MagicMock()
        mock_set_result = MagicMock()
        mock_set_result.data = {
            'metadata': {
                'question_hashes': []  # No questions
            }
        }
        
        # Mock the question set deletion
        mock_set_delete_query = MagicMock()
        mock_set_eq_query1 = MagicMock()
        mock_set_eq_query2 = MagicMock()
        mock_set_delete_result = MagicMock()
        mock_set_delete_result.data = [{'hash': 'test_hash'}]
        
        def table_side_effect(table_name):
            if table_name == 'question_sets':
                mock_table.select.return_value = mock_select_query
                mock_select_query.eq.return_value = mock_eq_query1
                mock_eq_query1.eq.return_value = mock_eq_query2
                mock_eq_query2.maybe_single.return_value = mock_maybe_single_query
                mock_maybe_single_query.execute.return_value = mock_set_result
                
                mock_table.delete.return_value = mock_set_delete_query
                mock_set_delete_query.eq.return_value = mock_set_eq_query1
                mock_set_eq_query1.eq.return_value = mock_set_eq_query2
                mock_set_eq_query2.execute.return_value = mock_set_delete_result
                
            return mock_table
        
        mock_client.table.side_effect = table_side_effect
        mock_get_client.return_value = mock_client
        
        result = delete_question_set_and_questions('test_hash', 123)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['deleted_questions'], 0)
        self.assertEqual(result['deleted_sets'], 1)

    @patch('backend.database.get_supabase_client')
    def test_delete_question_set_and_questions_set_deletion_failed(self, mock_get_client):
        """Test when question set deletion fails"""
        from backend.database import delete_question_set_and_questions
        
        mock_client = MagicMock()
        mock_table = MagicMock()
        
        # Mock the question set retrieval
        mock_select_query = MagicMock()
        mock_eq_query1 = MagicMock()
        mock_eq_query2 = MagicMock()
        mock_maybe_single_query = MagicMock()
        mock_set_result = MagicMock()
        mock_set_result.data = {
            'metadata': {
                'question_hashes': ['q_hash1']
            }
        }
        
        # Mock the questions deletion (successful)
        mock_questions_delete_query = MagicMock()
        mock_questions_in_query = MagicMock()
        mock_questions_result = MagicMock()
        mock_questions_result.data = [{'hash': 'q_hash1'}]
        
        # Mock the question set deletion (failed)
        mock_set_delete_query = MagicMock()
        mock_set_eq_query1 = MagicMock()
        mock_set_eq_query2 = MagicMock()
        mock_set_delete_result = MagicMock()
        mock_set_delete_result.data = None  # Deletion failed
        
        def table_side_effect(table_name):
            if table_name == 'question_sets':
                mock_table.select.return_value = mock_select_query
                mock_select_query.eq.return_value = mock_eq_query1
                mock_eq_query1.eq.return_value = mock_eq_query2
                mock_eq_query2.maybe_single.return_value = mock_maybe_single_query
                mock_maybe_single_query.execute.return_value = mock_set_result
                
                mock_table.delete.return_value = mock_set_delete_query
                mock_set_delete_query.eq.return_value = mock_set_eq_query1
                mock_set_eq_query1.eq.return_value = mock_set_eq_query2
                mock_set_eq_query2.execute.return_value = mock_set_delete_result
                
            elif table_name == 'quiz_questions':
                mock_table.delete.return_value = mock_questions_delete_query
                mock_questions_delete_query.in_.return_value = mock_questions_in_query
                mock_questions_in_query.execute.return_value = mock_questions_result
                
            return mock_table
        
        mock_client.table.side_effect = table_side_effect
        mock_get_client.return_value = mock_client
        
        result = delete_question_set_and_questions('test_hash', 123)
        
        self.assertFalse(result['success'])
        self.assertIn("Failed to delete question set", result['error'])

    @patch('backend.database.get_supabase_client')
    def test_delete_question_set_and_questions_database_error(self, mock_get_client):
        """Test deletion with database error"""
        from backend.database import delete_question_set_and_questions
        
        mock_get_client.side_effect = Exception("Database connection failed")
        
        result = delete_question_set_and_questions('test_hash', 123)
        
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], "Database connection failed")

if __name__ == '__main__':
    unittest.main() 