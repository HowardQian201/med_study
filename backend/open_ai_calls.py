from dotenv import load_dotenv
from openai import AsyncOpenAI # Changed to AsyncOpenAI
import os
import json
import time
import uuid
import random
import traceback
import hashlib
import tiktoken
import asyncio
from .database import upsert_quiz_questions_batch

load_dotenv()
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=600.0) # Changed to AsyncOpenAI

# Initialize tiktoken encoder
encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4 tokenizer

def count_tokens(text: str) -> int:
    """Count the number of tokens in a text string."""
    return len(encoding.encode(text))

def split_text_into_chunks(text: str, max_tokens: int = 1000) -> list:
    """
    Split text into chunks of approximately max_tokens each.
    
    Args:
        text (str): The text to split
        max_tokens (int): Maximum tokens per chunk
        
    Returns:
        list: List of text chunks
    """
    if not text:
        return []
    
    # Encode the text to get token positions
    tokens = encoding.encode(text)
    
    if len(tokens) <= max_tokens:
        return [text]
    
    chunks = []
    current_chunk = []
    current_token_count = 0
    
    # Split by sentences to avoid breaking mid-sentence
    sentences = text.split('. ')
    
    for sentence in sentences:
        # Add period back if it's not the last sentence
        if sentence != sentences[-1]:
            sentence += '. '
        
        sentence_tokens = encoding.encode(sentence)
        
        # If adding this sentence would exceed the limit, start a new chunk
        if current_token_count + len(sentence_tokens) > max_tokens and current_chunk:
            # Join current chunk and add to chunks
            chunks.append(''.join(current_chunk))
            current_chunk = [sentence]
            current_token_count = len(sentence_tokens)
        else:
            # Add sentence to current chunk
            current_chunk.append(sentence)
            current_token_count += len(sentence_tokens)
    
    # Add the last chunk if it has content
    if current_chunk:
        chunks.append(''.join(current_chunk))
    
    return chunks

async def gpt_summarize_transcript_chunked(text, temperature=0.15, stream=False, model="gpt-5-nano"):
    """
    Summarize text by breaking it into 1000-token chunks, summarizing each chunk,
    then creating a comprehensive summary from all chunk summaries.
    
    Args:
        text (str): The text to summarize
        temperature (float): Temperature for OpenAI API calls
        stream (bool): Whether to stream the response
        
    Returns:
        str: Comprehensive summary or streaming response
    """
    text_tokens = await asyncio.to_thread(count_tokens, text)
    print(f"gpt_summarize_transcript_chunked called with {text_tokens} tokens, stream: {stream}")
    
    if text_tokens > 500000:
        raise ValueError(f"Text is too long. Please select fewer PDFs or select smaller PDFs. {text_tokens} tokens is too long.")

    # Split text into chunks
    chunks = await asyncio.to_thread(split_text_into_chunks, text, 2000)
    print(f"Split text into {len(chunks)} chunks")
    
    # Summarize each chunk in parallel while maintaining order
    async def process_chunk(chunk, chunk_index):
        """Process a single chunk and return (index, summary) tuple to maintain order"""
        print(f"Processing chunk {chunk_index+1}/{len(chunks)} ({count_tokens(chunk)} tokens)")
        
        chunk_prompt = f"""Extract exactly 5 key medical concepts from the following text chunk. 
        Focus on high-yield information for medical students.
        Format as 5 bullet points with bold text for important terms.
        Include important lab values, diagnostic criteria, management steps, pathophysiology mechanisms, and clinical vignettes.
        
        <Text chunk>
        {chunk}
        </Text chunk>
        
        Return exactly 5 bullet points, each highlighting a key medical concept or high-yield fact.
        """
        
        try:
            # Add random delay to avoid rate limiting
            await asyncio.sleep(random.uniform(15, 90))
            chunk_completion = await openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an expert medical educator. Extract exactly 5 key medical concepts from text chunks as bullet points with bold formatting for important terms."},
                    {"role": "user", "content": chunk_prompt},
                ],
                # temperature=temperature,
                # max_completion_tokens=500,  # Reduced for concise 5 bullet points
            )
            
            chunk_summary = chunk_completion.choices[0].message.content.strip()
            print(f"Completed chunk {chunk_index+1} summary ({len(chunk_summary)} characters)")
            # print(f"Chunk summary: {chunk_summary}\n\n")
            return (chunk_index, chunk_summary)
            
        except Exception as e:
            print(f"Error processing chunk {chunk_index+1}: {e}")
            # Return None for failed chunks
            return (chunk_index, None)
    
    # Create tasks for all chunks
    chunk_tasks = [process_chunk(chunk, i) for i, chunk in enumerate(chunks)]
    
    # Execute all chunk summarizations in parallel
    chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)
    
    # Sort results by original index to maintain order
    chunk_results.sort(key=lambda x: x[0] if isinstance(x, tuple) else -1)
    
    # Extract summaries in correct order, filtering out failed chunks
    chunk_summaries = []
    for result in chunk_results:
        if isinstance(result, tuple) and result[1] is not None:
            chunk_summaries.append(result[1])
            print(f"Completed chunk {result[0]+1} summary ({len(result[1])} characters)")
        elif isinstance(result, Exception):
            print(f"Chunk processing failed with exception: {result}")
            # Continue with other chunks even if one fails
            continue
    
    if not chunk_summaries:
        raise Exception("No chunk summaries were successfully generated")
    
    # Combine all chunk summaries
    combined_summaries = "\n\n".join(chunk_summaries)
    print(f"Combined summaries: {len(combined_summaries)} characters and {count_tokens(combined_summaries)} tokens")
    
    # Create comprehensive summary from all chunk summaries
    final_prompt = f"""The following are detailed summaries of different sections of a medical text. 
    Create a comprehensive, well-organized medical study guide that synthesizes all this information.
    This comprehensive study guide should be more than 2,000 words.
    
    <CRITICAL REQUIREMENTS>  
    1. **Equal attention**: Ensure all sections receive equal coverage in the final summary
    2. **High-yield focus**: Highlight every exam-relevant lab values, diagnostic criteria, management steps, pathophysiology mechanisms—using **bold** for key terms and **italics** for definitions.  
    3. **Clinical correlates & examples**: For each major point, include at least one clinical vignette or real-world application illustrating how it presents or is managed in practice.  
    4. **Depth & length**: The final summary should have more than **2,000 words** in total. Ensure comprehensive coverage of all topics.
    </CRITICAL REQUIREMENTS>
    
    <FORMAT REQUIREMENTS>
    - Use Markdown formatting throughout
    - Use headers (# for main sections, ## for subsections)
    - Use bold (**text**) for key terms and important concepts
    - Use italics (*text*) for emphasis and definitions
    - Use bulleted lists (-) for key points and examples
    - Use numbered lists (1.) for step-by-step processes
    - Include tables where appropriate for comparisons
    - Use blockquotes (>) for important clinical pearls
    </FORMAT REQUIREMENTS>
    
    <Chunk Summaries>
    {combined_summaries}
    </Chunk Summaries>
    """
    
    # Wait 60 seconds before final API call to avoid 200,000 TPM rate limit
    print("Waiting 60 seconds before final comprehensive summary API call to avoid rate limits...")
    await asyncio.sleep(60)
    
    if stream:
        # Return streaming response for the final comprehensive summary
        return await openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert medical educator and USMLE/COMLEX tutor with extensive experience creating comprehensive study materials. Your goal is to create the most thorough, detailed, and well-organized study guides possible. You excel at identifying high-yield content, explaining complex concepts clearly, and structuring information in ways that maximize learning and retention. Always double-check your responses for accuracy and completeness. All of your study guides should be more than 2,000 words."},
                {"role": "user", "content": final_prompt},
            ],
            # temperature=temperature,
            # max_completion_tokens=10000,
            stream=True,
        )
    
    # Generate final comprehensive summary
    final_completion = await openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are an expert medical educator and USMLE/COMLEX tutor with extensive experience creating comprehensive study materials. Your goal is to create the most thorough, detailed, and well-organized study guides possible. You excel at identifying high-yield content, explaining complex concepts clearly, and structuring information in ways that maximize learning and retention. Always double-check your responses for accuracy and completeness. All of your study guides should more than 2,500 words."},
            {"role": "user", "content": final_prompt},
        ],
        # temperature=temperature,
        # max_completion_tokens=10000,
        stream=False,
    )
    
    final_summary = final_completion.choices[0].message.content.strip()
    print(f"Final comprehensive summary: {len(final_summary)} characters")
    
    return final_summary

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


async def generate_quiz_questions(summary_text, user_id, content_hash, incorrect_question_ids=None, previous_questions=None, num_questions=5, is_quiz_mode=True, model="gpt-5-nano"): # Changed to async def
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
        correct_question_answers = []
        if is_questions:
            incorrect_questions = [q['text'] for q in previous_questions if q['id'] in incorrect_question_ids]
            correct_questions = [q['text'] for q in previous_questions if q['id'] not in incorrect_question_ids]
            correct_question_answers = [q['options'][q['correctAnswer']] for q in previous_questions if q['id'] not in incorrect_question_ids]
        print(correct_question_answers)

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
            <Prompt description>
            Based on the following medical text summary, create {num_questions} VERY challenging USMLE clinical vignette style multiple-choice questions to test the student's understanding. Make sure to include all the key concepts and information from the summary.
            </Prompt description>

            <Requirements>
            1. Clear, specific and challenging clinical vignette stems (about 400 characters).
            2. Question stems must be in the style of a USMLE clinical vignette 
            3. Include a thorough explanation (about 500 characters) for why the correct answer is right and why others are wrong. Do not include the answer index in the reason.
            4. Aim for clarity, clinical relevance, and high-yield facts
            5. Each question must test a **specific factoid** (mechanism, lab value, dianosis, etc.)
            6. Must include balanced representation of Diagnosis, Treatment/Management, Pathophysiology/Mechanism, and High-Yield Factoid/Association vignettes
            </Requirements>

            <Example question fromat>
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
                    "correctAnswer": 1,
                    "reason": "The patient presents with signs of acute heart failure and pericardial effusion (dyspnea, JVD, low-voltage ECG, enlarged cardiac silhouette). These findings raise concern for cardiac tamponade, which can be rapidly fatal. The most appropriate next step is a transthoracic echocardiogram to evaluate for pericardial fluid and assess for signs of tamponade physiology such as diastolic collapse of the right heart chambers."
                }},
                ...
            ]
            </Example question fromat>

            <Summary>
            {summary_text}
            </Summary>
            '''

            system_prompt = """You are an expert medical professor that creates accurate, challenging USMLE clinical vignette style multiple choice questions. Output **only** valid JSON exactly matching the specified schema.
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
            <Prompt description>
            Based on the following medical text summary, create {num_questions} active‑recall flashcards that cover every key concept.
            </Prompt description>

            <Requirements>
            1. Clear, specific, and concise question stems for active recall flashcards (about 100 characters). Do not include the answer in the question stem or suggest there are multiple answers.
            2. Simple, direct active recall flashcard/multiple choice questions based on the summary.
            3. Include a thorough explanation (about 500 characters) for why the correct answer is right and why others are wrong. Do not include the answer index in the reason.
            4. Aim for clarity, clinical relevance, and high-yield facts
            5. Each flashcard must contain one clear fact.
            6. Each question must test a **unique factoid** (mechanism, lab value, dianosis, etc.)
            </Requirements>

            <Example flashcard format>
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
            </Example flashcard format>

            <Summary>
            {summary_text}
            </Summary>
            '''

            system_prompt = """You are an expert medical professor that creates accurate, active recall flashcard/multiple choice questions. Output **only** valid JSON exactly matching the specified schema.
            """
        
        print(f"Using model: {model} for quiz generation USMLE mode: {is_quiz_mode} with max completion tokens: {max_completion_tokens}")
        gpt_time_start = time.time()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        if correct_questions and len(correct_questions) > 0:
            new_message = f"""Generate {num_questions} new questions that:
            - **Cover entirely new medical subtopics** not addressed by the questions below.
            - **Avoid any repetition** or rewording of concepts already covered.
            - Each question must test a **unique fact** not yet assessed, even if phrased differently.
            - **Do not reuse** the same conditions, complications, lab findings, mechanisms, or drug classes from earlier questions.
            - Prioritize **coverage gaps**—review previous questions to identify what's missing, then fill in those gaps.

            You may reference the summary content below to ensure all concepts are grounded in the original source.

            <Previous question answers>
            {json.dumps(correct_question_answers)}
            </Previous question answers>

            <Previous question stems>
            {json.dumps(correct_questions)}
            </Previous question stems>

            <Summary>
            {summary_text}
            </Summary>

            Return the new questions in the JSON format specified earlier.
            """
            messages.append({"role": "user", "content": new_message})

        # for message in messages:
        #     print(f"message: {message}")

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
            # temperature=0.5,
            # presence_penalty=0.5,
            # max_completion_tokens=max_completion_tokens,
            # top_p=0.9,
            # frequency_penalty=0.5,
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

            # print(f"Question: {q['text']}")
            # print(f"Question options: {q['options']}")
            # print(f"Question correct answer: {q['correctAnswer']}")
            # print(f"Question reason: {q['reason']}")
            # print("--------------------------------")
        
        # Batch upsert all questions
        db_result = upsert_quiz_questions_batch(questions_with_ids)
        if db_result["success"]:
            print(f"Successfully stored {db_result['count']} quiz questions in database (batch)")
        else:
            print(f"Failed to store quiz questions: {db_result.get('error', 'Unknown error')}")

        return questions, question_hashes

    except (json.JSONDecodeError, ValueError) as e:
        print(f"Failed to get valid JSON. Error: {e}")
        print(f"Response text: {response_text}")
        raise Exception(f"Failed to get valid JSON response from AI: {e}")
    
    except Exception as e:
        print(f"An unexpected error occurred in generate_quiz_questions: {e}")
        traceback.print_exc()
        raise e

async def generate_short_title(text_to_summarize: str, model: str = "gpt-5-nano") -> str: # Changed to async def
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
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert at creating short, descriptive titles from text. You always follow length constraints and instructions precisely."},
                {"role": "user", "content": prompt},
            ],
            # temperature=1.0,
            # max_completion_tokens=20,  # Generous buffer for 10 words
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
        return "Untitled PDF" 