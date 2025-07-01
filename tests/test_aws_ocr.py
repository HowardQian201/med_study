"""
Unit tests for backend/aws_ocr.py
"""
import unittest
from unittest.mock import patch, MagicMock
import sys
import os
from io import BytesIO

# Add the parent directory to the Python path so we can import from backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class TestAwsOcr(unittest.TestCase):
    """Test cases for AWS OCR functions"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        pass
    
    def tearDown(self):
        """Tear down test fixtures after each test method."""
        pass
    
    @patch('boto3.client')
    @patch('PyPDF2.PdfReader')
    @patch('PyPDF2.PdfWriter')
    def test_extract_text_with_ocr_from_pdf_success(self, mock_pdf_writer, mock_pdf_reader, mock_boto_client):
        """Test successful OCR text extraction"""
        from backend.aws_ocr import extract_text_with_ocr_from_pdf
        
        # Mock PDF components
        mock_page = MagicMock()
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader
        
        mock_writer = MagicMock()
        mock_pdf_writer.return_value = mock_writer
        
        # Mock BytesIO write operation
        with patch('backend.aws_ocr.BytesIO') as mock_bytesio:
            mock_buffer = MagicMock()
            mock_buffer.getvalue.return_value = b"mocked pdf bytes"
            mock_bytesio.return_value = mock_buffer
            
            # Mock Textract client and response
            mock_textract = MagicMock()
            mock_boto_client.return_value = mock_textract
            
            mock_response = {
                'Blocks': [
                    {
                        'BlockType': 'LINE',
                        'Text': 'This is line 1',
                        'Confidence': 95.5
                    },
                    {
                        'BlockType': 'LINE', 
                        'Text': 'This is line 2',
                        'Confidence': 98.2
                    },
                    {
                        'BlockType': 'WORD',
                        'Text': 'word',
                        'Confidence': 99.0
                    }
                ]
            }
            mock_textract.detect_document_text.return_value = mock_response
            
            file_obj = BytesIO(b"fake pdf content")
            result = extract_text_with_ocr_from_pdf(file_obj, 0)
            
            self.assertIn('This is line 1', result)
            self.assertIn('This is line 2', result)
            mock_textract.detect_document_text.assert_called_once()
    
    @patch('boto3.client')
    @patch('PyPDF2.PdfReader')
    @patch('PyPDF2.PdfWriter')
    def test_extract_text_with_ocr_from_pdf_no_confidence(self, mock_pdf_writer, mock_pdf_reader, mock_boto_client):
        """Test OCR text extraction with blocks that have no confidence"""
        from backend.aws_ocr import extract_text_with_ocr_from_pdf
        
        # Mock PDF components
        mock_page = MagicMock()
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader
        
        mock_writer = MagicMock()
        mock_pdf_writer.return_value = mock_writer
        
        # Mock BytesIO write operation
        with patch('backend.aws_ocr.BytesIO') as mock_bytesio:
            mock_buffer = MagicMock()
            mock_buffer.getvalue.return_value = b"mocked pdf bytes"
            mock_bytesio.return_value = mock_buffer
            
            # Mock Textract client and response
            mock_textract = MagicMock()
            mock_boto_client.return_value = mock_textract
            
            mock_response = {
                'Blocks': [
                    {
                        'BlockType': 'LINE',
                        'Text': 'This is line without confidence'
                        # No 'Confidence' field
                    }
                ]
            }
            mock_textract.detect_document_text.return_value = mock_response
            
            file_obj = BytesIO(b"fake pdf content")
            result = extract_text_with_ocr_from_pdf(file_obj, 0)
            
            self.assertIn('This is line without confidence', result)
            mock_textract.detect_document_text.assert_called_once()
    
    @patch('boto3.client')
    @patch('PyPDF2.PdfReader')
    @patch('PyPDF2.PdfWriter')
    def test_extract_text_with_ocr_invalid_parameter_error(self, mock_pdf_writer, mock_pdf_reader, mock_boto_client):
        """Test OCR with InvalidParameterException"""
        from backend.aws_ocr import extract_text_with_ocr_from_pdf
        from botocore.exceptions import ClientError
        
        # Mock PDF components
        mock_page = MagicMock()
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader
        
        mock_writer = MagicMock()
        mock_pdf_writer.return_value = mock_writer
        
        # Mock BytesIO write operation
        with patch('backend.aws_ocr.BytesIO') as mock_bytesio:
            mock_buffer = MagicMock()
            mock_buffer.getvalue.return_value = b"mocked pdf bytes"
            mock_bytesio.return_value = mock_buffer
            
            # Mock Textract client with ClientError
            mock_textract = MagicMock()
            mock_boto_client.return_value = mock_textract
            
            error_response = {
                'Error': {
                    'Code': 'InvalidParameterException',
                    'Message': 'Invalid PDF format'
                }
            }
            mock_textract.detect_document_text.side_effect = ClientError(error_response, 'DetectDocumentText')
            
            file_obj = BytesIO(b"fake pdf content")
            result = extract_text_with_ocr_from_pdf(file_obj, 0)
            
            # Should return empty string on error
            self.assertEqual(result, "")
    
    @patch('boto3.client')
    @patch('PyPDF2.PdfReader')
    @patch('PyPDF2.PdfWriter')
    def test_extract_text_with_ocr_access_denied_error(self, mock_pdf_writer, mock_pdf_reader, mock_boto_client):
        """Test OCR with AccessDeniedException"""
        from backend.aws_ocr import extract_text_with_ocr_from_pdf
        from botocore.exceptions import ClientError
        
        # Mock PDF components
        mock_page = MagicMock()
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader
        
        mock_writer = MagicMock()
        mock_pdf_writer.return_value = mock_writer
        
        # Mock BytesIO write operation
        with patch('backend.aws_ocr.BytesIO') as mock_bytesio:
            mock_buffer = MagicMock()
            mock_buffer.getvalue.return_value = b"mocked pdf bytes"
            mock_bytesio.return_value = mock_buffer
            
            # Mock Textract client with ClientError
            mock_textract = MagicMock()
            mock_boto_client.return_value = mock_textract
            
            error_response = {
                'Error': {
                    'Code': 'AccessDeniedException',
                    'Message': 'Access denied'
                }
            }
            mock_textract.detect_document_text.side_effect = ClientError(error_response, 'DetectDocumentText')
            
            file_obj = BytesIO(b"fake pdf content")
            result = extract_text_with_ocr_from_pdf(file_obj, 0)
            
            # Should return empty string on error
            self.assertEqual(result, "")
    
    @patch('boto3.client')
    @patch('PyPDF2.PdfReader')
    @patch('PyPDF2.PdfWriter')
    def test_extract_text_with_ocr_throttling_error(self, mock_pdf_writer, mock_pdf_reader, mock_boto_client):
        """Test OCR with ThrottlingException"""
        from backend.aws_ocr import extract_text_with_ocr_from_pdf
        from botocore.exceptions import ClientError
        
        # Mock PDF components
        mock_page = MagicMock()
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader
        
        mock_writer = MagicMock()
        mock_pdf_writer.return_value = mock_writer
        
        # Mock BytesIO write operation
        with patch('backend.aws_ocr.BytesIO') as mock_bytesio:
            mock_buffer = MagicMock()
            mock_buffer.getvalue.return_value = b"mocked pdf bytes"
            mock_bytesio.return_value = mock_buffer
            
            # Mock Textract client with ClientError
            mock_textract = MagicMock()
            mock_boto_client.return_value = mock_textract
            
            error_response = {
                'Error': {
                    'Code': 'ThrottlingException',
                    'Message': 'Rate exceeded'
                }
            }
            mock_textract.detect_document_text.side_effect = ClientError(error_response, 'DetectDocumentText')
            
            file_obj = BytesIO(b"fake pdf content")
            result = extract_text_with_ocr_from_pdf(file_obj, 0)
            
            # Should return empty string on error
            self.assertEqual(result, "")
    
    @patch('boto3.client')
    @patch('PyPDF2.PdfReader')
    @patch('PyPDF2.PdfWriter')
    def test_extract_text_with_ocr_provisioned_throughput_error(self, mock_pdf_writer, mock_pdf_reader, mock_boto_client):
        """Test OCR with ProvisionedThroughputExceededException"""
        from backend.aws_ocr import extract_text_with_ocr_from_pdf
        from botocore.exceptions import ClientError
        
        # Mock PDF components
        mock_page = MagicMock()
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader
        
        mock_writer = MagicMock()
        mock_pdf_writer.return_value = mock_writer
        
        # Mock BytesIO write operation
        with patch('backend.aws_ocr.BytesIO') as mock_bytesio:
            mock_buffer = MagicMock()
            mock_buffer.getvalue.return_value = b"mocked pdf bytes"
            mock_bytesio.return_value = mock_buffer
            
            # Mock Textract client with ClientError
            mock_textract = MagicMock()
            mock_boto_client.return_value = mock_textract
            
            error_response = {
                'Error': {
                    'Code': 'ProvisionedThroughputExceededException',
                    'Message': 'Capacity exceeded'
                }
            }
            mock_textract.detect_document_text.side_effect = ClientError(error_response, 'DetectDocumentText')
            
            file_obj = BytesIO(b"fake pdf content")
            result = extract_text_with_ocr_from_pdf(file_obj, 0)
            
            # Should return empty string on error
            self.assertEqual(result, "")
    
    @patch('boto3.client')
    @patch('PyPDF2.PdfReader')
    @patch('PyPDF2.PdfWriter')
    def test_extract_text_with_ocr_credentials_error(self, mock_pdf_writer, mock_pdf_reader, mock_boto_client):
        """Test OCR with credentials error"""
        from backend.aws_ocr import extract_text_with_ocr_from_pdf
        from botocore.exceptions import NoCredentialsError
        
        # Mock PDF components
        mock_page = MagicMock()
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader
        
        mock_writer = MagicMock()
        mock_pdf_writer.return_value = mock_writer
        
        # Mock BytesIO write operation
        with patch('backend.aws_ocr.BytesIO') as mock_bytesio:
            mock_buffer = MagicMock()
            mock_buffer.getvalue.return_value = b"mocked pdf bytes"
            mock_bytesio.return_value = mock_buffer
            
            # Mock Textract client with credentials error
            mock_textract = MagicMock()
            mock_boto_client.return_value = mock_textract
            
            mock_textract.detect_document_text.side_effect = NoCredentialsError()
            
            file_obj = BytesIO(b"fake pdf content")
            result = extract_text_with_ocr_from_pdf(file_obj, 0)
            
            # Should return empty string on error
            self.assertEqual(result, "")
    
    @patch('boto3.client')
    @patch('PyPDF2.PdfReader')
    @patch('PyPDF2.PdfWriter')
    def test_extract_text_with_ocr_partial_credentials_error(self, mock_pdf_writer, mock_pdf_reader, mock_boto_client):
        """Test OCR with partial credentials error"""
        from backend.aws_ocr import extract_text_with_ocr_from_pdf
        from botocore.exceptions import PartialCredentialsError
        
        # Mock PDF components
        mock_page = MagicMock()
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader
        
        mock_writer = MagicMock()
        mock_pdf_writer.return_value = mock_writer
        
        # Mock BytesIO write operation
        with patch('backend.aws_ocr.BytesIO') as mock_bytesio:
            mock_buffer = MagicMock()
            mock_buffer.getvalue.return_value = b"mocked pdf bytes"
            mock_bytesio.return_value = mock_buffer
            
            # Mock Textract client with partial credentials error
            mock_textract = MagicMock()
            mock_boto_client.return_value = mock_textract
            
            mock_textract.detect_document_text.side_effect = PartialCredentialsError(
                provider='test', cred_var='test'
            )
            
            file_obj = BytesIO(b"fake pdf content")
            result = extract_text_with_ocr_from_pdf(file_obj, 0)
            
            # Should return empty string on error
            self.assertEqual(result, "")
    
    @patch('boto3.client')
    @patch('PyPDF2.PdfReader')
    @patch('PyPDF2.PdfWriter')
    def test_extract_text_with_ocr_unexpected_error(self, mock_pdf_writer, mock_pdf_reader, mock_boto_client):
        """Test OCR with unexpected error"""
        from backend.aws_ocr import extract_text_with_ocr_from_pdf
        
        # Mock PDF components
        mock_page = MagicMock()
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader
        
        mock_writer = MagicMock()
        mock_pdf_writer.return_value = mock_writer
        
        # Mock BytesIO write operation
        with patch('backend.aws_ocr.BytesIO') as mock_bytesio:
            mock_buffer = MagicMock()
            mock_buffer.getvalue.return_value = b"mocked pdf bytes"
            mock_bytesio.return_value = mock_buffer
            
            # Mock Textract client with unexpected error
            mock_textract = MagicMock()
            mock_boto_client.return_value = mock_textract
            
            mock_textract.detect_document_text.side_effect = Exception("Unexpected error")
            
            file_obj = BytesIO(b"fake pdf content")
            result = extract_text_with_ocr_from_pdf(file_obj, 0)
            
            # Should return empty string on error
            self.assertEqual(result, "")
    
    @patch('PyPDF2.PdfReader', side_effect=Exception("PDF processing error"))
    def test_extract_text_with_ocr_pdf_processing_error(self, mock_pdf_reader):
        """Test OCR with PDF processing error"""
        from backend.aws_ocr import extract_text_with_ocr_from_pdf
        
        file_obj = BytesIO(b"fake pdf content")
        result = extract_text_with_ocr_from_pdf(file_obj, 0)
        
        # Should return empty string on error
        self.assertEqual(result, "")

if __name__ == '__main__':
    unittest.main() 