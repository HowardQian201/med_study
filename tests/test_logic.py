"""
Unit tests for backend/logic.py
"""
import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
from io import BytesIO

# Add the parent directory to the Python path so we can import from backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

class TestLogicFunctions(unittest.TestCase):
    """Test cases for logic functions"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        pass
    
    def tearDown(self):
        """Tear down test fixtures after each test method."""
        pass
    
    @patch('builtins.open', new_callable=mock_open, read_data='max')
    def test_get_container_memory_limit_cgroups_v2_max(self, mock_file):
        """Test memory limit detection with cgroups v2 max value"""
        from backend.logic import get_container_memory_limit
        
        with patch('os.path.exists', return_value=True):
            result = get_container_memory_limit()
            # Should fall back to default when 'max' is read
            self.assertEqual(result, 512 * 1024 * 1024)
    
    @patch('builtins.open', new_callable=mock_open, read_data='1073741824')
    def test_get_container_memory_limit_cgroups_v2_success(self, mock_file):
        """Test successful memory limit detection with cgroups v2"""
        from backend.logic import get_container_memory_limit
        
        with patch('os.path.exists', return_value=True):
            result = get_container_memory_limit()
            self.assertEqual(result, 1073741824)
    
    @patch('builtins.open', side_effect=[IOError("File not found"), mock_open(read_data='1073741824').return_value])
    def test_get_container_memory_limit_cgroups_v1_fallback(self, mock_open):
        """Test memory limit detection falling back to cgroups v1"""
        from backend.logic import get_container_memory_limit
        
        with patch('os.path.exists', side_effect=[False, True, True]):
            result = get_container_memory_limit()
            self.assertEqual(result, 1073741824)
    
    @patch('builtins.open', side_effect=IOError("No files available"))
    def test_get_container_memory_limit_env_var(self, mock_open):
        """Test memory limit detection using environment variable"""
        from backend.logic import get_container_memory_limit
        
        with patch.dict(os.environ, {'MEMORY_LIMIT': '2048'}):
            with patch('os.path.exists', return_value=False):
                result = get_container_memory_limit()
                self.assertEqual(result, 2048 * 1024 * 1024)
    
    @patch('builtins.open', side_effect=IOError("No files available"))
    def test_get_container_memory_limit_default(self, mock_open):
        """Test memory limit detection using default value"""
        from backend.logic import get_container_memory_limit
        
        with patch.dict(os.environ, {}, clear=True):
            with patch('os.path.exists', return_value=False):
                result = get_container_memory_limit()
                self.assertEqual(result, 512 * 1024 * 1024)
    
    @patch('builtins.open', new_callable=mock_open, read_data='536870912')
    def test_get_container_memory_usage_cgroups_v2(self, mock_file):
        """Test memory usage detection with cgroups v2"""
        from backend.logic import get_container_memory_usage
        
        with patch('os.path.exists', return_value=True):
            result = get_container_memory_usage()
            self.assertEqual(result, 536870912)
    
    @patch('builtins.open', side_effect=[IOError("v2 not found"), mock_open(read_data='536870912').return_value])
    def test_get_container_memory_usage_cgroups_v1(self, mock_open):
        """Test memory usage detection with cgroups v1"""
        from backend.logic import get_container_memory_usage
        
        with patch('os.path.exists', side_effect=[False, True, True]):
            result = get_container_memory_usage()
            self.assertEqual(result, 536870912)
    
    @patch('builtins.open', side_effect=IOError("No cgroups"))
    @patch('psutil.Process')
    def test_get_container_memory_usage_process_fallback(self, mock_process, mock_open):
        """Test memory usage detection falling back to process memory"""
        from backend.logic import get_container_memory_usage
        
        mock_memory_info = MagicMock()
        mock_memory_info.rss = 268435456  # 256MB
        mock_memory_info.vms = 536870912  # 512MB
        
        mock_proc = MagicMock()
        mock_proc.memory_info.return_value = mock_memory_info
        mock_process.return_value = mock_proc
        
        with patch('os.path.exists', return_value=False):
            result = get_container_memory_usage()
            self.assertEqual(result, 268435456)
    
    @patch('builtins.open', side_effect=IOError("No cgroups"))
    @patch('psutil.Process', side_effect=Exception("Process error"))
    @patch('psutil.virtual_memory')
    def test_get_container_memory_usage_system_fallback(self, mock_virtual_memory, mock_process, mock_open):
        """Test memory usage detection falling back to system memory"""
        from backend.logic import get_container_memory_usage
        
        mock_memory = MagicMock()
        mock_memory.used = 1073741824  # 1GB
        mock_virtual_memory.return_value = mock_memory
        
        with patch('os.path.exists', return_value=False):
            result = get_container_memory_usage()
            self.assertEqual(result, 1073741824)
    
    @patch('backend.logic.get_container_memory_limit')
    @patch('backend.logic.get_container_memory_usage')
    def test_log_memory_usage_success(self, mock_usage, mock_limit):
        """Test successful memory usage logging"""
        from backend.logic import log_memory_usage
        
        mock_limit.return_value = 1073741824  # 1GB
        mock_usage.return_value = 536870912   # 512MB (50%)
        
        result = log_memory_usage("test stage")
        self.assertEqual(result, 50.0)
    
    @patch('backend.logic.get_container_memory_limit', side_effect=Exception("Error"))
    @patch('psutil.virtual_memory')
    def test_log_memory_usage_error_fallback(self, mock_virtual_memory, mock_get_limit):
        """Test memory usage logging with error fallback"""
        from backend.logic import log_memory_usage
        
        mock_memory = MagicMock()
        mock_memory.percent = 75.0
        mock_memory.used = 1073741824
        mock_memory.total = 1431655765
        mock_virtual_memory.return_value = mock_memory
        
        result = log_memory_usage("test stage")
        self.assertEqual(result, 75.0)
    
    @patch('backend.logic.analyze_memory_usage')
    @patch('backend.logic.extract_text_with_ocr_from_pdf')
    @patch('backend.logic.check_memory')
    @patch('PyPDF2.PdfReader')
    def test_extract_text_from_pdf_memory_success(self, mock_pdf_reader, mock_check_memory, mock_ocr, mock_analyze):
        """Test successful PDF text extraction"""
        from backend.logic import extract_text_from_pdf_memory
        
        # Mock PDF reader and pages
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "This is extracted text from the PDF page."
        
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader
        
        file_obj = BytesIO(b"fake pdf content")
        
        result = extract_text_from_pdf_memory(file_obj, "test.pdf")
        
        self.assertIn("This is extracted text", result)
        self.assertIn("[Page 1]:", result)
    
    @patch('backend.logic.analyze_memory_usage')
    @patch('backend.logic.extract_text_with_ocr_from_pdf')
    @patch('backend.logic.check_memory')
    @patch('PyPDF2.PdfReader')
    def test_extract_text_from_pdf_memory_with_ocr(self, mock_pdf_reader, mock_check_memory, mock_ocr, mock_analyze):
        """Test PDF text extraction with OCR fallback"""
        from backend.logic import extract_text_from_pdf_memory
        
        # Mock PDF reader with insufficient text
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Short"  # Less than OCR_TEXT_THRESHOLD
        
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader
        
        # Mock OCR to return better text
        mock_ocr.return_value = "This is much longer OCR extracted text that exceeds the threshold."
        
        file_obj = BytesIO(b"fake pdf content")
        
        result = extract_text_from_pdf_memory(file_obj, "test.pdf")
        
        self.assertIn("OCR extracted text", result)
        mock_ocr.assert_called_once()
    
    @patch('backend.logic.analyze_memory_usage')
    @patch('backend.logic.extract_text_with_ocr_from_pdf', side_effect=Exception("OCR failed"))
    @patch('backend.logic.check_memory')
    @patch('PyPDF2.PdfReader')
    def test_extract_text_from_pdf_memory_ocr_failure(self, mock_pdf_reader, mock_check_memory, mock_ocr, mock_analyze):
        """Test PDF text extraction with OCR failure"""
        from backend.logic import extract_text_from_pdf_memory
        
        # Mock PDF reader with insufficient text
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Short"
        
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader
        
        file_obj = BytesIO(b"fake pdf content")
        
        result = extract_text_from_pdf_memory(file_obj, "test.pdf")
        
        # Should still return the original text even if OCR fails
        self.assertIn("Short", result)
        mock_ocr.assert_called_once()
    
    @patch('backend.logic.analyze_memory_usage')
    @patch('PyPDF2.PdfReader', side_effect=Exception("PDF parsing failed"))
    def test_extract_text_from_pdf_memory_pdf_error(self, mock_pdf_reader, mock_analyze):
        """Test PDF text extraction with PDF parsing error"""
        from backend.logic import extract_text_from_pdf_memory
        
        file_obj = BytesIO(b"fake pdf content")
        
        result = extract_text_from_pdf_memory(file_obj, "test.pdf")
        
        # Should return empty string on error
        self.assertEqual(result, "")
    
    @patch('psutil.Process')
    def test_set_process_priority_success(self, mock_process):
        """Test successful process priority setting"""
        from backend.logic import set_process_priority
        
        mock_proc = MagicMock()
        mock_process.return_value = mock_proc
        
        # Should not raise an exception
        set_process_priority()
        
        # On Windows, should attempt to set priority
        if os.name == 'nt':
            mock_proc.nice.assert_called()
    
    @patch('psutil.Process', side_effect=Exception("Permission denied"))
    def test_set_process_priority_error(self, mock_process):
        """Test process priority setting with error"""
        from backend.logic import set_process_priority
        
        # Should not raise an exception even on error, just print a message
        set_process_priority()
        mock_process.assert_called_once()
    
    @patch('backend.logic.get_container_memory_limit')
    @patch('backend.logic.get_container_memory_usage')
    def test_check_memory_normal(self, mock_usage, mock_limit):
        """Test memory check under normal conditions"""
        from backend.logic import check_memory
        
        mock_limit.return_value = 1073741824  # 1GB
        mock_usage.return_value = 536870912   # 512MB (50%)
        
        # Should not raise an exception
        check_memory()
    
    @patch('backend.logic.get_container_memory_limit')
    @patch('backend.logic.get_container_memory_usage')
    @patch('gc.collect')
    def test_check_memory_high_usage(self, mock_gc, mock_usage, mock_limit):
        """Test memory check with high memory usage"""
        from backend.logic import check_memory
        
        mock_limit.return_value = 1073741824      # 1GB
        mock_usage.return_value = 966367641       # 90% usage
        
        # Should not raise an exception, but should trigger GC
        check_memory()
        mock_gc.assert_called_once()
    
    @patch('builtins.print')
    @patch('backend.logic.get_container_memory_limit')
    @patch('backend.logic.get_container_memory_usage')
    def test_check_memory_critical_usage(self, mock_usage, mock_limit, mock_print):
        """Test memory check with critical memory usage"""
        from backend.logic import check_memory
        
        mock_limit.return_value = 1073741824   # 1GB
        mock_usage.return_value = 1020054733   # 95% usage
        
        # The function catches the MemoryError, so we check for the print output
        check_memory()
        
        # Check that the critical error message was printed
        critical_message_found = False
        for call in mock_print.call_args_list:
            if "Memory usage critical" in call[0][0]:
                critical_message_found = True
                break
        self.assertTrue(critical_message_found, "Critical memory usage message was not printed.")
    
    @patch('backend.logic.log_memory_usage')
    def test_analyze_memory_usage(self, mock_log):
        """Test memory usage analysis"""
        from backend.logic import analyze_memory_usage
        analyze_memory_usage("test stage")
        mock_log.assert_called_once_with("test stage")

if __name__ == '__main__':
    unittest.main() 