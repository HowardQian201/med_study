from dotenv import load_dotenv
from openai import OpenAI
import psutil
import platform
import os
import PyPDF2
import tempfile
from pdf2image import convert_from_path
import io
from PIL import Image
import pytesseract
import shutil



load_dotenv()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_PATH")

def gpt_summarize_transcript(text):
    prompt = f"Provide me with detailed and concise notes on this transcript, and include relevant headers for each topic. Be sure to include the mentioned clinical correlates. Transcript:{text}"

    completion = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful teaching assistant \
             (TA) for US medical school. You are extremely knowledgable and \
             want your students to succeed. You also double check your responses \
             for accuracy."},
            {"role": "user", "content": prompt},
        ],
    )

    # Parse the response into lines
    text = completion.choices[0].message.content.strip()
    return text


def extract_text_with_pytesseract(image):
    """Extract text from an image using pytesseract"""
    try:
        # Use pytesseract to extract text
        text = pytesseract.image_to_string(image, lang='eng')
        return text
    except Exception as e:
        print(f"Error with pytesseract OCR: {str(e)}")
        return ""

def convert_pdf_page_to_image(pdf_path, page_num):
    """Convert a specific PDF page to an image"""
    try:
        # Instead of using a context manager, create a temp directory that persists
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Convert PDF page to image with maximum quality settings
            images = convert_from_path(
                pdf_path, 
                first_page=page_num + 1,  # PDF pages are 1-indexed
                last_page=page_num + 1,
                dpi=600,  # Higher DPI for maximum quality
                output_folder=temp_dir,
                fmt='png',  # PNG for lossless quality
            )
            
            if not images:
                return None
            
            # Load the image into memory before returning
            if images:
                # Open the image with PIL and create an in-memory copy
                img = images[0]
                in_memory_img = Image.new(img.mode, img.size)
                in_memory_img.paste(img)
                return in_memory_img
            return None
            
        finally:
            # Clean up the temp directory
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"Error cleaning up temp directory: {str(e)}")
                
    except Exception as e:
        print(f"Error converting PDF to image: {str(e)}")
        return None

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file using both PyPDF2 and pytesseract OCR"""
    PyPDF2_combined_text = ""
    pytesseract_combined_text = ""
    final_text = ""
    min_text_length = 100  # Minimum characters to consider text sufficient
    
    try:
        # Get direct text extraction first
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            num_pages = len(pdf_reader.pages)
            
            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                PyPDF2_combined_text += f"[Page {page_num + 1}]:\n{page_text}\n\n"
                
                # Check if the extracted text is too short
                if len(page_text.strip()) < min_text_length:
                    # Text is too short, use OCR instead
                    image = convert_pdf_page_to_image(pdf_path, page_num)
                    if image:
                        ocr_text = extract_text_with_pytesseract(image)
                        if ocr_text:
                            # Use OCR text for this page
                            final_text += f"[Page {page_num + 1}]:\n{ocr_text}\n\n"
                            pytesseract_combined_text += f"[OCR Page {page_num + 1}]:\n{ocr_text}\n\n"
                            continue
                
                # If we didn't use OCR or OCR failed, use the PyPDF2 text
                final_text += f"[Page {page_num + 1}]:\n{page_text}\n\n"
                                
        return final_text.strip()
    except Exception as e:
        print(f"Error extracting text from PDF: {str(e)}")
        return ""
    

def set_process_priority():
    """Configure process priority based on OS"""
    current_process = psutil.Process()
    try:
        if platform.system() == 'Windows':
            current_process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            current_process.nice(10)  # Unix-like systems
    except:
        print("Could not set process priority")

def check_memory():
    """Check if system has enough memory"""
    if psutil.virtual_memory().percent > 90:
        raise Exception("Memory usage too high")

def save_uploaded_file(file, input_path):
    """Save uploaded file and return total bytes"""
    total_bytes = 0
    chunk_size = 1024 * 1024  # 1MB chunks
    
    with open(input_path, 'wb') as f:
        while True:
            chunk = file.read(chunk_size)
            if not chunk:
                break
            check_memory()
            f.write(chunk)
            total_bytes += len(chunk)
            if total_bytes % (100 * 1024 * 1024) == 0:
                print(f"Received {total_bytes / (1024*1024):.1f} MB")
    
    return total_bytes


