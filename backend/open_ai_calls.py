from dotenv import load_dotenv
from openai import OpenAI
import os
import json
import time
import uuid
import random
import traceback
import hashlib
from .logic import log_memory_usage, check_memory, analyze_memory_usage
from .database import upsert_quiz_questions_batch

load_dotenv()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
    prompt = f"""Create a comprehensive, detailed study guide/summary from this transcript that covers ALL content thoroughly.

    CRITICAL REQUIREMENTS:
    - You MUST read and analyze the ENTIRE transcript from beginning to end, no matter how long it is
    - Do NOT skip any sections, pages, or content - process everything completely
    - Include information from EVERY single page, section, paragraph, and sentence of the transcript
    - Focus on high-yield information for USMLE, COMLEX, and medical school exams
    - Include ALL key concepts, clinical correlates, and important details mentioned throughout
    - Provide real-world examples and clinical applications
    - Make this as comprehensive and detailed as possible - leave nothing out
    - Structure the content logically with clear organization
    - If the transcript is very long, take your time to process it completely and thoroughly

    FORMAT REQUIREMENTS:
    - Use Markdown formatting throughout
    - Use headers (# for main sections, ## for subsections)
    - Use bold (**text**) for key terms and important concepts
    - Use italics (*text*) for emphasis and definitions
    - Use bulleted lists (-) for key points and examples
    - Use numbered lists (1.) for step-by-step processes
    - Include tables where appropriate for comparisons
    - Use blockquotes (>) for important clinical pearls

    IMPORTANT: This transcript contains {len(text)} characters. Please ensure you process every single character and include all details in your summary.

    Transcript:
    {text}
    """

    completion = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert medical educator and USMLE/COMLEX tutor with extensive experience creating comprehensive study materials. Your goal is to create the most thorough, detailed, and well-organized study guides possible. You excel at identifying high-yield content, explaining complex concepts clearly, and structuring information in ways that maximize learning and retention. Always double-check your responses for accuracy and completeness."},
            {"role": "user", "content": prompt},
        ],
        temperature=1.2,
        presence_penalty=0.6,
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

def generate_quiz_questions(summary_text, user_id, content_hash, incorrect_question_ids=None, previous_questions=None, num_questions=5, is_quiz_mode=True):
    """Generate quiz questions from a summary text using OpenAI's API
    
    Args:
        summary_text: The text to generate questions from
        user_id: User ID for question hashing
        content_hash: Content hash for question set
        incorrect_question_ids: Optional list of IDs of questions answered incorrectly
        previous_questions: Optional list of previous questions for focused generation
        num_questions: Number of questions to generate (default: 5)
    
    Returns:
        tuple: (questions, question_hashes)
    """
    
    log_memory_usage("quiz generation start")
    
    try:

        quiz_schema = {
            "type": "object",
            "required": ["questions"],
            "additionalProperties": False,
            "properties": {
                "questions": {
                    "type": "array",
                    "minItems": num_questions,
                    "maxItems": num_questions,
                    "items": {
                        "type": "object",
                        "required": ["id", "text", "options", "correctAnswer", "reason"],
                        "properties": {
                            "id":           {"type": "integer", "minimum": 1, "maximum": num_questions},
                            "text":         {"type": "string"},
                            "options": {
                                "type": "array",
                                "minItems": 4,
                                "maxItems": 4,
                                "items": {"type": "string"}
                            },
                            "correctAnswer": {"type": "integer", "minimum": 0, "maximum": 3},
                            "reason":       {"type": "string"}
                        },
                        "additionalProperties": False
                    }
                }
            }
        }

        is_questions = previous_questions is not None and incorrect_question_ids is not None

        incorrect_questions = []
        correct_questions = []
        if is_questions:
            incorrect_questions = [q['text'] for q in previous_questions if q['id'] in incorrect_question_ids]
            correct_questions = [q['text'] for q in previous_questions if q['id'] not in incorrect_question_ids]

        previous_questions_text = ""
        if len(incorrect_questions) > 0:
            previous_questions_text += f"The user previously answered the following questions INCORRECTLY and should be tested on these topics as well as others mentioned in the summary:\n{json.dumps(incorrect_questions)}\n"
        if len(correct_questions) > 0:
            previous_questions_text += f"The user previously answered the following questions CORRECTLY and should be tested on different topics mentioned in the summary:\n{json.dumps(correct_questions)}\n"

        print("previous_questions_text")
        print(previous_questions_text)
        print(f"is_quiz_mode: {is_quiz_mode}")
        if is_quiz_mode:
            prompt = f"""
            Based on the following medical text summary, create {num_questions} VERY challenging USMLE clinical vignette style \
                multiple-choice questions to test the student's understanding. Make sure to include all the key concepts and information from the summary.
            
            {previous_questions_text}

            For each question:
            1. A clear, specific and challenging clinical vignette stem.
            2. Be in the style of a USMLE clinical vignette (Example clinical vignette stem: "A 62-year-old man presents to the emergency department with shortness of breath and chest discomfort that began two hours ago while he was watching television. He describes the discomfort as a vague pressure in the center of his chest, without radiation. He denies any nausea or diaphoresis. He has a history of hypertension, type 2 diabetes mellitus, and hyperlipidemia. He is a former smoker (40 pack-years, quit 5 years ago). On examination, his blood pressure is 146/88 mmHg, heart rate is 94/min, respiratory rate is 20/min, and oxygen saturation is 95% on room air. Cardiac auscultation reveals normal S1 and S2 without murmurs. Lungs are clear to auscultation bilaterally. There is no jugular venous distension or peripheral edema. ECG reveals normal sinus rhythm with 2 mm ST-segment depressions in leads V4–V6. Cardiac biomarkers are pending. Which of the following is the most appropriate next step in management?")
            3. Include a thorough explanation for why the correct answer is right and why others are wrong (Dont include the answer index in the reason)
            
            Summary:
            {summary_text}
            """

            system_prompt = """
            You are an expert medical professor that creates 
            accurate, challenging USMLE clinical vignette style multiple choice questions. 
            Generate ONLY valid JSON matching the provided schema.
            """
        else:
            prompt = f"""
            Based on the following medical text summary, create {num_questions} VERY challenging
                multiple-choice questions to test the student's understanding. Make sure to include all the key concepts and information from the summary.
            
            {previous_questions_text}

            For each question:
            1. A clear, specific, and concise question stem for active recall flashcards. Do not include the answer in the question stem or suggest there are multiple answers.
            2. Simple multiple choice questions based on the summary.
            3. Include a thorough explanation for why the correct answer is right and why others are wrong (Dont include the answer index in the reason)
            
            Summary:
            {summary_text}
            """

            system_prompt = """
            You are an expert medical professor that creates 
            accurate, challenging multiple choice questions. 
            Generate ONLY valid JSON matching the provided schema.
            """
                
        gpt_time_start = time.time()
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "quiz_questions",
                    "strict": True,
                    "schema": quiz_schema
                }
            },
            temperature=0.9,
            presence_penalty=0.6,
            max_completion_tokens=3000,  # Increased for more questions
            top_p=0.9,
            frequency_penalty=0.25,
        )
        gpt_time_end = time.time()
        print(f"GPT time: {gpt_time_end - gpt_time_start} seconds")

        response_text = response.choices[0].message.content.strip()
        
        response_json = json.loads(response_text)
        questions = response_json["questions"]
        
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

        # If validation is successful, randomize and store in database
        for q in questions:
            randomize_answer_choices(q)

        questions_with_ids = []
        question_hashes = []

        for q in questions:
            q['id'] = str(uuid.uuid4())
            question_text = q.get('text', '')
            
            # Create a hash for the question content
            question_hash = hashlib.sha256((question_text + str(user_id)).encode('utf-8')).hexdigest()
            question_hashes.append(question_hash)
            q['hash'] = question_hash

            questions_with_ids.append({
                "hash": question_hash,
                "question": q,
                "user_id": user_id,
                "question_set_hash": content_hash
            })
        
        # Batch upsert all questions
        db_result = upsert_quiz_questions_batch(questions_with_ids)
        if db_result["success"]:
            print(f"Successfully stored {db_result['count']} quiz questions in database (batch)")
        else:
            print(f"Failed to store quiz questions: {db_result.get('error', 'Unknown error')}")

        log_memory_usage("quiz generation complete")
        return questions, question_hashes

    except (json.JSONDecodeError, ValueError) as e:
        print(f"Failed to get valid JSON. Error: {e}")
        raise Exception(f"Failed to get valid JSON response from AI: {e}")
    
    except Exception as e:
        print(f"An unexpected error occurred in generate_quiz_questions: {e}")
        traceback.print_exc()
        raise e

def generate_short_title(text_to_summarize: str) -> str:
    """
    Generates a short, max 10-word title for a given text.

    Args:
        text_to_summarize (str): The text to summarize into a title.

    Returns:
        str: A title of 10 words or less.
    """
    if not text_to_summarize:
        return "Untitled"

    try:
        # We only need the beginning of the text to generate a title
        prompt = f"""
        Based on the following text, create a very short, concise title.
        The title must be a maximum of 10 words.
        Do not use quotes or any introductory phrases like "Title:".
        
        Text:
        {text_to_summarize}
        """

        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at creating short, descriptive titles from text. You always follow length constraints and instructions precisely."},
                {"role": "user", "content": prompt},
            ],
            presence_penalty=0.5,
            temperature=1.2,
            max_tokens=25,  # Generous buffer for 10 words
            n=1,
            stop=None,
        )

        title = completion.choices[0].message.content.strip()

        # Enforce the 10-word limit just in case
        words = title.split()
        if len(words) > 10:
            title = " ".join(words[:10])

        print(f"Generated short title: {title}")
        return title

    except Exception as e:
        print(f"Error generating short title: {e}")
        # Fallback title in case of an error
        return "Untitled" 