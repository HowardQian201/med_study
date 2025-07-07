from flask import Flask, request, jsonify, session, send_from_directory, Response
from flask_cors import CORS
import traceback
from .logic import extract_text_from_pdf_memory, set_process_priority, log_memory_usage, check_memory, get_container_memory_limit
from .open_ai_calls import gpt_summarize_transcript, generate_quiz_questions, generate_short_title
from .database import (
    upsert_pdf_results, check_question_set_exists,
    check_file_exists, generate_content_hash, generate_file_hash,
    authenticate_user, star_all_questions_by_hashes,
    upsert_question_set, upload_pdf_to_storage, get_question_sets_for_user, get_full_study_set_data, update_question_set_title,
    touch_question_set, update_question_starred_status, delete_question_set_and_questions, insert_feedback, 
    append_pdf_hash_to_user_pdfs, get_user_associated_pdf_metadata, get_pdf_text_by_hashes
)
from .background.tasks import print_number_task, process_pdf_task, celery_app
from flask_session import Session
import os
import re
from datetime import timedelta, datetime
import atexit
import glob
import gc
from io import BytesIO
import uuid
import random
from celery.result import AsyncResult # Import this to interact with task results
import tempfile # Import tempfile for creating temporary files

# Streaming flag
STREAMING_ENABLED = True

# Try absolute path resolution
static_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'client', 'dist')
app = Flask(__name__, static_folder=static_folder, static_url_path='/static')
CORS(app)

# Configure session
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback-dev-key')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
app.config['SESSION_FILE_THRESHOLD'] = 100  # Maximum number of sessions to store
app.config['SESSION_FILE_DIR'] = 'flask_session'
app.config['CLEANUP_INTERVAL'] = 300  # Cleanup every 5 minutes

# Email validation regex
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

Session(app)

# Cleanup on application exit
@atexit.register
def cleanup_on_exit():
    print("cleanup_on_exit()")
    try:
            
        # Clean up all session files
        session_dir = app.config['SESSION_FILE_DIR']
        if os.path.exists(session_dir):
            print(f"Cleaning up all session files in {session_dir}")
            for session_file in glob.glob(os.path.join(session_dir, '*')):
                try:
                    print(f"Removing session file: {session_file}")
                    os.remove(session_file)
                except Exception as e:
                    print(f"Error removing session file {session_file}: {str(e)}")
    except Exception as e:
        print(f"Error during cleanup: {str(e)}")


@app.route('/api/auth/login', methods=['POST'])
def login():
    print("login()")
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({'message': 'Email and password are required'}), 400

        # Validate email format
        if not re.match(EMAIL_REGEX, email):
            return jsonify({'message': 'Invalid email format'}), 400

        # Authenticate user against database
        auth_result = authenticate_user(email, password)
        
        if not auth_result["success"]:
            print(f"Database error during authentication: {auth_result.get('error', 'Unknown error')}")
            return jsonify({'message': 'Authentication service unavailable'}), 500
            
        if not auth_result["authenticated"]:
            print(f"Invalid credentials for email: {email}")
            return jsonify({'message': 'Invalid credentials'}), 401

        print(f"User authenticated: {auth_result['user']}")
        user = auth_result["user"]
        
        # Clear any existing session data
        session.clear()
        
        # Set new session data
        session['user_id'] = user['id']
        session['name'] = user['name']
        session['email'] = user['email']
        
        # Ensure PDF results are empty on fresh login
        session['summary'] = ""
        session['quiz_questions'] = []
        session['total_extracted_text'] = ""
        
        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'message': str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    print("logout()")
    try:
        
        # Explicitly clear PDF results and all session data
        session.clear()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    print("check_auth()")
    try:
        if 'user_id' in session:
            # Get user email from session
            email = session.get('email')
            # In a real app, you might want to fetch more user details from a database
            return jsonify({
                'authenticated': True,
                'user': {
                    'name': session.get('name'),
                    'email': email,
                    'id': session.get('user_id')
                },
                'summary': session.get('summary', '')
            })
        return jsonify({'authenticated': False})
    except Exception as e:
        return jsonify({'message': str(e)}), 500

# New endpoint to get user's associated PDFs
@app.route('/api/get-user-pdfs', methods=['GET'])
def get_user_pdfs():
    print("get_user_pdfs()")
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        user_id = session['user_id']
        result = get_user_associated_pdf_metadata(user_id)
        
        if not result['success']:
            return jsonify({'error': result.get('error', 'Failed to retrieve user PDFs')}), 500
            
        return jsonify({'success': True, 'pdfs': result['data']})
    except Exception as e:
        print(f"Error getting user PDFs: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-summary', methods=['POST'])
def generate_summary():
    print("generate_summary()")
    try:
        # Check if user is authenticated
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
                
        user_id = session.get('user_id')

        # Get additional user text if provided
        data = request.get_json()
        user_text = data.get('userText', '').strip()
        selected_pdf_hashes = data.get('selectedPdfHashes', [])
        is_quiz_mode = str(data.get('isQuizMode', 'false')).lower() == 'true'
        
        # Must have either selected PDFs or user text
        if not selected_pdf_hashes and not user_text:
            raise Exception("No files or text provided")
        
        log_memory_usage("before content processing")
        
        total_extracted_text = ""
        files_usertext_content = set()
        content_name_list = []

        # Process selected PDFs from database
        if selected_pdf_hashes:
            pdf_texts_result = get_pdf_text_by_hashes(selected_pdf_hashes)
            if not pdf_texts_result['success']:
                raise Exception(f"Failed to retrieve PDF texts: {pdf_texts_result.get('error')}")
            
            pdf_texts_map = pdf_texts_result['data']
            for pdf_hash in selected_pdf_hashes:
                # Retrieve the object containing both text and filename
                pdf_data = pdf_texts_map.get(pdf_hash)
                if pdf_data and pdf_data.get('text'):
                    text = pdf_data['text']
                    filename = pdf_data['filename'] # Get the filename

                    total_extracted_text += text
                    files_usertext_content.add(text) # Add text content for hash generation
                    if filename and filename not in content_name_list: # Add filename to list if not already present
                        content_name_list.append(filename)
                else:
                    print(f"Warning: Text for hash {pdf_hash[:8]}... not found in DB.")

        # Add user text if provided
        print(f"User text: {user_text[:100]}")
        if user_text:
            files_usertext_content.add(user_text)
            total_extracted_text += f"\n\nUser inputted text:\n{user_text}"
            content_name_list.append("User Text") # Indicate user text was included
        
        content_hash = generate_content_hash(files_usertext_content, user_id, is_quiz_mode)
        other_content_hash = generate_content_hash(files_usertext_content, user_id, not is_quiz_mode)

        session['content_hash'] = content_hash
        session['other_content_hash'] = other_content_hash
        session['content_name_list'] = content_name_list
        session.modified = True

        if not total_extracted_text:
            raise Exception("No text could be extracted from selected PDFs and no additional text provided")
        
        log_memory_usage("before summarization")
        
        
        print(f"Text length being sent to AI: {len(total_extracted_text)} characters")
        
        session['total_extracted_text'] = total_extracted_text
        
        if not STREAMING_ENABLED:
            summary = gpt_summarize_transcript(total_extracted_text, stream=STREAMING_ENABLED)
            session['summary'] = summary
            session.modified = True
            log_memory_usage("upload complete")
            return jsonify({'success': True, 'results': summary})
            
        # --- Streaming Response ---
        def stream_generator(text_to_summarize):
            stream_gen = gpt_summarize_transcript(text_to_summarize, stream=STREAMING_ENABLED)
            for chunk in stream_gen:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
            
            # The session cannot be modified here. The client will send the final summary
            # to a different endpoint to be saved.
            gc.collect()
            log_memory_usage("streaming complete")

        # Before streaming, save file-related info to the session. This is okay
        # because it happens within the initial request context.
        session.modified = True

        return Response(stream_generator(total_extracted_text), mimetype='text/plain')

    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        log_memory_usage("upload error")
        return jsonify({'error': str(e)}), 500
    finally:
        # Force garbage collection to clean up memory
        log_memory_usage("final cleanup")
        gc.collect()


@app.route('/api/generate-quiz', methods=['POST'])
def generate_quiz():
    """Endpoint to generate quiz questions from the stored summary"""
    print("generate_quiz()")
    try:
        # Check if user is authenticated
        if 'user_id' not in session:
            print(f"No user_id in session - returning 401")
            return jsonify({'error': 'Unauthorized'}), 401
            
        user_id = session['user_id']
        content_hash = session.get('content_hash')
        other_content_hash = session.get('other_content_hash')
        content_name_list = session.get('content_name_list', [])
        total_extracted_text = session.get('total_extracted_text', '')
        
        # Check if there's a summary to work with
        summary = session.get('summary', '')
        if not summary or not content_hash:
            print(f"No summary or content_hash available - returning 400")
            return jsonify({'error': 'No summary available. Please upload content first.'}), 400
        
        # Get request data and determine question type
        data = request.json or {}
        question_type = data.get('type', 'initial')  # 'initial', 'focused', or 'additional'
        incorrect_question_ids = data.get('incorrectQuestionIds', [])
        previous_questions = data.get('previousQuestions', [])
        is_previewing = data.get('isPreviewing', False)
        num_questions = data.get('numQuestions', 5)  # Default to 5 if not specified
        is_quiz_mode = str(data.get('isQuizMode', 'false')).lower() == 'true' # Default to False (study mode)
        other_quiz_exists = False

        # Validate number of questions is within reasonable bounds
        if not isinstance(num_questions, int) or num_questions < 1 or num_questions > 20:
            num_questions = 5  # Default to 5 if invalid
        
        # For initial generation, check if we already have questions to prevent duplicates
        if question_type == 'initial':
            other_quiz_exists = check_question_set_exists(other_content_hash, user_id)['exists']
            existing_questions = session.get('quiz_questions', [])
            if existing_questions:
                latest_questions = existing_questions[-1]
                print(f"Found existing questions ({len(latest_questions)} questions) - returning cached")
                return jsonify({
                    'success': True,
                    'questions': latest_questions
                })
        
        # Generate questions (can be initial or focused based on parameters)
        questions, question_hashes = generate_quiz_questions(
            summary, user_id, content_hash, 
            incorrect_question_ids=incorrect_question_ids, 
            previous_questions=previous_questions,
            num_questions=num_questions,
            is_quiz_mode=is_quiz_mode
        )
        
        # Only generate short title and upsert question set for initial generation
        if question_type == 'initial':
            short_summary = generate_short_title(total_extracted_text)
            # Upsert the question set to the database
            upsert_question_set(content_hash, user_id, question_hashes, content_name_list, total_extracted_text, short_summary, summary, is_quiz_mode)
            if not other_quiz_exists:
                other_questions, other_question_hashes = generate_quiz_questions(
                    summary, user_id, other_content_hash,
                    num_questions=num_questions,
                    is_quiz_mode=not is_quiz_mode
                )
                upsert_question_set(other_content_hash, user_id, other_question_hashes, content_name_list, total_extracted_text, short_summary, summary, not is_quiz_mode)
        else:
            # For focused/additional questions, just upsert the new questions
            upsert_question_set(content_hash, user_id, question_hashes, content_name_list, is_quiz=is_quiz_mode)
        
        # Store questions in session
        if is_previewing:
            # Store new questions in session, appending to the last set
            quiz_questions_sets = session.get('quiz_questions', [])
            if not quiz_questions_sets:
                # If there are no sets for some reason, create a new one.
                quiz_questions_sets.append(questions)
            else:
                # Get the last question set and extend it with the new questions.
                quiz_questions_sets[-1].extend(questions)

            session['quiz_questions'] = quiz_questions_sets
        else:
            # Store new questions in session
            quiz_questions = session.get('quiz_questions', [])
            quiz_questions.append(questions)
            session['quiz_questions'] = quiz_questions
        
        session.modified = True
        
        return jsonify({
            'success': True,
            'questions': questions
        })
    except Exception as e:
        print(f"Error generating quiz questions: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500



@app.route('/api/get-quiz', methods=['GET'])
def get_quiz():
    """Endpoint to retrieve stored quiz questions"""
    print("get_quiz()")
    try:
        # Check if user is authenticated
        if 'user_id' not in session:
            print(f"No user_id in session - returning 401")
            return jsonify({'error': 'Unauthorized'}), 401
            
        # Get stored questions
        questions = session.get('quiz_questions', [])
        latest_questions = questions[-1] if questions else []
        
        return jsonify({
            'success': True,
            'questions': latest_questions
        })
    except Exception as e:
        print(f"Error retrieving quiz questions: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-all-quiz-questions', methods=['GET'])
def get_all_quiz_questions():
    """Endpoint to retrieve all stored quiz questions from previous sessions"""
    print("get_all_quiz_questions()")
    try:
        # Check if user is authenticated
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
            
        # Get all stored questions
        all_questions = session.get('quiz_questions', [])
        
        return jsonify({
            'success': True,
            'questions': all_questions
        })
    except Exception as e:
        print(f"Error retrieving all quiz questions: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/save-quiz-answers', methods=['POST'])
def save_quiz_answers():
    """Endpoint to save user answers for the current quiz set"""
    print("save_quiz_answers()")
    try:
        # Check if user is authenticated
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
            
        # Get the request data
        data = request.json
        user_answers = data.get('userAnswers', {})
        submitted_answers = data.get('submittedAnswers', {})
        
        # Get current quiz questions
        quiz_questions = session.get('quiz_questions', [])
        if not quiz_questions:
            return jsonify({'error': 'No quiz questions found'}), 400
            
        # Update the latest question set with user answers
        latest_question_set = quiz_questions[-1]
        
        for question in latest_question_set:
            question_id = question['id']
            question_id_str = str(question_id)  # Convert to string for JSON key comparison
            
            if question_id_str in user_answers and question_id_str in submitted_answers:
                question['userAnswer'] = user_answers[question_id_str]
                question['isAnswered'] = True
            else:
                question['userAnswer'] = None
                question['isAnswered'] = False
        
        # Save back to session
        session['quiz_questions'] = quiz_questions
        session.modified = True
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error saving quiz answers: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/regenerate-summary', methods=['POST'])
def regenerate_summary():
    """Endpoint to regenerate the summary from stored text"""
    print("regenerate_summary()")
    try:
        # Check if user is authenticated
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        # Get stored data from session
        total_extracted_text = session.get('total_extracted_text', '')

        # Must have text to regenerate from
        if not total_extracted_text:
            return jsonify({'error': 'No text available to regenerate summary from. Please upload content first.'}), 400
        
        # Generate new summary
        if not STREAMING_ENABLED:
            summary = gpt_summarize_transcript(total_extracted_text, stream=STREAMING_ENABLED)
            session['summary'] = summary
            session['quiz_questions'] = []
            session.modified = True
            return jsonify({'success': True, 'summary': summary})

        # --- Streaming Response ---
        def stream_generator(text_to_summarize):
            stream_gen = gpt_summarize_transcript(text_to_summarize, stream=STREAMING_ENABLED)
            for chunk in stream_gen:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
            
            # Session cannot be modified here.
            print("Session not modified, streaming complete (regenerate).")

        # Clear old questions
        session['quiz_questions'] = []
        session.modified = True

        return Response(stream_generator(total_extracted_text), mimetype='text/plain')

    except Exception as e:
        print(f"Error regenerating summary: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/save-summary', methods=['POST'])
def save_summary():
    """Endpoint to save the completed summary to the session."""
    print("save_summary()")
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.json
        summary = data.get('summary')

        if summary is None:
            return jsonify({'error': 'No summary provided'}), 400

        session['summary'] = summary
        # Clear any old quiz questions, as they are now outdated
        session['quiz_questions'] = []
        session.modified = True
        
        print("Summary successfully saved to session.")
        return jsonify({'success': True})

    except Exception as e:
        print(f"Error saving summary: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-question-sets', methods=['GET'])
def get_question_sets():
    """Endpoint to retrieve all study sets for the logged-in user."""
    print("get_question_sets()")
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session['user_id']
    result = get_question_sets_for_user(user_id)
    
    if not result['success']:
        return jsonify({'error': result.get('error', 'Failed to get question sets')}), 500
        
    return jsonify({'success': True, 'sets': result['data']})

@app.route('/api/load-study-set', methods=['POST'])
def load_study_set():
    """Endpoint to load a full study set into the user's session."""
    print("load_study_set()")
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session['user_id']
    data = request.json
    content_hash = data.get('content_hash')
    
    if not content_hash:
        return jsonify({'error': 'content_hash is required'}), 400
        
    # Update the 'modified_at' timestamp (via created_at field)
    touch_result = touch_question_set(content_hash, user_id)
    if not touch_result['success']:
        # This is not a fatal error for loading, so we just log a warning.
        print(f"Warning: could not update timestamp for set {content_hash}. Reason: {touch_result.get('error')}")

    result = get_full_study_set_data(content_hash, user_id)
    print(f"get_full_study_set_data() result:")
    for i, q_set in enumerate(result['data']['quiz_questions']):
        for j, question in enumerate(q_set):
            print(f"{i}.{j}: {question['text']}")
    
    if not result['success']:
        print(f"Failed to get study set data: {result.get('error')}")
        return jsonify({'error': result.get('error', 'Failed to load study set')}), 500
    
    # Load data into session
    set_data = result['data']
    # Ensure summary is a string, not None, to prevent crashes.
    summary_text = set_data.get('summary', '')
    session['summary'] = summary_text
    session['short_summary'] = set_data.get('short_summary', '')
    session['quiz_questions'] = set_data.get('quiz_questions', [])
    session['total_extracted_text'] = set_data.get('total_extracted_text', '')
    session['content_hash'] = set_data.get('content_hash', '')
    session['content_name_list'] = set_data.get('content_name_list', [])
    session.modified = True
    
    print(f"Loaded {len(session.get('quiz_questions', []))} question sets into session.")
    print(f"Summary loaded (first 100 chars): {summary_text[:100]}")
    return jsonify({'success': True, 'summary': summary_text})

@app.route('/api/update-set-title', methods=['POST'])
def update_set_title():
    """Endpoint to update the title of a study set."""
    print("update_set_title()")
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session['user_id']
    data = request.json
    content_hash = data.get('content_hash')
    new_title = data.get('new_title')
    
    if not content_hash or not new_title:
        return jsonify({'error': 'content_hash and new_title are required'}), 400
        
    result = update_question_set_title(content_hash, user_id, new_title)
    
    if not result['success']:
        return jsonify({'error': result.get('error', 'Failed to update title')}), 500
        
    return jsonify({'success': True, 'data': result['data']})

@app.route('/api/clear-session-content', methods=['POST'])
def clear_session_content():
    """Endpoint to clear session data related to a study set."""
    print("clear_session_content()")
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        session.pop('summary', None)
        session.pop('quiz_questions', None)
        session.pop('content_hash', None)
        session.pop('other_content_hash', None)
        session.pop('content_name_list', None)
        session.pop('short_summary', None)
        session.pop('total_extracted_text', None)
        session.modified = True
        
        return jsonify({'success': True, 'message': 'Session content cleared.'})
    except Exception as e:
        print(f"Error clearing session content: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/toggle-star-question', methods=['POST'])
def toggle_star_question():
    print("toggle_star_question()")
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.json
        question_id = data.get('questionId')

        if not question_id:
            return jsonify({'error': 'Question ID is required'}), 400
            
        quiz_questions_sets = session.get('quiz_questions', [])
        updated_question = None

        # Iterate through all question sets and questions to find and update the question
        for q_set in quiz_questions_sets:
            for question in q_set:
                # Make sure question ID is a string for consistent comparison if UUIDs are used.
                if str(question.get('id')) == str(question_id):
                    # Toggle the starred status locally in the session
                    new_starred_status = not question.get('starred', False)
                    question['starred'] = new_starred_status
                    updated_question = question

                    # Call database function to persist the change
                    # Ensure question has a 'hash' to update in DB
                    question_hash = question.get('hash')
                    if question_hash:
                        db_update_result = update_question_starred_status(question_hash, new_starred_status)
                        if not db_update_result['success']:
                            print(f"Warning: Failed to update star status in DB for {question_hash}: {db_update_result.get('error')}")
                    else:
                        print(f"Warning: Question {question_id} has no hash. Star status not persisted to DB.")

                    break
            if updated_question:
                break
        
        if updated_question:
            session['quiz_questions'] = quiz_questions_sets
            session.modified = True
            print(f"Toggled star for question ID {question_id}. New status: {updated_question.get('starred')}")
            return jsonify({'success': True, 'question': updated_question})
        else:
            print(f"Question with ID {question_id} not found.")
            return jsonify({'error': 'Question not found'}), 404

    except Exception as e:
        print(f"Error toggling star status: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/shuffle-quiz', methods=['POST'])
def shuffle_quiz():
    print("shuffle_quiz()")
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        quiz_questions_sets = session.get('quiz_questions', [])
        
        if not quiz_questions_sets:
            return jsonify({'success': True, 'questions': []})
            
        # Get the latest set of questions
        latest_questions = quiz_questions_sets[-1]
        
        # Apply Fisher-Yates shuffle algorithm
        shuffled_questions = list(latest_questions)
        random.shuffle(shuffled_questions)
        
        # Update the latest set in session with shuffled questions
        quiz_questions_sets[-1] = shuffled_questions
        session['quiz_questions'] = quiz_questions_sets
        session.modified = True
        
        print(f"Shuffled {len(shuffled_questions)} questions in session.")
        return jsonify({'success': True, 'questions': shuffled_questions})
    except Exception as e:
        print(f"Error shuffling quiz questions: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/start-starred-quiz', methods=['POST'])
def start_starred_quiz():
    print("start_starred_quiz()")
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        quiz_questions_sets = session.get('quiz_questions', [])
        
        if not quiz_questions_sets:
            return jsonify({'success': True, 'questions': []})

        # Get the latest set of questions from the session
        latest_questions = quiz_questions_sets[-1]
        
        # Filter for only starred questions
        starred_questions = [q for q in latest_questions if q.get('starred', False)]

        if not starred_questions:
            return jsonify({'success': False, 'error': 'No starred questions found to start a quiz.'}), 400
            
        # Replace the current (latest) quiz set in the session with only the starred questions
        # This effectively creates a new quiz from existing starred questions
        quiz_questions_sets[-1] = starred_questions
        session['quiz_questions'] = quiz_questions_sets
        session.modified = True
        
        print(f"Started quiz with {len(starred_questions)} starred questions.")
        return jsonify({'success': True, 'questions': starred_questions})
    except Exception as e:
        print(f"Error starting starred quiz: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/star-all-questions', methods=['POST'])
def star_all_questions():
    print("star_all_questions()")
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.json or {}
        action = data.get('action', 'star')  # 'star' or 'unstar'
        
        if action not in ['star', 'unstar']:
            return jsonify({'error': 'Invalid action. Must be "star" or "unstar"'}), 400
        
        quiz_questions_sets = session.get('quiz_questions', [])
        
        if not quiz_questions_sets:
            return jsonify({'success': True, 'questions': []})

        # Get the latest set of questions from the session
        latest_questions = quiz_questions_sets[-1]
        
        # Update all questions based on action
        starred_status = action == 'star'
        updated_questions = []
        question_hashes = []
        
        for question in latest_questions:
            question['starred'] = starred_status
            updated_questions.append(question)
            
            # Collect question hashes for database update
            question_hash = question.get('hash')
            if question_hash:
                question_hashes.append(question_hash)
        
        # Update database for all questions
        if question_hashes:
            db_result = star_all_questions_by_hashes(question_hashes, starred_status)
            if not db_result['success']:
                print(f"Warning: Failed to update star status in DB: {db_result.get('error')}")
        
        # Update session
        quiz_questions_sets[-1] = updated_questions
        session['quiz_questions'] = quiz_questions_sets
        session.modified = True
        
        action_verb = "Starred" if starred_status else "Unstarred"
        print(f"{action_verb} all {len(updated_questions)} questions.")
        return jsonify({'success': True, 'questions': updated_questions})
    except Exception as e:
        print(f"Error {action}ring all questions: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete-question-set', methods=['POST'])
def delete_question_set():
    print("delete_question_set()")
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        user_id = session['user_id']
        data = request.json
        content_hash = data.get('content_hash')
        
        if not content_hash:
            return jsonify({'error': 'content_hash is required'}), 400
        
        # Delete the question set and associated questions from database
        delete_result = delete_question_set_and_questions(content_hash, user_id)
        
        if not delete_result['success']:
            return jsonify({'error': delete_result.get('error', 'Failed to delete question set')}), 500
        
        # Clear session data if the deleted set is currently loaded
        current_content_hash = session.get('content_hash')
        if current_content_hash == content_hash:
            session.pop('summary', None)
            session.pop('quiz_questions', None)
            session.pop('content_hash', None)
            session.pop('other_content_hash', None)
            session.pop('content_name_list', None)
            session.pop('short_summary', None)
            session.pop('total_extracted_text', None)
            session.modified = True
            print(f"Cleared session data for deleted set: {content_hash}")
        
        return jsonify({'success': True, 'message': 'Question set deleted successfully'})
        
    except Exception as e:
        print(f"Error deleting question set: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/submit-feedback', methods=['POST'])
def submit_feedback():
    print("submit_feedback()")
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.json
        feedback_text = data.get('feedback')
        user_id = session.get('user_id')
        user_name = session.get('name')
        user_email = session.get('email')

        if not feedback_text or not feedback_text.strip():
            return jsonify({'error': 'Feedback text cannot be empty'}), 400

        result = insert_feedback(user_id, user_email, user_name, feedback_text)
        
        if result['success']:
            return jsonify({'success': True, 'message': 'Feedback submitted successfully.'})
        else:
            return jsonify({'success': False, 'error': result.get('error', 'Failed to submit feedback.')}), 500

    except Exception as e:
        print(f"Error submitting feedback: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload-pdfs', methods=['POST'])
def upload_pdfs():
    print("upload_pdfs()")
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401

        if 'files' not in request.files:
            return jsonify({'error': 'No files part in the request'}), 400

        files = request.files.getlist('files')
        if not files:
            return jsonify({'error': 'No selected files'}), 400

        user_id = session['user_id']
        bucket_name = "pdfs"
        uploaded_task_details = []
        uploaded_files_details = []
        existing_files_details = []
        failed_files_details = []

        for file in files:
            if file.filename == '':
                continue

            print(f"Uploading file: {file.filename}")
            
            temp_file_path = None # Initialize to None
            try:
                # Create a temporary file to store the incoming PDF stream
                # delete=True ensures the file is automatically deleted when closed
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                    file.stream.seek(0) # Ensure stream is at the beginning
                    temp_file.write(file.stream.read())
                    temp_file_path = temp_file.name # Get the path to the temporary file
                
                original_filename = file.filename
                
                # Generate hash of the content from the temporary file
                file_hash = generate_file_hash(temp_file_path)
                print(f"File hash: {file_hash}")

                # Check if file content already exists in our 'pdfs' table
                file_exists_result = check_file_exists(file_hash)

                if not file_exists_result['exists']:
                    # If file content is new, upload to Supabase Storage from the temporary file
                    upload_result = upload_pdf_to_storage(temp_file_path, file_hash, original_filename, bucket_name)

                    if not upload_result['success']:
                        print(f"Error uploading {original_filename} to Supabase Storage: {upload_result.get('error')}")
                        failed_files_details.append({'filename': original_filename, 'error': upload_result.get('error', 'Unknown upload error')})
                        continue # Skip to next file if upload to storage failed
                    
                    # Upsert PDF metadata to 'pdfs' table (linking storage URL and path)
                    pdf_metadata = {
                        "hash": file_hash,
                        "filename": original_filename,
                        "bucket_name": bucket_name,
                        "storage_file_path": upload_result['path'],
                        "text": "" # Text will be extracted by background task
                    }
                    upsert_pdf_results_result = upsert_pdf_results(pdf_metadata)

                    if not upsert_pdf_results_result['success']:
                        print(f"Error upserting PDF results for {original_filename}: {upsert_pdf_results_result.get('error')}")
                        failed_files_details.append({'filename': original_filename, 'error': upsert_pdf_results_result.get('error', 'Unknown database error')})
                        continue # Skip to next file if DB upsert failed
                    
                    # Dispatch the Celery task to process the PDF text (using the hash to retrieve from Supabase)
                    task = process_pdf_task.delay(file_hash, original_filename, bucket_name, upload_result['path'], user_id)
                    uploaded_task_details.append({'filename': original_filename, 'task_id': task.id, 'file_hash': file_hash})
                    uploaded_files_details.append({'filename': original_filename, 'message': 'Uploaded and queued for processing.'})

                else:
                    print(f"File with hash {file_hash[:8]}... already exists in storage. Skipping re-upload.")
                    # Even if file exists, ensure it's linked to this user
                    append_result = append_pdf_hash_to_user_pdfs(user_id, file_hash)
                    if not append_result['success']:
                        print(f"Error linking existing PDF {file_hash[:8]}... to user {user_id}: {append_result.get('error')}")
                        failed_files_details.append({'filename': original_filename, 'error': append_result.get('error', 'Failed to link file to user')})
                        continue
                    existing_files_details.append({'filename': original_filename, 'message': 'File already exists in storage.'})

            except Exception as e:
                print(f"An unexpected error occurred for file {file.filename}: {str(e)}")
                failed_files_details.append({'filename': original_filename, 'error': str(e)})
            finally:
                if temp_file_path and os.path.exists(temp_file_path):
                    os.remove(temp_file_path) # Ensure temporary file is deleted
        
        if not uploaded_task_details and not existing_files_details and not failed_files_details:
            return jsonify({'success': False, 'message': 'No valid PDF files were provided or processed.'}), 200

        return jsonify({
            'success': True,
            'message': f'{len(uploaded_files_details)} files uploaded, {len(existing_files_details)} existing files, {len(failed_files_details)} files failed.',
            'uploaded_files': uploaded_files_details,
            'existing_files': existing_files_details,
            'failed_files': failed_files_details,
            'task_details': uploaded_task_details # Still include for debugging if needed
        })

    except Exception as e:
        print(f"Error uploading PDFs: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route("/api/pdf-processing-status/<task_id>")
def get_pdf_processing_status(task_id):
    print(f"Checking status for task_id: {task_id}")
    try:
        # Check if user is authenticated (optional, but good practice if task results are user-specific)
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        task_result = AsyncResult(task_id, app=celery_app)
        
        status = task_result.status
        result = task_result.result # This will be the return value of the task if successful

        # Handle specific states
        if status == 'PENDING':
            # Task is not yet ready or does not exist
            message = "Task is pending or not found."
        elif status == 'STARTED':
            message = "Task has started processing."
        elif status == 'SUCCESS':
            message = "Task completed successfully."
        elif status == 'FAILURE':
            message = f"Task failed: {result}"
        else:
            message = f"Task status: {status}"

        return jsonify({
            'success': True,
            'task_id': task_id,
            'status': status,
            'result': result,
            'message': message
        })

    except Exception as e:
        print(f"Error checking task status: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# Serve the React frontend
@app.route("/")
def serve():
    """Serve the main React app"""
    print(f"Serving main React app from: {app.static_folder}")
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/favicon.png')
def favicon():
    # Serve the favicon from the React build output
    return send_from_directory(app.static_folder, 'favicon.png', mimetype='image/png')

# Catch-all route for client-side routing (React Router)
@app.route("/<path:path>")
def serve_static(path):
    print(f"Serving static file: {path}")
    # If it's an asset file (CSS, JS), serve it
    if path.startswith('assets/'):
        return send_from_directory(app.static_folder, path)
    # For all other routes, serve index.html (let React Router handle it)
    else:
        return send_from_directory(app.static_folder, 'index.html')
    
    