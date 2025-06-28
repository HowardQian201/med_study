from dotenv import load_dotenv
from openai import OpenAI
import psutil
import platform
import os
import PyPDF2
import requests
import json
import time
import uuid
import random
import gc
from io import BytesIO
import traceback
import boto3
from botocore.client import Config
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

load_dotenv()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OCR_API_KEY = os.getenv("OCR_API_KEY", "helloworld")


# Configuration constants
OCR_AVAILABLE = True
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

def gpt_summarize_transcript(text, stream=False):
    print(f"gpt_summarize_transcript called with stream={stream}")
    gpt_time_start = time.time()
    prompt = f"""Provide me with a detailed, thorough, and comprehensive study guide/summary based on this transcript. 
        The output should be in Markdown format. 
        Use Markdown for structure, including headers (#, ##), bold text (**bold**), italics (*italics*), and bulleted lists (-) to organize the information clearly. 
        Ensure all key information and mentioned clinical correlates are included.
        Give explanations with real world examples. 
        
        Transcript:
        {text}
        """

    completion = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful teaching assistant \
             for US medical school. You are extremely knowledgable and \
             want your students to succeed by providing them with extremely detailed and thorough study guides/summaries. \
             You also double check all your responses for accuracy."},
            {"role": "user", "content": prompt},
        ],
        temperature = 1.2,
        presence_penalty = 0.6,
        stream=stream,
    )

    if stream:
        return completion

    print("gpt_summarize_transcript completion")
    gpt_time_end = time.time()
    print(f"GPT time: {gpt_time_end - gpt_time_start} seconds")
    analyze_memory_usage("gpt_summarize_transcript completion")

    # Parse the response into lines
    text = completion.choices[0].message.content.strip()
    return text

def generate_quiz_questions(summary_text, request_id=None):
    """Generate quiz questions from a summary text using OpenAI's API"""
    if request_id is None:
        request_id = str(uuid.uuid4())[:8]

    log_memory_usage("quiz generation start")
    
    prompt = f"""
    Based on the following medical text summary, create 5 VERY challenging USMLE clinical vignette style \
        multiple-choice questions to test the student's understanding. 
    
    For each question:
    1. Create a clear, specific, and very challenging question about key concepts in the text
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

    max_retries = 3
    for attempt in range(max_retries):
        try:
            check_memory()  # Check memory before API call
            
            gpt_time_start = time.time()
            completion = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert medical professor that creates \
                    accurate, challenging multiple choice questions in the style of clinical vignettes. \
                    You respond ONLY with the requested JSON format."},
                    {"role": "user", "content": prompt},
                ],
                temperature=1.2,
                presence_penalty=0.6,
            )
            gpt_time_end = time.time()
            print(f"GPT time (attempt {attempt + 1}): {gpt_time_end - gpt_time_start} seconds")
            log_memory_usage(f"after OpenAI API call (attempt {attempt + 1})")

            response_text = completion.choices[0].message.content.strip()
            
            if response_text.startswith("```json"):
                response_text = response_text.replace("```json", "", 1).strip()
            if response_text.endswith("```"):
                response_text = response_text.rsplit("```", 1)[0].strip()
            
            questions = json.loads(response_text)
            
            # Validate structure
            if not isinstance(questions, list) or not questions:
                raise ValueError("Response is not a list or is empty.")
            
            for q in questions:
                required_fields = ['id', 'text', 'options', 'correctAnswer', 'reason']
                if not all(field in q for field in required_fields):
                    raise ValueError(f"Question missing required fields: {q}")
                if not isinstance(q.get('options'), list) or len(q['options']) != 4:
                    raise ValueError(f"Question options is not a list of 4: {q}")
                if not isinstance(q.get('correctAnswer'), int) or not (0 <= q['correctAnswer'] <= 3):
                    raise ValueError(f"Invalid correctAnswer: {q}")

            # If validation is successful, randomize and return
            for q in questions:
                randomize_answer_choices(q)
            
            log_memory_usage("quiz generation complete")
            return questions

        except (json.JSONDecodeError, ValueError) as e:
            print(f"Attempt {attempt + 1} failed to get valid JSON. Error: {e}")
            if attempt < max_retries - 1:
                print("Retrying...")
                time.sleep(1)  # Wait for a second before retrying
            else:
                print("Max retries reached. Failing.")
                raise Exception("Failed to get valid JSON response from AI after multiple attempts.")
        
        except Exception as e:
            print(f"An unexpected error occurred in generate_quiz_questions: {e}")
            traceback.print_exc()
            raise e

    raise Exception("Failed to generate quiz questions after all retries.")

def generate_focused_questions(summary_text, incorrect_question_ids, previous_questions):
    """Generate more targeted quiz questions focusing on areas where the user had difficulty"""
    # Extract incorrect questions
    incorrect_questions = []
    if previous_questions and incorrect_question_ids:
        incorrect_questions = [q['text'] for q in previous_questions if q['id'] in incorrect_question_ids]
    
    # Create a prompt with more focus on areas the user missed
    print("incorrect_questions")
    print({json.dumps(incorrect_questions) if incorrect_questions else "No specific areas - generate new questions on the key topics"})

    prompt = f"""
    Based on the following medical text summary and struggled concepts, create 5 VERY challenging USMLE clinical vignette style multiple-choice questions.
    
    The user previously struggled with these specific concepts:
    {json.dumps(incorrect_questions) if incorrect_questions else "No specific areas - generate new questions on the key topics"}
    
    For each question:
    1. Create very challenging questions that test understanding of key concepts
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

    max_retries = 3
    for attempt in range(max_retries):
        try:
            check_memory()
            gpt_time_start = time.time()
            completion = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert medical professor that creates \
                    accurate, challenging multiple choice questions in the style of clinical vignettes. \
                    You respond ONLY with the requested JSON format."},
                    {"role": "user", "content": prompt},
                ],
                temperature=1.2,
                presence_penalty=0.6,
            )

            gpt_time_end = time.time()
            print(f"GPT time (attempt {attempt + 1}): {gpt_time_end - gpt_time_start} seconds")
            log_memory_usage(f"after OpenAI 2 API call (attempt {attempt + 1})")
            
            response_text = completion.choices[0].message.content.strip()
            
            if response_text.startswith("```json"):
                response_text = response_text.replace("```json", "", 1).strip()
            if response_text.endswith("```"):
                response_text = response_text.rsplit("```", 1)[0].strip()
            
            questions = json.loads(response_text)
            
            # Validate structure
            if not isinstance(questions, list) or not questions:
                raise ValueError("Response is not a list or is empty.")
                
            for q in questions:
                required_fields = ['id', 'text', 'options', 'correctAnswer', 'reason']
                if not all(field in q for field in required_fields):
                    raise ValueError(f"Question missing required fields: {q}")
                if not isinstance(q.get('options'), list) or len(q['options']) != 4:
                    raise ValueError(f"Question options is not a list of 4: {q}")
                if not isinstance(q.get('correctAnswer'), int) or not (0 <= q['correctAnswer'] <= 3):
                    raise ValueError(f"Invalid correctAnswer: {q}")
            
            # If validation is successful, randomize and return
            for q in questions:
                randomize_answer_choices(q)
            
            return questions

        except (json.JSONDecodeError, ValueError) as e:
            print(f"Attempt {attempt + 1} failed to get valid JSON for focused questions. Error: {e}")
            if attempt < max_retries - 1:
                print("Retrying...")
                time.sleep(1) # Wait for a second before retrying
            else:
                print("Max retries reached. Failing.")
                raise Exception("Failed to get valid JSON for focused questions after multiple attempts.")

        except Exception as e:
            print(f"An unexpected error occurred in generate_focused_questions: {e}")
            traceback.print_exc()
            raise e

    raise Exception("Failed to generate focused questions after all retries.")

def extract_text_with_ocr_from_pdf(file_obj, page_num):
    """Extract text from a specific PDF page using OCR.space API directly"""
    try:
        # Create a new PDF with just the target page
        file_obj.seek(0)
        pdf_reader = PyPDF2.PdfReader(file_obj)
        
        # Create a new PDF writer with just the target page
        pdf_writer = PyPDF2.PdfWriter()
        pdf_writer.add_page(pdf_reader.pages[page_num])
        
        # Write the single page to a BytesIO buffer
        page_buffer = BytesIO()
        pdf_writer.write(page_buffer)
        page_buffer.seek(0)
        
        payload = {
            'apikey': OCR_API_KEY,
            'language': 'eng',
            'isOverlayRequired': False,
            'filetype': 'PDF'
        }

        files = {'file': (f'page_{page_num + 1}.pdf', page_buffer, 'application/pdf')}

        print("before OCR API call")
        ocr_time_start = time.time()
        try:
            response = requests.post('https://api.ocr.space/parse/image',
                                     data=payload, files=files, timeout=10)
            ocr_time_end = time.time()
            print("after OCR API call")
            print(f"OCR time: {ocr_time_end - ocr_time_start} seconds")
        except requests.exceptions.Timeout:
            print(f"OCR API call timed out after 10 seconds for page {page_num + 1}")
            return ""
        except requests.exceptions.RequestException as req_error:
            print(f"OCR API request failed for page {page_num + 1}: {str(req_error)}")
            return ""

        # Check if the response status is OK
        if response.status_code != 200:
            print(f"OCR API returned status code {response.status_code} for page {page_num + 1}")
            print(f"Response text: {response.text[:200]}")
            return ""

        # Try to parse JSON response
        try:
            result = response.json()
        except Exception as json_error:
            print(f"Failed to parse JSON response for page {page_num + 1}: {str(json_error)}")
            print(f"Response text: {response.text[:200]}")
            return ""

        # Check if result is a string (error case)
        if isinstance(result, str):
            print(f"OCR API returned error string for page {page_num + 1}: {result}")
            return ""

        if result.get('IsErroredOnProcessing'):
            print(f"OCR failed for page {page_num + 1}: {result.get('ErrorMessage', 'Unknown error')}")
            return ""

        # Check if ParsedResults exists and has content
        if not result.get('ParsedResults') or len(result['ParsedResults']) == 0:
            print(f"OCR failed for page {page_num + 1}: No parsed results returned")
            return ""
            
        text = result['ParsedResults'][0]['ParsedText']
        print(f"OCR extracted {len(text)} characters from page {page_num + 1}")
        return text
                
    except Exception as e:
        print(f"Error in OCR processing for page {page_num + 1}: {str(e)}")
        traceback.print_exc()
        return ""


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
