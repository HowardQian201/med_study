from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import traceback
from .logic import log_memory_usage
from .open_ai_calls import gpt_summarize_transcript, generate_quiz_questions, generate_short_title
from .database import (
    upsert_pdf_results, check_question_set_exists,
    check_file_exists, generate_content_hash, generate_file_hash,
    authenticate_user, star_all_questions_by_hashes,
    upsert_question_set, upload_pdf_to_storage, get_question_sets_for_user, get_full_study_set_data, update_question_set_title,
    touch_question_set, update_question_starred_status, delete_question_set_and_questions, insert_feedback, 
    append_pdf_hash_to_user_pdfs, get_user_associated_pdf_metadata, get_pdf_text_by_hashes,
    update_user_task_status, get_user_tasks, delete_user_tasks_by_status, remove_pdf_hashes_from_user,
    create_session, get_session_data, update_session_data, delete_session, extend_session_ttl, clear_redis_session_content
)
# Import the main Celery app instance from worker.py
from .background.worker import app as celery_app
from .background.tasks import print_number_task, process_pdf_task
import os
import re
from datetime import timedelta, datetime
import gc
import random
from celery.result import AsyncResult # Import this to interact with task results
import tempfile # Import tempfile for creating temporary files
from datetime import datetime, timezone # Import timezone for UTC
import secrets

# Custom Redis Session Management
class RedisSessionManager:
    """Custom session manager using Redis for session storage."""
    
    def __init__(self, app=None):
        self.app = app
        self.session_data = {}
        self.session_id = None
        self.modified = False
        
    def init_app(self, app):
        self.app = app
        app.before_request(self._load_session)
        app.after_request(self._save_session)
        
    def _load_session(self):
        """Load session data from Redis before each request."""
        self.session_id = request.cookies.get('session_id')
        self.modified = False # Reset modification flag on each request
        
        if self.session_id:
            result = get_session_data(self.session_id)
            if result["success"]:
                self.session_data = result["data"]
                # Extend session TTL on access
                extend_session_ttl(self.session_id, 1)  # 1 hour
            else:
                # Session expired or doesn't exist
                self.session_data = {}
                self.session_id = None
        else:
            self.session_data = {}
            
    def _save_session(self, response):
        """Save session data to Redis after each request if modified."""
        
        # Only save to Redis if the session has been modified
        if not self.modified and self.session_id:
            return response
        
        if self.session_id and self.session_data:
            # Update session data in Redis
            update_session_data(self.session_id, self.session_data, 1)  # 1 hour TTL
            
            # Set session cookie
            response.set_cookie(
                'session_id',
                self.session_id,
                max_age=3600,  # 1 hour
                secure=True,
                httponly=True,
                samesite='Lax'
            )
        elif not self.session_id and self.session_data:
            # Create new session
            self.session_id = secrets.token_urlsafe(32)
            create_result = create_session(self.session_id, self.session_data, 1)
            if create_result["success"]:
                response.set_cookie(
                    'session_id',
                    self.session_id,
                    max_age=3600,
                    secure=True,
                    httponly=True,
                    samesite='Lax'
                )
        
        return response
        
    def get(self, key, default=None):
        """Get session value."""
        return self.session_data.get(key, default)
        
    def __getitem__(self, key):
        """Get session value with bracket notation."""
        return self.session_data[key]
        
    def __setitem__(self, key, value):
        """Set session value with bracket notation."""
        self.session_data[key] = value
        self.modified = True
        
    def __contains__(self, key):
        """Check if key exists in session."""
        return key in self.session_data
        
    def pop(self, key, default=None):
        """Remove and return session value."""
        self.modified = True
        return self.session_data.pop(key, default)
        
    def clear(self):
        """Clear all session data."""
        if self.session_id:
            delete_session(self.session_id)
            self.session_id = None
        self.session_data = {}
        self.modified = True
        
    def update(self, data):
        """Update session data with dict."""
        self.session_data.update(data)
        self.modified = True
        
    def clear_content(self):
        """Clear session content while preserving user auth."""
        if self.session_id:
            result = clear_redis_session_content(self.session_id)
            if result.get("success"):
                # Reload local session data to reflect the change
                self.session_data = result.get("data", {})
                # self.modified = True # REMOVED: Redis DB update is handled by clear_redis_session_content already
                return True
        return False

# Custom session object
redis_session = RedisSessionManager()

# Streaming flag
STREAMING_ENABLED = True

# Try absolute path resolution
static_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'client', 'dist')
app = Flask(__name__, static_folder=static_folder, static_url_path='/static')
CORS(app)

# Configure session - keep minimal Flask session config for fallback
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback-dev-key')

# Initialize Redis session manager
redis_session.init_app(app)

# Email validation regex
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

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
        redis_session.clear()
        print(f"User ID: {user['id']}")
        
        # Set new session data
        redis_session['user_id'] = user['id']
        redis_session['name'] = user['name']
        redis_session['email'] = user['email']
        
        # Ensure PDF results are empty on fresh login
        redis_session['summary'] = ""
        redis_session['quiz_questions'] = []
        
        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'message': str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    print("logout()")
    try:
        
        # Explicitly clear PDF results and all session data
        redis_session.clear()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    print("check_auth()")
    try:
        if 'user_id' in redis_session:
            # Get user email from session
            email = redis_session.get('email')
            # In a real app, you might want to fetch more user details from a database
            return jsonify({
                'authenticated': True,
                'user': {
                    'name': redis_session.get('name'),
                    'email': email,
                    'id': redis_session.get('user_id')
                },
                'summary': redis_session.get('summary', '')
            })
        return jsonify({'authenticated': False})
    except Exception as e:
        return jsonify({'message': str(e)}), 500

# New endpoint to get user's associated PDFs
@app.route('/api/get-user-pdfs', methods=['GET'])
def get_user_pdfs():
    print("get_user_pdfs()")
    try:
        user_id = redis_session.get('user_id')
        
        # Validate user_id to ensure it's an integer before passing to DB
        if not isinstance(user_id, int):
            print(f"Invalid user_id type or missing in session for get_user_pdfs: {user_id}")
            return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}), 401

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
        user_id = redis_session.get('user_id')

        # Validate user_id to ensure it's an integer before passing to DB
        if not isinstance(user_id, int):
            print(f"Invalid user_id type or missing in session for generate_summary: {user_id}")
            return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}) , 401

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
                    print(f"Generate Summary with Filename: {filename}")

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

        redis_session['content_hash'] = content_hash
        redis_session['content_name_list'] = content_name_list
        # redis_session auto-saves

        if not total_extracted_text:
            raise Exception("No text could be extracted from selected PDFs and no additional text provided")
        
        log_memory_usage("before summarization")
        
        
        print(f"Text length being sent to AI: {len(total_extracted_text)} characters")
                
        if not STREAMING_ENABLED:
            summary = gpt_summarize_transcript(total_extracted_text, stream=STREAMING_ENABLED)
            redis_session['summary'] = summary
            # redis_session auto-saves
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
        # redis_session auto-saves

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
        user_id = redis_session.get('user_id')
        
        # Validate user_id to ensure it's an integer before passing to DB
        if not isinstance(user_id, int):
            print(f"Invalid user_id type or missing in session for generate_quiz: {user_id}")
            return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}), 401

        content_hash = redis_session.get('content_hash')
        content_name_list = redis_session.get('content_name_list', [])
        
        # Check if there's a summary to work with
        summary = redis_session.get('summary', '')
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

        # Validate number of questions is within reasonable bounds
        if not isinstance(num_questions, int) or num_questions < 1 or num_questions > 20:
            num_questions = 5  # Default to 5 if invalid
        
        # For initial generation, check if we already have questions to prevent duplicates
        if question_type == 'initial':
            quiz_exists = check_question_set_exists(content_hash, user_id)['exists']
            if quiz_exists:
                print(f"Quiz set {content_hash} already exists for user {user_id}")
                return jsonify({'error': 'Quiz set already exists', 'content_hash': content_hash}), 201
        
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
            short_summary = generate_short_title(summary)
            # Upsert the question set to the database
            upsert_question_set(content_hash, user_id, question_hashes, content_name_list, short_summary, summary, is_quiz_mode)
            redis_session['short_summary'] = short_summary
            # redis_session auto-saves
        else:
            # For focused/additional questions, just upsert the new questions
            upsert_question_set(content_hash, user_id, question_hashes, content_name_list, is_quiz=is_quiz_mode)
        
        # Store questions in session
        if is_previewing:
            # Store new questions in session, appending to the last set
            quiz_questions_sets = redis_session.get('quiz_questions', [])
            if not quiz_questions_sets:
                # If there are no sets for some reason, create a new one.
                quiz_questions_sets.append(questions)
            else:
                # Get the last question set and extend it with the new questions.
                quiz_questions_sets[-1].extend(questions)

            redis_session['quiz_questions'] = quiz_questions_sets
        else:
            # Store new questions in session
            quiz_questions = redis_session.get('quiz_questions', [])
            quiz_questions.append(questions)
            redis_session['quiz_questions'] = quiz_questions
        
        # redis_session auto-saves
        
        return jsonify({
            'success': True,
            'questions': questions,
            'short_summary': redis_session.get('short_summary', '')
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
        user_id = redis_session.get('user_id')

        # Validate user_id to ensure it's an integer before proceeding
        if not isinstance(user_id, int):
            print(f"Invalid user_id type or missing in session for get_quiz: {user_id}")
            return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}), 401
            
        # Get stored questions
        questions = redis_session.get('quiz_questions', [])
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
        user_id = redis_session.get('user_id')

        # Validate user_id to ensure it's an integer before proceeding
        if not isinstance(user_id, int):
            print(f"Invalid user_id type or missing in session for get_all_quiz_questions: {user_id}")
            return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}), 401
            
        # Get all stored questions
        all_questions = redis_session.get('quiz_questions', [])
        
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
        user_id = redis_session.get('user_id')

        # Validate user_id to ensure it's an integer before proceeding
        if not isinstance(user_id, int):
            print(f"Invalid user_id type or missing in session for save_quiz_answers: {user_id}")
            return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}), 401
            
        # Get the request data
        data = request.json
        user_answers = data.get('userAnswers', {})
        submitted_answers = data.get('submittedAnswers', {})
        
        # Get current quiz questions
        quiz_questions = redis_session.get('quiz_questions', [])
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
        redis_session['quiz_questions'] = quiz_questions
        # redis_session auto-saves
        
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
        user_id = redis_session.get('user_id')

        # Validate user_id to ensure it's an integer before proceeding
        if not isinstance(user_id, int):
            print(f"Invalid user_id type or missing in session for regenerate_summary: {user_id}")
            return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}), 401
        
        # Get additional user text if provided
        data = request.get_json()
        user_text = data.get('userText', '').strip()
        selected_pdf_hashes = data.get('selectedPdfHashes', [])
        
        # Must have either selected PDFs or user text
        if not selected_pdf_hashes and not user_text:
            raise Exception("No files or text provided")
        
        total_extracted_text = ""
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

                    total_extracted_text += text
                else:
                    print(f"Warning: Text for hash {pdf_hash[:8]}... not found in DB.")

        # Add user text if provided
        print(f"User text: {user_text[:100]}")
        if user_text:
            total_extracted_text += f"\n\nUser inputted text:\n{user_text}"

        # Must have text to regenerate from
        if not total_extracted_text:
            return jsonify({'error': 'No text available to regenerate summary from. Please upload content first.'}), 400
        
        # Generate new summary
        if not STREAMING_ENABLED:
            summary = gpt_summarize_transcript(total_extracted_text, temperature=1.2, stream=STREAMING_ENABLED)
            redis_session['summary'] = summary
            redis_session['quiz_questions'] = []
            # redis_session auto-saves
            return jsonify({'success': True, 'summary': summary})

        # --- Streaming Response ---
        def stream_generator(text_to_summarize):
            stream_gen = gpt_summarize_transcript(text_to_summarize, temperature=1.2, stream=STREAMING_ENABLED)
            for chunk in stream_gen:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
            
            # Redis session cannot be modified here.
            print("Redis session not modified, streaming complete (regenerate).")

        # Clear old questions
        redis_session['quiz_questions'] = []
        # redis_session auto-saves

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
        user_id = redis_session.get('user_id')

        # Validate user_id to ensure it's an integer before proceeding
        if not isinstance(user_id, int):
            print(f"Invalid user_id type or missing in session for save_summary: {user_id}")
            return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}), 401
        
        data = request.json
        summary = data.get('summary')

        if summary is None:
            return jsonify({'error': 'No summary provided'}), 400

        redis_session['summary'] = summary
        # Clear any old quiz questions, as they are now outdated
        redis_session['quiz_questions'] = []
        # redis_session auto-saves
        
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
    if 'user_id' not in redis_session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = redis_session.get('user_id')
    
    # Validate user_id to ensure it's an integer before passing to DB
    if not isinstance(user_id, int):
        print(f"Invalid user_id type or missing in session for get_question_sets: {user_id}")
        return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}), 401

    result = get_question_sets_for_user(user_id)
    
    if not result['success']:
        return jsonify({'error': result.get('error', 'Failed to get question sets')}), 500
        
    return jsonify({'success': True, 'sets': result['data']})

@app.route('/api/load-study-set', methods=['POST'])
def load_study_set():
    """Endpoint to load a full study set into the user's session."""
    print("load_study_set()")
    user_id = redis_session.get('user_id')
    
    # Validate user_id to ensure it's an integer before passing to DB
    if not isinstance(user_id, int):
        print(f"Invalid user_id type or missing in session for load_study_set: {user_id}")
        return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}), 401

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
            print(f"{i}.{j}: {question['text'][:50]}")
    
    if not result['success']:
        print(f"Failed to get study set data: {result.get('error')}")
        return jsonify({'error': result.get('error', 'Failed to load study set')}), 500
    
    # Load data into session
    set_data = result['data']
    # Ensure summary is a string, not None, to prevent crashes.
    summary_text = set_data.get('summary', '')
    redis_session['summary'] = summary_text
    redis_session['short_summary'] = set_data.get('short_summary', '')
    redis_session['quiz_questions'] = set_data.get('quiz_questions', [])
    redis_session['content_hash'] = set_data.get('content_hash', '')
    redis_session['content_name_list'] = set_data.get('content_name_list', [])
    # redis_session auto-saves
    
    print(f"Loaded {len(redis_session.get('quiz_questions', []))} question sets into session.")
    print(f"Summary loaded (first 100 chars): {summary_text[:100]}")
    return jsonify({'success': True, 'summary': summary_text})

@app.route('/api/get-current-session-sources', methods=['GET'])
def get_current_session_sources():
    print("get_current_session_sources()")
    user_id = redis_session.get('user_id')
    
    # Validate user_id to ensure it's an integer before proceeding
    if not isinstance(user_id, int):
        print(f"Invalid user_id type or missing in session for get_current_session_sources: {user_id}")
        return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}), 401

    # Retrieve the content_name_list from the session
    content_names = redis_session.get('content_name_list', [])
    return jsonify({'success': True, 'content_names': content_names, 'short_summary': redis_session.get('short_summary', '')})

@app.route('/api/update-set-title', methods=['POST'])
def update_set_title():
    """Endpoint to update the title of a study set."""
    print("update_set_title()")
    user_id = redis_session.get('user_id')

    # Validate user_id to ensure it's an integer before passing to DB
    if not isinstance(user_id, int):
        print(f"Invalid user_id type or missing in session for update_set_title: {user_id}")
        return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}), 401

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
        user_id = redis_session.get('user_id')

        # Validate user_id to ensure it's an integer before proceeding
        if not isinstance(user_id, int):
            print(f"Invalid user_id type or missing in session for clear_session_content: {user_id}")
            return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}), 401
        
        redis_session.clear_content()
        
        return jsonify({'success': True, 'message': 'Session content cleared.'})
    except Exception as e:
        print(f"Error clearing session content: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/toggle-star-question', methods=['POST'])
def toggle_star_question():
    print("toggle_star_question()")
    try:
        user_id = redis_session.get('user_id')

        # Validate user_id to ensure it's an integer before proceeding
        if not isinstance(user_id, int):
            print(f"Invalid user_id type or missing in session for toggle_star_question: {user_id}")
            return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}), 401

        data = request.json
        question_id = data.get('questionId')

        if not question_id:
            return jsonify({'error': 'Question ID is required'}), 400
            
        quiz_questions_sets = redis_session.get('quiz_questions', [])
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
            redis_session['quiz_questions'] = quiz_questions_sets
            # redis_session auto-saves
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
        user_id = redis_session.get('user_id')

        # Validate user_id to ensure it's an integer before proceeding
        if not isinstance(user_id, int):
            print(f"Invalid user_id type or missing in session for shuffle_quiz: {user_id}")
            return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}), 401
        
        quiz_questions_sets = redis_session.get('quiz_questions', [])
        
        if not quiz_questions_sets:
            return jsonify({'success': True, 'questions': []})
            
        # Get the latest set of questions
        latest_questions = quiz_questions_sets[-1]
        
        # Apply Fisher-Yates shuffle algorithm
        shuffled_questions = list(latest_questions)
        random.shuffle(shuffled_questions)
        
        # Update the latest set in session with shuffled questions
        quiz_questions_sets[-1] = shuffled_questions
        redis_session['quiz_questions'] = quiz_questions_sets
        # redis_session auto-saves
        
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
        user_id = redis_session.get('user_id')

        # Validate user_id to ensure it's an integer before proceeding
        if not isinstance(user_id, int):
            print(f"Invalid user_id type or missing in session for start_starred_quiz: {user_id}")
            return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}), 401
        
        quiz_questions_sets = redis_session.get('quiz_questions', [])
        
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
        redis_session['quiz_questions'] = quiz_questions_sets
        # redis_session auto-saves
        
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
        user_id = redis_session.get('user_id')

        # Validate user_id to ensure it's an integer before proceeding
        if not isinstance(user_id, int):
            print(f"Invalid user_id type or missing in session for star_all_questions: {user_id}")
            return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}), 401
        
        data = request.json or {}
        action = data.get('action', 'star')  # 'star' or 'unstar'
        
        if action not in ['star', 'unstar']:
            return jsonify({'error': 'Invalid action. Must be "star" or "unstar"'}), 400
        
        quiz_questions_sets = redis_session.get('quiz_questions', [])
        
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
        redis_session['quiz_questions'] = quiz_questions_sets
        # redis_session auto-saves
        
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
        user_id = redis_session.get('user_id')

        # Validate user_id to ensure it's an integer before passing to DB
        if not isinstance(user_id, int):
            print(f"Invalid user_id type or missing in session for delete_question_set: {user_id}")
            return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}), 401

        data = request.json
        content_hash = data.get('content_hash')
        
        if not content_hash:
            return jsonify({'error': 'content_hash is required'}), 400
        
        # Delete the question set and associated questions from database
        delete_result = delete_question_set_and_questions(content_hash, user_id)
        
        if not delete_result['success']:
            return jsonify({'error': delete_result.get('error', 'Failed to delete question set')}), 500
        
        # Clear session data if the deleted set is currently loaded
        current_content_hash = redis_session.get('content_hash')
        if current_content_hash == content_hash:
            redis_session.clear_content()
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
        data = request.json
        feedback_text = data.get('feedback')
        user_id = redis_session.get('user_id')
        user_name = redis_session.get('name')
        user_email = redis_session.get('email')

        # Validate user_id to ensure it's an integer before proceeding
        if not isinstance(user_id, int):
            print(f"Invalid user_id type or missing in session for submit_feedback: {user_id}")
            return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}), 401

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

@app.route('/api/clear-completed-tasks', methods=['POST'])
def clear_completed_tasks_endpoint():
    print("clear_completed_tasks_endpoint()")
    user_id = redis_session.get('user_id')

    # Validate user_id to ensure it's an integer before proceeding
    if not isinstance(user_id, int):
        print(f"Invalid user_id type or missing in session for clear_completed_tasks_endpoint: {user_id}")
        return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}), 401

    # Define statuses to clear: SUCCESS and FAILURE
    statuses_to_clear = ['SUCCESS', 'FAILURE']
    
    result = delete_user_tasks_by_status(user_id, statuses_to_clear)
    
    if not result['success']:
        return jsonify({'error': result.get('error', 'Failed to clear tasks')}), 500
        
    return jsonify({'success': True, 'message': f"Cleared {result.get('deleted_count', 0)} completed tasks."})

@app.route('/api/remove-user-pdfs', methods=['POST'])
def remove_user_pdfs_endpoint():
    print("remove_user_pdfs_endpoint()")
    user_id = redis_session.get('user_id')

    # Validate user_id to ensure it's an integer before proceeding
    if not isinstance(user_id, int):
        print(f"Invalid user_id type or missing in session for remove_user_pdfs_endpoint: {user_id}")
        return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}), 401

    data = request.get_json()
    pdf_hashes = data.get('pdf_hashes', [])

    if not pdf_hashes:
        return jsonify({'success': False, 'message': 'No PDF hashes provided for removal.'}), 400

    result = remove_pdf_hashes_from_user(user_id, pdf_hashes)
    
    if not result['success']:
        return jsonify({'error': result.get('error', 'Failed to remove PDFs')}), 500
        
    return jsonify({'success': True, 'message': f"Removed {result.get('deleted_count', 0)} PDFs from your account."})

@app.route('/api/get-user-tasks', methods=['GET'])
def get_user_tasks_endpoint():
    print("get_user_tasks()")
    user_id = redis_session.get('user_id')

    # Validate user_id to ensure it's an integer before proceeding
    if not isinstance(user_id, int):
        print(f"Invalid user_id type or missing in session for get_user_tasks_endpoint: {user_id}")
        return jsonify({'error': 'Unauthorized: Invalid or missing user ID in session'}), 401

    result = get_user_tasks(user_id)
    
    if not result['success']:
        print(f"Error retrieving tasks from Redis for user {user_id}: {result.get('error', 'Unknown error')}")
        return jsonify({'error': result.get('error', 'Failed to get tasks')}), 500
    
    print(f"Tasks retrieved from Redis for user {user_id}:")
    for task in result['data']:
        print(f"  Task ID: {task.get('task_id', '')}, Filename: {task.get('filename', '')}, Status: {task.get('status', '')}, Message: {task.get('message', '')}")
            
    return jsonify({'success': True, 'tasks': result['data']})

@app.route('/api/upload-pdfs', methods=['POST'])
def upload_pdfs():
    print("upload_pdfs()")
    try:
        if 'user_id' not in redis_session:
            return jsonify({'error': 'Unauthorized'}), 401

        if 'files' not in request.files:
            return jsonify({'error': 'No files part in the request'}), 400

        files = request.files.getlist('files')
        if not files:
            return jsonify({'error': 'No selected files'}), 400

        user_id = redis_session['user_id']
        
        # Validate user_id to ensure it's an integer before passing to DB
        if not isinstance(user_id, int):
            print(f"Invalid user_id type in session for upload_pdfs: {user_id}")
            return jsonify({'error': 'Unauthorized: Invalid user ID in session'}), 401

        bucket_name = "pdfs"
        uploaded_task_details = []
        uploaded_files_details = []
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
                        "text": "", # Text will be extracted by background task
                        "created_at": datetime.now().isoformat()
                    }
                    upsert_pdf_results_result = upsert_pdf_results(pdf_metadata)

                    if not upsert_pdf_results_result['success']:
                        print(f"Error upserting PDF results for {original_filename}: {upsert_pdf_results_result.get('error')}")
                        failed_files_details.append({'filename': original_filename, 'error': upsert_pdf_results_result.get('error', 'Unknown database error')})
                        continue # Skip to next file if DB upsert failed
                    
                    # Dispatch the Celery task to process the PDF text (using the hash to retrieve from Supabase)
                    task = process_pdf_task.delay(file_hash, bucket_name, upload_result['path'], user_id, original_filename)
                    uploaded_task_details.append({'filename': original_filename, 'task_id': task.id, 'file_hash': file_hash})
                    uploaded_files_details.append({'filename': original_filename, 'message': 'Uploaded and queued for processing.'})
                    
                    # Store initial task status in Redis
                    update_user_task_status(
                        user_id=user_id,
                        task_id=task.id,
                        filename=original_filename,
                        status='PENDING',
                        message=f'Task is queued for processing'
                    )

                else:
                    print(f"File with hash {file_hash[:8]}... already exists in storage. Skipping re-upload.")
                    # Even if file exists, ensure it's linked to this user
                    append_result = append_pdf_hash_to_user_pdfs(user_id, file_hash)
                    if not append_result['success']:
                        print(f"Error linking existing PDF {file_hash[:8]}... to user {user_id}: {append_result.get('error')}")
                        failed_files_details.append({'filename': original_filename, 'error': append_result.get('error', 'Failed to link file to user')})
                        continue
                    # For display purposes, treat existing files as successfully "uploaded"
                    uploaded_files_details.append({'filename': original_filename, 'message': 'Uploaded and queued for processing.'})

            except Exception as e:
                print(f"An unexpected error occurred for file {file.filename}: {str(e)}")
                failed_files_details.append({'filename': original_filename, 'error': str(e)})
            finally:
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        # Explicitly close the file handle before attempting to remove it
                        if 'temp_file' in locals() and not temp_file.closed:
                            temp_file.close()
                        os.remove(temp_file_path) # Ensure temporary file is deleted
                    except Exception as e_clean:
                        print(f"Error cleaning up temporary file {temp_file_path}: {str(e_clean)}")
        
        if not uploaded_task_details and not failed_files_details and not uploaded_files_details:
            return jsonify({'success': False, 'message': 'No valid PDF files were provided or processed.'}), 200

        return jsonify({
            'success': True,
            'message': f'{len(uploaded_files_details)} files uploaded, {len(failed_files_details)} files failed.',
            'uploaded_files': uploaded_files_details,
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
        if 'user_id' not in redis_session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        task_result = AsyncResult(task_id, app=celery_app)
        
        status = task_result.status
        result = task_result.result # This will be the return value of the task if successful

        # Handle specific states
        if status == 'PENDING':
            # Task is not yet ready or does not exist
            timestamp = datetime.now(timezone.utc).strftime("%m-%d %H:%M")
            message = f"Task is queued for processing (UTC {timestamp})"
        elif status == 'IN PROGRESS' or status == 'STARTED':
            # Get the message from the meta information
            message = task_result.info.get('message', 'Task is in progress...')
        elif status == 'SUCCESS':
            message = task_result.info.get('message', 'Task completed successfully')
        elif status == 'FAILURE':
            # For a failed task, the `result` attribute typically contains the exception.
            # The `info` field might contain our last custom progress message or the exception itself.
            # We check if `info` is a dictionary; if so, we get our message. Otherwise, the exception is the message.
            if isinstance(task_result.info, dict):
                message = task_result.info.get('message', str(task_result.result))
            else:
                message = str(task_result.result)
        else:
            message = f"Task status: {status}"

        # Sanitize the result for JSON serialization if it's an exception object
        json_safe_result = result
        if isinstance(result, Exception):
            json_safe_result = str(result)

        return jsonify({
            'success': True,
            'task_id': task_id,
            'status': status,
            'result': json_safe_result,
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
    
    