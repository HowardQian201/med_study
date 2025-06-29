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

def generate_quiz_questions(summary_text):
    """Generate quiz questions from a summary text using OpenAI's API"""
    
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

            # If validation is successful, randomize and store in database
            for q in questions:
                randomize_answer_choices(q)

            # Store questions in database - hash each question individually and batch upsert
            try:
                # Prepare batch data with individual hashes
                batch_data = []
                for question in questions:
                    # Generate a hash for this specific question
                    question_text = json.dumps(question, sort_keys=True)
                    question_hash = hashlib.sha256(question_text.encode('utf-8')).hexdigest()
                    
                    batch_data.append({
                        "hash": question_hash,
                        "question": question
                    })
                
                # Batch upsert all questions
                db_result = upsert_quiz_questions_batch(batch_data)
                if db_result["success"]:
                    print(f"Successfully stored {db_result['count']} quiz questions in database (batch)")
                else:
                    print(f"Failed to store quiz questions: {db_result.get('error', 'Unknown error')}")
            except Exception as e:
                print(f"Error storing quiz questions in database: {str(e)}")
                # Don't fail the entire operation if database storage fails
            
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
            
            # If validation is successful, randomize and store in database
            for q in questions:
                randomize_answer_choices(q)

            # Store questions in database - hash each question individually and batch upsert
            try:
                # Prepare batch data with individual hashes
                batch_data = []
                for question in questions:
                    # Generate a hash for this specific question
                    question_text = json.dumps(question, sort_keys=True)
                    question_hash = hashlib.sha256(question_text.encode('utf-8')).hexdigest()
                    
                    batch_data.append({
                        "hash": question_hash,
                        "question": question
                    })
                
                # Batch upsert all questions
                db_result = upsert_quiz_questions_batch(batch_data)
                if db_result["success"]:
                    print(f"Successfully stored {db_result['count']} focused quiz questions in database (batch)")
                else:
                    print(f"Failed to store focused quiz questions: {db_result.get('error', 'Unknown error')}")
            except Exception as e:
                print(f"Error storing focused quiz questions in database: {str(e)}")
                # Don't fail the entire operation if database storage fails
            
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