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



load_dotenv()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
tesseract_custom_path = os.getenv("TESSERACT_PATH")
if tesseract_custom_path:
    pytesseract.pytesseract.tesseract_cmd = tesseract_custom_path

def gpt_summarize_transcript(text):
    prompt = f"Provide me with detailed and thorough study guide using full sentences based on this transcript. Include relevant headers for each topic. Be sure to include the mentioned clinical correlates. Transcript:{text}"

    completion = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful teaching assistant \
             for US medical school. You are extremely knowledgable and \
             want your students to succeed by providing them with extremely detailed and thorough study guides. \
             You also double check all your responses for accuracy."},
            {"role": "user", "content": prompt},
        ],
    )

    # Parse the response into lines
    text = completion.choices[0].message.content.strip()
    return text

def generate_quiz_questions(summary_text, request_id=None):
    """Generate quiz questions from a summary text using OpenAI's API"""
    if request_id is None:
        request_id = str(uuid.uuid4())[:8]
    
    try:
        prompt = f"""
        Based on the following medical text summary, create 5 multiple-choice questions to test the reader's understanding. 
        
        For each question:
        1. Create a clear, specific question about key concepts in the text
        2. Provide exactly 4 answer choices labeled A, B, C, and D
        3. Indicate which answer is correct
        4. Include a brief explanation for why the correct answer is right
        
        Format the response as a JSON array of question objects. Each question object should have these fields:
        - id: a unique number (1-5)
        - text: the question text
        - options: array of 4 answer choices
        - correctAnswer: index of correct answer (0-3)
        - reason: explanation for the correct answer
        
        Summary:
        {summary_text}
        
        Return ONLY the valid JSON array with no other text.
        """

        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful medical education assistant that creates accurate, challenging multiple choice questions. You respond ONLY with the requested JSON format."},
                {"role": "user", "content": prompt},
            ],
        )

        # Get JSON response
        response_text = completion.choices[0].message.content.strip()
        print("response_text")
        print(response_text)
        
        # Sometimes the API returns markdown json blocks, so let's clean that up
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
        prompt = f"""
        Based on the following medical text summary, create 5 new multiple-choice questions.
        
        The user previously struggled with these specific concepts:
        {json.dumps(incorrect_questions) if incorrect_questions else "No specific areas - generate new questions on the key topics"}
        
        For each question:
        1. Create challenging but fair questions that test understanding of key concepts
        2. If the user struggled with specific areas above, focus at least 3 questions on similar topics
        3. Provide exactly 4 answer choices
        4. Indicate which answer is correct
        5. Include a thorough explanation for why the correct answer is right and why others are wrong
        
        Format the response as a JSON array of question objects. Each question object should have these fields:
        - id: a unique number (1-5)
        - text: the question text
        - options: array of 4 answer choices
        - correctAnswer: index of correct answer (0-3)
        - reason: explanation for the correct answer
        
        Summary:
        {summary_text}
        
        Return ONLY the valid JSON array with no other text.
        """

        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful medical education assistant that creates accurate, challenging multiple choice questions to help students improve in areas they struggled with. You respond ONLY with the requested JSON format."},
                {"role": "user", "content": prompt},
            ],
        )

        # Get JSON response
        response_text = completion.choices[0].message.content.strip()
        print("response_text")
        print(response_text)
        
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
    min_text_length = 50  # Minimum characters to consider text sufficient
    
    try:
        # Get direct text extraction first
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            num_pages = len(pdf_reader.pages)
            
            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                PyPDF2_combined_text += f"[Page {page_num + 1}]:\n{page_text}\n\n"
                
                # # OCR causes OOM error
                # # Check if the extracted text is too short
                # if len(page_text.strip()) < min_text_length:
                #     # Text is too short, use OCR instead
                #     print(f"Text is too short, using OCR for page {page_num + 1}")
                #     image = convert_pdf_page_to_image(pdf_path, page_num)
                #     if image:
                #         ocr_text = extract_text_with_pytesseract(image)
                #         if ocr_text:
                #             # Use OCR text for this page
                #             final_text += f"[Page {page_num + 1}]:\n{ocr_text}\n\n"
                #             pytesseract_combined_text += f"[OCR Page {page_num + 1}]:\n{ocr_text}\n\n"
                #             continue
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


