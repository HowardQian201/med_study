from dotenv import load_dotenv
from openai import OpenAI
import psutil
import platform
import os
import PyPDF2
import tempfile
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import shutil
import json
import time
import uuid
import random
import gc



load_dotenv()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Configure tesseract path
tesseract_custom_path = os.getenv("TESSERACT_PATH")
if tesseract_custom_path:
    pytesseract.pytesseract.tesseract_cmd = tesseract_custom_path
    print(f"Using custom tesseract path: {tesseract_custom_path}")
else:
    # Try common tesseract paths
    common_paths = [
        '/usr/bin/tesseract',
        '/usr/local/bin/tesseract',
        '/bin/tesseract',
        '/opt/homebrew/bin/tesseract',  # macOS with Homebrew
        'tesseract'  # System PATH
    ]
    
    tesseract_found = False
    print("Searching for tesseract executable...")
    
    for path in common_paths:
        print(f"Checking path: {path}")
        try:
            if path == 'tesseract':
                # Test system PATH using shutil.which
                import shutil
                tesseract_path = shutil.which('tesseract')
                if tesseract_path:
                    print(f"Found tesseract in system PATH: {tesseract_path}")
                    pytesseract.pytesseract.tesseract_cmd = tesseract_path
                    tesseract_found = True
                    break
            elif os.path.exists(path):
                print(f"Found tesseract at: {path}")
                pytesseract.pytesseract.tesseract_cmd = path
                tesseract_found = True
                break
            else:
                print(f"  Not found at {path}")
        except Exception as e:
            print(f"  Error checking {path}: {str(e)}")
            continue
    
    if not tesseract_found:
        print("Warning: Tesseract not found. OCR functionality will be disabled.")
        # Try to get more info about the environment
        try:
            import subprocess
            print("Running diagnostic commands...")
            
            # Check if tesseract is installed but not in expected locations
            try:
                result = subprocess.run(['dpkg', '-l', 'tesseract-ocr'], 
                                      capture_output=True, text=True, timeout=10)
                print(f"dpkg check returncode: {result.returncode}")
                if result.returncode == 0:
                    print("tesseract-ocr package is installed:")
                    print(result.stdout)
                else:
                    print("tesseract-ocr package not found via dpkg")
                    print(f"stderr: {result.stderr}")
            except Exception as dpkg_error:
                print(f"dpkg command failed: {str(dpkg_error)}")
            
            # Try to find tesseract files anywhere
            try:
                result = subprocess.run(['find', '/usr', '-name', '*tesseract*', '-type', 'f'], 
                                      capture_output=True, text=True, timeout=15)
                print(f"find command returncode: {result.returncode}")
                if result.returncode == 0 and result.stdout.strip():
                    print("Found tesseract-related files:")
                    print(result.stdout)
                    # Look for executable files
                    tesseract_files = result.stdout.strip().split('\n')
                    for file_path in tesseract_files:
                        if 'tesseract' in file_path and os.access(file_path, os.X_OK):
                            print(f"Found executable tesseract: {file_path}")
                            pytesseract.pytesseract.tesseract_cmd = file_path
                            tesseract_found = True
                            break
                else:
                    print("No tesseract files found via find command")
                    print(f"stderr: {result.stderr}")
            except Exception as find_error:
                print(f"find command failed: {str(find_error)}")
            
            # Check PATH environment variable
            try:
                path_env = os.environ.get('PATH', '')
                print(f"PATH environment variable: {path_env}")
                
                # Try whereis command
                result = subprocess.run(['whereis', 'tesseract'], 
                                      capture_output=True, text=True, timeout=10)
                print(f"whereis tesseract: {result.stdout}")
            except Exception as path_error:
                print(f"PATH check failed: {str(path_error)}")
                
        except Exception as e:
            print(f"Error during comprehensive tesseract search: {str(e)}")
            import traceback
            traceback.print_exc()

# Test if tesseract is working
try:
    version = pytesseract.get_tesseract_version()
    print(f"Tesseract OCR available - version: {version}")
    TESSERACT_AVAILABLE = True
except Exception as e:
    print(f"Tesseract OCR not available: {str(e)}")
    TESSERACT_AVAILABLE = False
    
    # Additional debugging - show current tesseract command
    print(f"Current tesseract command: {pytesseract.pytesseract.tesseract_cmd}")
    
    # Try to run tesseract directly to see what happens
    try:
        import subprocess
        result = subprocess.run([pytesseract.pytesseract.tesseract_cmd, '--version'], 
                              capture_output=True, text=True, timeout=10)
        print(f"Direct tesseract call result (returncode {result.returncode}):")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
    except Exception as direct_error:
        print(f"Direct tesseract call failed: {str(direct_error)}")

# Configuration constants
OCR_TEXT_THRESHOLD = 50  # Minimum characters to trigger OCR fallback
OCR_DPI = 300  # DPI for OCR image conversion (balance between quality and memory)

# Global variable to track peak memory usage
_peak_memory_usage = 0

def get_container_memory_limit():
    """Get the actual memory limit for the container"""
    try:
        
        # Try to read from cgroups v2
        try:
            with open('/sys/fs/cgroup/memory.max', 'r') as f:
                limit_str = f.read().strip()
                if limit_str == 'max':
                    raise Exception("No cgroup limit set")
                return int(limit_str)
        except:
            print("Error reading memory limit from cgroups v2")
            pass

        # Try to read from cgroups v1
        try:
            with open('/sys/fs/cgroup/memory/memory.limit_in_bytes', 'r') as f:
                limit = int(f.read().strip())
                # If limit is very large, it's probably not set (default is 9223372036854775807)
                if limit > 1024 * 1024 * 1024 * 1024:  # 1TB
                    raise Exception("No cgroup limit set")
                return limit
        except:
            print("Error reading memory limit from cgroups v1")
            pass
            
        # Check environment variables that Render might set
        if 'MEMORY_LIMIT' in os.environ:
            return int(os.environ['MEMORY_LIMIT']) * 1024 * 1024  # Assume MB
        
        # Default to Render free tier limit
        print("Warning: Could not detect container memory limit, assuming 512MB")
        return 512 * 1024 * 1024  # 512MB in bytes
        
    except Exception as e:
        print(f"Error detecting memory limit: {e}")
        return 512 * 1024 * 1024  # Default to 512MB

def get_container_memory_usage():
    """Get current memory usage that respects container limits"""
    try:
        # First try to read current usage from cgroups v2 (most accurate for containers)
        try:
            with open('/sys/fs/cgroup/memory.current', 'r') as f:
                cgroup_memory = int(f.read().strip())
                print(f"Container memory from cgroups v2: {cgroup_memory/(1024*1024):.1f}MB")
                return cgroup_memory
        except Exception as e:
            print(f"Error reading memory usage from cgroups v2: {e}")
        
        # Try to read current usage from cgroups v1
        try:
            with open('/sys/fs/cgroup/memory/memory.usage_in_bytes', 'r') as f:
                cgroup_memory = int(f.read().strip())
                print(f"Container memory from cgroups v1: {cgroup_memory/(1024*1024):.1f}MB")
                return cgroup_memory
        except Exception as e:
            print(f"Error reading memory usage from cgroups v1: {e}")
        
        # Fallback to process memory (less accurate but better than system memory)
        current_process = psutil.Process()
        process_memory = current_process.memory_info()
        
        # RSS (Resident Set Size) is the actual physical memory used by this process
        actual_memory_used = process_memory.rss
        
        print(f"Process memory fallback - RSS: {actual_memory_used/(1024*1024):.1f}MB, VMS: {process_memory.vms/(1024*1024):.1f}MB")
        return actual_memory_used
        
    except Exception as e:
        print(f"Error reading container memory: {e}")
        # Final fallback to system memory (least accurate)
        memory = psutil.virtual_memory()
        print("Using system memory as final fallback")
        return memory.used

def log_memory_usage(stage):
    """Log current memory usage with container awareness and peak tracking"""
    global _peak_memory_usage
    
    try:
        memory_limit = get_container_memory_limit()
        memory_used = get_container_memory_usage()
        memory_percent = (memory_used / memory_limit) * 100
        
        # Track peak memory usage
        if memory_used > _peak_memory_usage:
            _peak_memory_usage = memory_used
            
        print(f"Memory at {stage}: {memory_percent:.1f}% used ({memory_used/(1024*1024):.1f}MB/{memory_limit/(1024*1024):.1f}MB) [Peak: {_peak_memory_usage/(1024*1024):.1f}MB]")
        return memory_percent
    except Exception as e:
        print(f"Error in memory logging: {e}")
        # Fallback to psutil
        memory = psutil.virtual_memory()
        print(f"Memory at {stage}: {memory.percent}% used ({memory.used/(1024*1024):.1f}MB/{memory.total/(1024*1024):.1f}MB) [HOST]")
        return memory.percent

def randomize_answer_choices(question):
    """
    Randomize the order of answer choices and update the correctAnswer index accordingly.
    
    Args:
        question (dict): Question object with 'options' and 'correctAnswer' fields
        
    Returns:
        dict: Question object with randomized options and updated correctAnswer index
    """
    if not isinstance(question.get('options'), list) or len(question['options']) != 4:
        return question
    
    if not isinstance(question.get('correctAnswer'), int) or question['correctAnswer'] < 0 or question['correctAnswer'] > 3:
        return question
    
    # Store the original correct answer index
    original_correct_index = question['correctAnswer']
    
    # Create a list of (index, option) pairs to track original positions
    indexed_options = [(i, option) for i, option in enumerate(question['options'])]
    
    # Shuffle the options
    random.shuffle(indexed_options)
    
    # Extract the shuffled options and find new position of correct answer
    shuffled_options = []
    new_correct_index = 0
    
    for new_index, (original_index, option) in enumerate(indexed_options):
        shuffled_options.append(option)
        if original_index == original_correct_index:
            new_correct_index = new_index
    
    # Update the question with randomized data
    question['options'] = shuffled_options
    question['correctAnswer'] = new_correct_index
    
    return question

def gpt_summarize_transcript(text):
    print("gpt_summarize_transcript")
    prompt = f"Provide me with detailed, thorough, and comprehensive study guide/summary \
        using full sentences based on this transcript. Include relevant headers for each \
            topic and make sure to inlcude all key information. Be sure to include the \
                mentioned clinical correlates. Transcript:{text}"

    completion = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful teaching assistant \
             for US medical school. You are extremely knowledgable and \
             want your students to succeed by providing them with extremely detailed and thorough study guides/summaries. \
             You also double check all your responses for accuracy."},
            {"role": "user", "content": prompt},
        ],
    )

    print("gpt_summarize_transcript completion")
    analyze_memory_usage("gpt_summarize_transcript completion")

    # Parse the response into lines
    text = completion.choices[0].message.content.strip()
    return text

def generate_quiz_questions(summary_text, request_id=None):
    """Generate quiz questions from a summary text using OpenAI's API"""
    if request_id is None:
        request_id = str(uuid.uuid4())[:8]
    
    try:
        log_memory_usage("quiz generation start")
        
        prompt = f"""
        Based on the following medical text summary, create 5 challenging USMLE clinical vignette style \
            multiple-choice questions to test the student's understanding. 
        
        For each question:
        1. Create a clear, specific question about key concepts in the text
        2. Provide exactly 4 answer choices
        3. Indicate which answer is correct (index 0-3)
        4. Include a thorough explanation for why the correct answer is right and why others are wrong (Dont include the answer index in the reason)
        5. Be in the style of a clinical vignette (e.g. "A 62-year-old man presents to the emergency department with shortness of breath and chest discomfort that began two hours ago while he was watching television. He describes the discomfort as a vague pressure in the center of his chest, without radiation. He denies any nausea or diaphoresis. He has a history of hypertension, type 2 diabetes mellitus, and hyperlipidemia. He is a former smoker (40 pack-years, quit 5 years ago). On examination, his blood pressure is 146/88 mmHg, heart rate is 94/min, respiratory rate is 20/min, and oxygen saturation is 95% on room air. Cardiac auscultation reveals normal S1 and S2 without murmurs. Lungs are clear to auscultation bilaterally. There is no jugular venous distension or peripheral edema. ECG reveals normal sinus rhythm with 2 mm ST-segment depressions in leads V4–V6. Cardiac biomarkers are pending. Which of the following is the most appropriate next step in management?")

        Format the response as a JSON array of question objects. Each question object should have these fields:
        - id: a unique number (1-5)
        - text: the question text
        - options: array of 4 answer choices 
        - correctAnswer: index of correct answer (0-3)
        - reason: explanation for the correct answer (Dont include the answer index in the reason)
        
        Summary:
        {summary_text}
        
        Return ONLY the valid JSON array with no other text.
        """

        check_memory()  # Check memory before API call
        
        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert medical professor that creates \
                 accurate, challenging multiple choice questions in the style of clinical vignettes. \
                 You respond ONLY with the requested JSON format."},
                {"role": "user", "content": prompt},
            ],
        )

        log_memory_usage("after OpenAI API call")
        analyze_memory_usage("after OpenAI API call")

        # Get JSON response
        response_text = completion.choices[0].message.content.strip()
        print("response_text")
        print(response_text[:100])
        
        # Sometimes the API returns markdown json blocks, so let's clean that up
        if response_text.startswith("```json"):
            response_text = response_text.replace("```json", "", 1)
        if response_text.endswith("```"):
            response_text = response_text.rsplit("```", 1)[0]
            
        response_text = response_text.strip()
        # Parse JSON
        questions = json.loads(response_text)
        
        log_memory_usage("after JSON parsing")
        
        # Validate the response has the expected structure
        if not isinstance(questions, list) or len(questions) == 0:
            raise Exception("Invalid response format: not a list or empty list")
            
        # Ensure each question has the required fields
        for q in questions:
            required_fields = ['id', 'text', 'options', 'correctAnswer', 'reason']
            for field in required_fields:
                if field not in q:
                    raise Exception(f"Question missing required field: {field}")
            
            # Ensure options is a list with exactly 4 items
            if not isinstance(q['options'], list) or len(q['options']) != 4:
                raise Exception(f"Question options must be a list with exactly 4 items")
                
            # Ensure correctAnswer is an integer between 0-3
            if not isinstance(q['correctAnswer'], int) or q['correctAnswer'] < 0 or q['correctAnswer'] > 3:
                raise Exception(f"Question correctAnswer must be an integer between 0-3")
        
            randomize_answer_choices(q)

        log_memory_usage("quiz generation complete")
        return questions
    except Exception as e:
        print(f"Error generating quiz questions: {str(e)}")
        # Return some default questions if there's an error
        fallback_questions = [
            {
                "id": 1,
                "text": "What is the main purpose of this document?",
                "options": [
                    "To provide medical information",
                    "To give financial advice",
                    "To describe laboratory procedures",
                    "To explain treatment options"
                ],
                "correctAnswer": 0,
                "reason": "This is a fallback question generated when the API request failed."
            },
            {
                "id": 2,
                "text": "Which of the following best describes the content?",
                "options": [
                    "Research findings",
                    "Patient cases",
                    "Medical guidelines",
                    "Educational material"
                ],
                "correctAnswer": 3,
                "reason": "This is a fallback question generated when the API request failed."
            }
        ]
        return fallback_questions

def generate_focused_questions(summary_text, incorrect_question_ids, previous_questions):
    """Generate more targeted quiz questions focusing on areas where the user had difficulty"""
    try:
        # Extract incorrect questions
        incorrect_questions = []
        if previous_questions and incorrect_question_ids:
            incorrect_questions = [q['text'] for q in previous_questions if q['id'] in incorrect_question_ids]
        
        # Create a prompt with more focus on areas the user missed
        print("incorrect_questions")
        print({json.dumps(incorrect_questions) if incorrect_questions else "No specific areas - generate new questions on the key topics"})

        prompt = f"""
        Based on the following medical text summary and struggled concepts, create 5 challenging USMLE clinical vignette style multiple-choice questions.

        The user previously struggled with these specific concepts:
        {json.dumps(incorrect_questions) if incorrect_questions else "No specific areas - generate new questions on the key topics"}
        
        For each question:
        1. Create challenging but fair questions that test understanding of key concepts
        2. If the user struggled with specific areas above, focus at least 3 questions on similar topics, but make sure they are not too similar/repetitive.
        3. Provide exactly 4 answer choices
        4. Indicate which answer is correct (index 0-3)
        5. Include a thorough explanation for why the correct answer is right and why others are wrong (Dont include the answer index in the reason)
        6. Be in the style of a clinical vignette (e.g. "A 62-year-old man presents to the emergency department with shortness of breath and chest discomfort that began two hours ago while he was watching television. He describes the discomfort as a vague pressure in the center of his chest, without radiation. He denies any nausea or diaphoresis. He has a history of hypertension, type 2 diabetes mellitus, and hyperlipidemia. He is a former smoker (40 pack-years, quit 5 years ago). On examination, his blood pressure is 146/88 mmHg, heart rate is 94/min, respiratory rate is 20/min, and oxygen saturation is 95% on room air. Cardiac auscultation reveals normal S1 and S2 without murmurs. Lungs are clear to auscultation bilaterally. There is no jugular venous distension or peripheral edema. ECG reveals normal sinus rhythm with 2 mm ST-segment depressions in leads V4–V6. Cardiac biomarkers are pending. Which of the following is the most appropriate next step in management?")


        Format the response as a JSON array of question objects. Each question object should have these fields:
        - id: a unique number (1-5)
        - text: the question text
        - options: array of 4 answer choices 
        - correctAnswer: index of correct answer (0-3)
        - reason: explanation for the correct answer (Dont include the answer index in the reason)
        
        Summary:
        {summary_text}
        
        Return ONLY the valid JSON array with no other text.
        """

        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert medical professor that creates \
                 accurate, challenging multiple choice questions in the style of clinical vignettes. \
                 You respond ONLY with the requested JSON format."},
                {"role": "user", "content": prompt},
            ],
        )

        log_memory_usage("after OpenAI 2 API call")
        analyze_memory_usage("after OpenAI 2 API call")

        # Get JSON response
        response_text = completion.choices[0].message.content.strip()
        print("response_text")
        print(response_text[:100])
        
        # Clean up markdown formatting if present
        if response_text.startswith("```json"):
            response_text = response_text.replace("```json", "", 1)
        if response_text.endswith("```"):
            response_text = response_text.rsplit("```", 1)[0]
            
        response_text = response_text.strip()
            
        # Parse JSON
        questions = json.loads(response_text)
        
        # Validate the response has the expected structure
        if not isinstance(questions, list) or len(questions) == 0:
            raise Exception("Invalid response format: not a list or empty list")
            
        # Ensure each question has the required fields
        for q in questions:
            required_fields = ['id', 'text', 'options', 'correctAnswer', 'reason']
            for field in required_fields:
                if field not in q:
                    raise Exception(f"Question missing required field: {field}")
            
            # Ensure options is a list with exactly 4 items
            if not isinstance(q['options'], list) or len(q['options']) != 4:
                raise Exception(f"Question options must be a list with exactly 4 items")
                
            # Ensure correctAnswer is an integer between 0-3
            if not isinstance(q['correctAnswer'], int) or q['correctAnswer'] < 0 or q['correctAnswer'] > 3:
                raise Exception(f"Question correctAnswer must be an integer between 0-3")
        
            randomize_answer_choices(q)
        
        return questions
    except Exception as e:
        print(f"Error generating focused questions: {str(e)}")
        # Return some default questions if there's an error
        return [
            {
                "id": 1,
                "text": "What aspect of the content needs further review?",
                "options": [
                    "Key terminology",
                    "Core concepts",
                    "Practical applications",
                    "All of the above"
                ],
                "correctAnswer": 3,
                "reason": "This is a fallback question generated when the API request failed."
            },
            {
                "id": 2,
                "text": "Which learning strategy might help reinforce this material?",
                "options": [
                    "Flashcard review",
                    "Practice problems",
                    "Discussion with peers",
                    "Creating concept maps"
                ],
                "correctAnswer": 1,
                "reason": "This is a fallback question generated when the API request failed."
            }
        ]

def extract_text_with_pytesseract(image):
    """Extract text from an image using pytesseract with optimized settings"""
    # Check if tesseract is available
    if not TESSERACT_AVAILABLE:
        print("Tesseract OCR not available - skipping OCR")
        return ""
    
    try:
        # Use pytesseract with optimized configuration for medical/academic text
        # PSM 3 = Fully automatic page segmentation, but no OSD
        # OEM 3 = Default, based on what is available
        # Simplified character whitelist without problematic quotes
        custom_config = r'--oem 3 --psm 3'
        
        # Extract text with custom configuration
        text = pytesseract.image_to_string(image, lang='eng', config=custom_config)
        
        # Clean up the extracted text
        cleaned_text = text.strip()
        
        # Log OCR result quality
        if len(cleaned_text) > 0:
            print(f"OCR extracted {len(cleaned_text)} characters")
        else:
            print("OCR extracted no text")
        
        return cleaned_text
        
    except Exception as e:
        print(f"Error with pytesseract OCR: {str(e)}")
        
        # Fallback: try with minimal configuration
        try:
            print("Trying OCR with minimal configuration...")
            text = pytesseract.image_to_string(image, lang='eng')
            cleaned_text = text.strip()
            print(f"Fallback OCR extracted {len(cleaned_text)} characters")
            return cleaned_text
        except Exception as fallback_error:
            print(f"Fallback OCR also failed: {str(fallback_error)}")
            return ""


def convert_pdf_page_to_image_from_memory(file_obj, page_num):
    """Convert a specific PDF page to an image from a file object in memory"""
    try:
        print(f"Converting page {page_num + 1} to image for OCR...")
        
        # Save file object to a temporary file for pdf2image conversion
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
            file_obj.seek(0)
            temp_pdf.write(file_obj.read())
            temp_pdf_path = temp_pdf.name
        
        print(f"Created temporary PDF: {temp_pdf_path}")
        
        try:
            # Convert PDF page to image with configured quality settings
            images = convert_from_path(
                temp_pdf_path, 
                first_page=page_num + 1,  # PDF pages are 1-indexed
                last_page=page_num + 1,
                dpi=OCR_DPI,  # Use configured DPI
                fmt='png'
            )
            
            if not images:
                print(f"No images generated for page {page_num + 1}")
                return None
            
            print(f"Successfully converted page {page_num + 1} to image ({len(images)} images)")
            
            # Return the first (and only) image
            image = images[0]
            print(f"Image size: {image.size}, mode: {image.mode}")
            return image
            
        finally:
            # Clean up the temporary PDF file
            try:
                os.unlink(temp_pdf_path)
                print(f"Cleaned up temporary PDF: {temp_pdf_path}")
            except Exception as e:
                print(f"Error cleaning up temp PDF file: {str(e)}")
                
    except Exception as e:
        print(f"Error converting PDF page to image from memory: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def extract_text_from_pdf_memory(file_obj, filename=""):
    """Extract text from a PDF file object directly from memory with OCR fallback"""
    final_text = ""
    ocr_pages_count = 0  # Track how many pages needed OCR
    
    try:
        analyze_memory_usage(f"PDF extraction start - {filename}")
        
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
                
                # Check memory before processing each page
                check_memory()
                
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text().strip()
                
                # Check if extracted text is insufficient (less than configured threshold)
                if len(page_text) < OCR_TEXT_THRESHOLD:
                    if TESSERACT_AVAILABLE:
                        print(f"Page {page_num + 1}: Insufficient text ({len(page_text)} chars), trying OCR...")
                        
                        try:
                            # Convert page to image and use OCR
                            page_image = convert_pdf_page_to_image_from_memory(file_obj, page_num)
                            
                            if page_image:
                                ocr_text = extract_text_with_pytesseract(page_image).strip()
                                
                                # Use OCR text if it's significantly better
                                if len(ocr_text) > len(page_text):
                                    print(f"Page {page_num + 1}: OCR extracted {len(ocr_text)} chars (vs {len(page_text)} from PDF)")
                                    print("OCR text")
                                    print(ocr_text)
                                    page_text = ocr_text
                                    ocr_pages_count += 1
                                else:
                                    print(f"Page {page_num + 1}: OCR didn't improve text extraction ({len(ocr_text)} chars)")
                                
                                # Clean up image to save memory
                                del page_image
                            else:
                                print(f"Page {page_num + 1}: Failed to convert to image for OCR")
                                
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
        elif TESSERACT_AVAILABLE:
            print(f"All {num_pages} pages had sufficient text, no OCR needed")
        else:
            insufficient_pages = sum(1 for page_num in range(num_pages) 
                                   if len(pdf_reader.pages[page_num].extract_text().strip()) < OCR_TEXT_THRESHOLD)
            if insufficient_pages > 0:
                print(f"Note: {insufficient_pages}/{num_pages} pages had insufficient text but OCR was unavailable")
            else:
                print(f"All {num_pages} pages had sufficient text (OCR not needed)")
        
        analyze_memory_usage(f"PDF extraction complete - {filename}")
        return final_text.strip()
        
    except Exception as e:
        print(f"Error extracting text from PDF in memory: {str(e)}")
        analyze_memory_usage(f"PDF extraction error - {filename}")
        # Force cleanup on error
        gc.collect()
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
    """Check if system has enough memory with proactive garbage collection and container awareness"""
    try:
        memory_limit = get_container_memory_limit()
        memory_used = get_container_memory_usage()
        memory_percent = (memory_used / memory_limit) * 100
        
        if memory_percent > 75:  # Lower threshold for containers (was 85%)
            print(f"High memory usage detected: {memory_percent:.1f}% - forcing garbage collection")
            gc.collect()  # Force garbage collection
            
            # Check again after garbage collection
            memory_used = get_container_memory_usage()
            memory_percent = (memory_used / memory_limit) * 100
            print(f"Memory after GC: {memory_percent:.1f}%")
            
        if memory_percent > 90:  # Critical threshold for containers (was 95%)
            print(f"Memory usage critical: {memory_percent:.1f}% ({memory_used/(1024*1024):.1f}MB/{memory_limit/(1024*1024):.1f}MB)")
        
        return memory_percent
        
    except Exception as e:
        if "Memory usage critical" in str(e):
            raise  # Re-raise critical memory errors
        
        print(f"Error in container memory check: {e}")
        # Fallback to psutil
        memory = psutil.virtual_memory()
        
        if memory.percent > 85:
            print(f"High memory usage detected (host): {memory.percent}% - forcing garbage collection")
            gc.collect()
            memory = psutil.virtual_memory()
            
        if memory.percent > 95:
            print(f"Memory usage critical (host): {memory.percent}%")
        
        return memory.percent

def analyze_memory_usage(stage):
    """Detailed memory analysis to identify memory consumers"""
    try:
        current_process = psutil.Process()
        memory_info = current_process.memory_info()
        memory_percent = current_process.memory_percent()
        
        # Get number of open file descriptors
        try:
            num_fds = current_process.num_fds()
        except:
            num_fds = "N/A"
        
        # Get thread count
        num_threads = current_process.num_threads()
        
        # Try to get container memory for comparison
        container_memory = None
        try:
            with open('/sys/fs/cgroup/memory.current', 'r') as f:
                container_memory = int(f.read().strip())
        except:
            try:
                with open('/sys/fs/cgroup/memory/memory.usage_in_bytes', 'r') as f:
                    container_memory = int(f.read().strip())
            except:
                pass
        
        print(f"=== Memory Analysis at {stage} ===")
        print(f"Process RSS (Physical): {memory_info.rss/(1024*1024):.1f}MB")
        print(f"Process VMS (Virtual): {memory_info.vms/(1024*1024):.1f}MB")
        if container_memory:
            print(f"Container Memory (cgroups): {container_memory/(1024*1024):.1f}MB")
            print(f"Difference (Container - Process): {(container_memory - memory_info.rss)/(1024*1024):.1f}MB")
        print(f"Memory %: {memory_percent:.1f}%")
        print(f"Threads: {num_threads}")
        print(f"File descriptors: {num_fds}")
        
        # Check for memory leaks by looking at object counts
        import sys
        print(f"Python objects: {len(gc.get_objects())}")
        
        # Return container memory if available, otherwise process memory
        return container_memory if container_memory else memory_info.rss
        
    except Exception as e:
        print(f"Error in memory analysis: {e}")
        return 0



