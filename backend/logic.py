from dotenv import load_dotenv
import PyPDF2
import gc
from .aws_ocr import extract_text_with_ocr_from_pdf

load_dotenv()


# Configuration constants
OCR_AVAILABLE = True
OCR_TEXT_THRESHOLD = 50  # Minimum characters to trigger OCR fallback
OCR_DPI = 300  # DPI for OCR image conversion (balance between quality and memory)


# Constants
HIGH_MEMORY_THRESHOLD = 0.85
CRITICAL_MEMORY_THRESHOLD = 0.95
DEFAULT_MEMORY_LIMIT = 512 * 1024 * 1024
OCR_TEXT_THRESHOLD = 50


def extract_text_from_pdf_memory(file_obj, filename=""):
    """Extract text from a PDF file object directly from memory with OCR fallback"""
    final_text = ""
    ocr_pages_count = 0  # Track how many pages needed OCR
    
    try:
        
        # Reset file pointer to beginning
        file_obj.seek(0)
        
        # Create PDF reader from file object
        pdf_reader = PyPDF2.PdfReader(file_obj)
        num_pages = len(pdf_reader.pages)
        
        print(f"Processing PDF '{filename}' with {num_pages} pages from memory")
        
        # Process pages in smaller batches to reduce memory usage
        batch_size = 5 if num_pages > 20 else 10  # Smaller batches for large files
        
        for batch_start in range(0, num_pages, batch_size):
            batch_end = min(batch_start + batch_size, num_pages)
            batch_text = ""
            
            print(f"Processing batch: pages {batch_start + 1}-{batch_end}")
            
            for page_num in range(batch_start, batch_end):
                print(f"Extracting text from page {page_num + 1}")
                                
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text().strip()
                
                # Check if extracted text is insufficient (less than configured threshold)
                if len(page_text) < OCR_TEXT_THRESHOLD:
                    if OCR_AVAILABLE:
                        print(f"Page {page_num + 1}: Insufficient text ({len(page_text)} chars), trying OCR...")
                        
                        try:
                            # Use OCR directly on PDF page
                            ocr_text = extract_text_with_ocr_from_pdf(file_obj, page_num).strip()
                            
                            # Use OCR text if it's significantly better
                            if len(ocr_text) > len(page_text):
                                print(f"Page {page_num + 1}: OCR extracted {len(ocr_text)} chars (vs {len(page_text)} from PDF)")
                                print("OCR text ***")
                                print(ocr_text[:100])
                                page_text = ocr_text
                                ocr_pages_count += 1
                            else:
                                print(f"Page {page_num + 1}: OCR didn't improve text extraction ({len(ocr_text)} chars)")
                                
                        except Exception as ocr_error:
                            print(f"Page {page_num + 1}: OCR failed - {str(ocr_error)}")
                    else:
                        print(f"Page {page_num + 1}: Insufficient text ({len(page_text)} chars), but OCR not available")
                else:
                    print(f"Page {page_num + 1}: Good text extraction ({len(page_text)} chars)")
                
                # Add page text to batch
                batch_text += f"[Page {page_num + 1}]:\n{page_text}\n\n"
                
                # Clear page reference to help garbage collection
                del page_text
                del page
                
                # Force garbage collection and check effect
                gc.collect()
            
            # Add batch to final text and clear batch
            final_text += batch_text
            del batch_text
            
            # Force garbage collection between batches for large files
            if num_pages > 15:
                gc.collect()
        
        # Log OCR usage statistics
        if ocr_pages_count > 0:
            print(f"OCR was used on {ocr_pages_count}/{num_pages} pages ({ocr_pages_count/num_pages*100:.1f}%)")
        elif OCR_AVAILABLE:
            print(f"All {num_pages} pages had sufficient text, no OCR needed")
        else:
            insufficient_pages = sum(1 for page_num in range(num_pages) 
                                   if len(pdf_reader.pages[page_num].extract_text().strip()) < OCR_TEXT_THRESHOLD)
            if insufficient_pages > 0:
                print(f"Note: {insufficient_pages}/{num_pages} pages had insufficient text but OCR was unavailable")
            else:
                print(f"All {num_pages} pages had sufficient text (OCR not needed)")
        
        return final_text.strip()
        
    except Exception as e:
        print(f"Error extracting text from PDF in memory: {str(e)}")
        # Force cleanup on error
        gc.collect()
        return ""
