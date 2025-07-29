from dotenv import load_dotenv
from openai import AsyncOpenAI # Changed to AsyncOpenAI
import os
import json
import time
import uuid
import random
import traceback
import hashlib
from .database import upsert_quiz_questions_batch

load_dotenv()
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=600.0) # Changed to AsyncOpenAI

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

async def gpt_summarize_transcript(text, temperature=1.0, stream=False): # Changed to async def
    # Generate random number between 1-50 for question ID
    random_id = random.randint(1, 50)
    print(f"gpt_summarize_transcript called random_id: {random_id}, stream: {stream}")

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

    completion = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert medical educator and USMLE/COMLEX tutor with extensive experience creating comprehensive study materials. Your goal is to create the most thorough, detailed, and well-organized study guides possible. You excel at identifying high-yield content, explaining complex concepts clearly, and structuring information in ways that maximize learning and retention. Always double-check your responses for accuracy and completeness."},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        frequency_penalty=0.25,
        stream=stream,
    )
    print(f"gpt_summarize_transcript returning random_id: {random_id}")

    if stream:
        return completion

    print("gpt_summarize_transcript completion")
    gpt_time_end = time.time()
    print(f"GPT time: {gpt_time_end - gpt_time_start} seconds")

    # Parse the response into lines
    text = completion.choices[0].message.content.strip()
    return text

async def generate_quiz_questions(summary_text, user_id, content_hash, incorrect_question_ids=None, previous_questions=None, num_questions=5, is_quiz_mode=True, model="gpt-4o-mini"): # Changed to async def
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
    
    try:

        is_questions = previous_questions is not None and incorrect_question_ids is not None

        incorrect_questions = []
        correct_questions = []
        if is_questions:
            incorrect_questions = [q['text'] for q in previous_questions if q['id'] in incorrect_question_ids]
            correct_questions = [q['text'] for q in previous_questions if q['id'] not in incorrect_question_ids]

        print(f"is_quiz_mode: {is_quiz_mode}")
        
        if is_quiz_mode:
            max_completion_tokens = 7000
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
            prompt = f'''
            Based on the following medical text summary, create {num_questions} VERY challenging USMLE clinical vignette style \
                multiple-choice questions to test the student's understanding. Make sure to include all the key concepts and information from the summary.
            
            Requirements:
            1. Clear, specific and challenging clinical vignette stems (about 400 characters).
            2. Question stems must be in the style of a USMLE clinical vignette 
            3. Include a thorough explanation (about 500 characters) for why the correct answer is right and why others are wrong. Do not include the answer index in the reason.
            4. Aim for clarity, clinical relevance, and high-yield facts

            Example question fromat:
            [
                {{
                    "id": 1,
                    "text": "A 34-year-old man presents to the emergency department with 5 days of worsening shortness of breath, orthopnea, and a nonproductive cough. He has no significant past medical history. Vitals show BP 110/70 mmHg, HR 105/min, and RR 22/min. Jugular venous distention is noted, and auscultation reveals bilateral crackles. ECG shows low-voltage QRS complexes. A chest x-ray demonstrates an enlarged cardiac silhouette. What is the most appropriate next step?",
                    "options": [
                        "Start loop diuretics",
                        "Order a transthoracic echocardiogram",
                        "Begin corticosteroid therapy",
                        "Perform emergent cardiac catheterization"
                    ],
                    "correctAnswer": 2,
                    "reason": "The patient presents with signs of acute heart failure and pericardial effusion (dyspnea, JVD, low-voltage ECG, enlarged cardiac silhouette). These findings raise concern for cardiac tamponade, which can be rapidly fatal. The most appropriate next step is a transthoracic echocardiogram to evaluate for pericardial fluid and assess for signs of tamponade physiology such as diastolic collapse of the right heart chambers."
                }},
                ...
            ]

            Summary:
            {summary_text}
            '''

            system_prompt = """
            You are an expert medical professor that creates 
            accurate, challenging USMLE clinical vignette style multiple choice questions. 
            Output **only** valid JSON exactly matching the schema below.
            """
        else:
            max_completion_tokens = 5000
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
            prompt = f'''
            Based on the following medical text summary, create {num_questions}
            active‑recall flashcards that cover every key concept.

            Requirements:
            1. Clear, specific, and concise question stems for active recall flashcards (about 100 characters). Do not include the answer in the question stem or suggest there are multiple answers.
            2. Simple, direct active recall flashcard/multiple choice questions based on the summary.
            3. Include a thorough explanation (about 500 characters) for why the correct answer is right and why others are wrong. Do not include the answer index in the reason.
            4. Aim for clarity, clinical relevance, and high-yield facts
            5. Each flashcard must contain one clear fact.

            Example flashcard format:
            [
                {{
                    "id": 1,
                    "text": "Which cytokine is most critical for Th1 differentiation?",
                    "options": ["IL-12", "TGF-β", "IL-4", "IL-10"],
                    "correctAnswer": 0,
                    "reason": "IL-12 is essential for naïve CD4+ T cells to differentiate into Th1 cells. It activates STAT4, a transcription factor that upregulates T-bet, the master regulator of Th1 lineage commitment. T-bet then promotes the production of IFN-γ, the key Th1 cytokine, which amplifies the Th1 response. In contrast, IL-4 promotes Th2 differentiation, IL-6 supports Th17 development, and IL-10 suppresses inflammatory responses, including Th1 activity."
                }},
                ...
            ]

            Summary:
            {summary_text}
            '''

            system_prompt = """
            You are an expert medical professor that creates 
            accurate, active recall flashcard/multiple choice questions. 
            Output **only** valid JSON exactly matching the schema below.
            """
        
        print(f"Using model: {model} for quiz generation USMLE mode: {is_quiz_mode} with max completion tokens: {max_completion_tokens}")
        gpt_time_start = time.time()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        if correct_questions and len(correct_questions) > 0:
            messages.append({"role": "user", "content": f"Generate {num_questions} new questions that are cover entirely different topics from the questions below. \n\n{json.dumps(correct_questions)}"})
        

        response = await openai_client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "quiz_questions",
                    "strict": True,
                    "schema": quiz_schema
                }
            },
            temperature=0.2,
            presence_penalty=0.0,
            max_completion_tokens=max_completion_tokens,
            top_p=0.9,
            frequency_penalty=0.2,
        )
        print(f"Completion tokens used: {response.usage.completion_tokens}")
        gpt_time_end = time.time()
        print(f"GPT time: {gpt_time_end - gpt_time_start} seconds")

        response_text = response.choices[0].message.content.strip()
        # print("\n--- Raw OpenAI Response Text (Quiz Generation) ---")
        # print(response_text)
        # print("--------------------------------------------------\n")
        
        response_json = json.loads(response_text)
        questions = response_json["questions"]
        
        # Validate structure
        if not isinstance(questions, list) or not questions:
            raise ValueError("Response is not a list or is empty.")
        
        for q in questions:
            required_fields = ['id', 'text', 'options', 'correctAnswer', 'reason']
            if not all(field in q for field in required_fields):
                raise ValueError(f"Question missing required fields: {q}")
            if not isinstance(q.get('options'), list) or len(q['options']) not in [1, 4]:
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
            question_hash = hashlib.sha256((question_text + q['id'] + str(user_id)).encode('utf-8')).hexdigest()
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

        return questions, question_hashes

    except (json.JSONDecodeError, ValueError) as e:
        print(f"Failed to get valid JSON. Error: {e}")
        raise Exception(f"Failed to get valid JSON response from AI: {e}")
    
    except Exception as e:
        print(f"An unexpected error occurred in generate_quiz_questions: {e}")
        traceback.print_exc()
        raise e

async def generate_short_title(text_to_summarize: str) -> str: # Changed to async def
    """
    Generates a short, max 8-word title for a given text.

    Args:
        text_to_summarize (str): The text to summarize into a title.

    Returns:
        str: A title of 8 words or less.
    """
    if not text_to_summarize:
        return "Untitled"

    try:
        prompt = f"""
        Based on the following text, create a very short, concise title.
        The title must be a maximum of 8 words.
        Do not use quotes or any introductory phrases like "Title:" or "Summary".
        
        Text:
        {text_to_summarize}
        """

        completion = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at creating short, descriptive titles from text. You always follow length constraints and instructions precisely."},
                {"role": "user", "content": prompt},
            ],
            temperature=1.0,
            max_tokens=20,  # Generous buffer for 10 words
            n=1,
            stop=None,
        )

        title = completion.choices[0].message.content.strip()

        # Enforce the 8-word limit just in case
        words = title.split()
        if len(words) > 8:
            title = " ".join(words[:8])

        print(f"Generated short title: {title}")
        return title

    except Exception as e:
        print(f"Error generating short title: {e}")
        # Fallback title in case of an error
        return "Untitled" 