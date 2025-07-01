from flask import Flask, request, jsonify, session, send_from_directory, Response
from flask_cors import CORS
import traceback
from .logic import extract_text_from_pdf_memory, set_process_priority, log_memory_usage, check_memory, get_container_memory_limit
from .open_ai_calls import gpt_summarize_transcript, generate_quiz_questions, generate_short_title
from .database import (
    upsert_pdf_results,
    check_file_exists, generate_content_hash, generate_file_hash,
    authenticate_user, 
    upsert_question_set, upload_pdf_to_storage, get_question_sets_for_user, get_full_study_set_data, update_question_set_title,
    touch_question_set
)
from flask_session import Session
import os
import re
from datetime import timedelta, datetime
import atexit
import glob
import gc
from io import BytesIO
import uuid

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


@app.route('/api/upload-multiple', methods=['POST'])
def upload_multiple():
    print("upload_multiple()")
    try:
        # Check if user is authenticated
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
                
        # Get memory limits for file size validation
        try:
            memory_limit = get_container_memory_limit()
            available_memory = memory_limit * 0.7  # Use only 70% of available memory
            max_file_size = min(available_memory * 0.3, 20 * 1024 * 1024)  # Max 30% of available or 20MB
            print(f"Memory limit: {memory_limit/(1024*1024):.0f}MB, Max file size: {max_file_size/(1024*1024):.1f}MB")
        except:
            max_file_size = 10 * 1024 * 1024  # Default 10MB limit
        

        set_process_priority()
        
        # Get additional user text if provided
        user_text = request.form.get('userText', '').strip()
        
        # Check if files were uploaded
        files = request.files.getlist('files') if 'files' in request.files else []
        
        # Must have either files or user text
        if len(files) == 0 and not user_text:
            raise Exception("No files or text provided")
        
        log_memory_usage("before file processing")
        
        results = {}
        total_extracted_text = ""
        files_usertext_content = set()
        
        # Process each file
        for file in files:
            if file.filename == '':
                continue
                
            log_memory_usage(f"processing {file.filename}")
            
            filename = file.filename
            
            # Read the file into an in-memory buffer to prevent "closed file" errors.
            file_content = file.read()
            files_usertext_content.add(file_content)

            # Generate hash for the file content
            file_hash = generate_file_hash(file_content)
            
            # Check if this file already exists in the database
            existing_file = check_file_exists(file_hash)
            
            if existing_file["exists"]:
                print(f"File '{filename}' already processed (hash: {file_hash[:8]}...)")
                # Use existing extracted text instead of reprocessing
                extracted_text = existing_file["data"]["text"]
                results[filename] = extracted_text
                print(f"Reusing {len(extracted_text)} characters of previously extracted text")
            else:
                print(f"New file '{filename}' (hash: {file_hash[:8]}...)")
                
                # Create separate, isolated buffers for each operation
                pdf_buffer = BytesIO(file_content)
                
                # Check memory before processing each file
                check_memory()
                
                print(f"Processing file: {filename}")
                
                # Extract text from PDF directly from memory without saving to disk
                if filename.endswith('.pdf'):

                    # Get file size for validation and logging
                    file_size = len(file_content)
                    
                    print(f"File: {filename}, {file_size / (1024*1024):.1f} MB")
                    
                    # Validate file size against memory constraints
                    if file_size > max_file_size:
                        error_msg = f"File '{filename}' ({file_size/(1024*1024):.1f}MB) exceeds maximum allowed size ({max_file_size/(1024*1024):.1f}MB) for current memory constraints"
                        print(error_msg)
                        raise Exception(error_msg)
                    
                    # Process PDF directly from memory
                    extracted_text = extract_text_from_pdf_memory(pdf_buffer, filename)
                    if extracted_text:
                        results[filename] = extracted_text
                        
                        # Upload the raw PDF to Supabase Storage
                        storage_result = upload_pdf_to_storage(file_content, file_hash, filename)

                        if storage_result["success"]:
                            print(f"Successfully uploaded '{filename}' to Supabase Storage.")
                            storage_url = storage_result["public_url"]
                            storage_file_path = storage_result["path"]
                        else:
                            print(f"Failed to upload '{filename}' to storage: {storage_result.get('error')}")
                            storage_url = None
                            storage_file_path = None

                        # Store metadata with content hash and storage URL
                        upsert_result = upsert_pdf_results({
                            "hash": file_hash,
                            "filename": filename,
                            "text": extracted_text,
                            "storage_url": storage_url,
                            "storage_file_path": storage_file_path
                        })
                        
                        if upsert_result["success"]:
                            print(f"Successfully stored file data in database (hash: {file_hash[:8]}...)")
                        else:
                            print(f"Failed to store file data: {upsert_result.get('error', 'Unknown error')}")
                    
                else:
                    print(f"Skipping non-PDF file: {filename}")
                    
        log_memory_usage("after file processing")
        
        # Combine PDF text and user text
        filenames = ""
        for key, value in results.items():
            filenames += key + " "
            total_extracted_text += value
                
        # Add user text if provided
        print(f"User text: {user_text[:100]}")
        if user_text:
            files_usertext_content.add(user_text)
            total_extracted_text += f"\n\nAdditional Notes:\n{user_text}"
            if filenames:
                filenames += "+ Additional Text"
            else:
                filenames = "User Text"
        
        user_id = session.get('user_id')
        content_hash = generate_content_hash(files_usertext_content, user_id)
        # Create a list of filenames
        content_name_list = list(results.keys())
        # Add "user text" to the list if user text was submitted
        if user_text:
            content_name_list.append("user text")

        session['content_hash'] = content_hash
        session['content_name_list'] = content_name_list
        session.modified = True

        if not total_extracted_text:
            raise Exception("No text could be extracted from PDFs and no additional text provided")
        
        log_memory_usage("before summarization")
        
        filenames = filenames.strip()
        
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
        
        # For initial generation, check if we already have questions to prevent duplicates
        if question_type == 'initial':
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
            previous_questions=previous_questions
        )
        
        # Only generate short title and upsert question set for initial generation
        if question_type == 'initial':
            short_summary = generate_short_title(total_extracted_text)
            # Upsert the question set to the database
            upsert_question_set(content_hash, user_id, question_hashes, content_name_list, total_extracted_text, short_summary, summary)
        else:
            # For focused/additional questions, just upsert the new questions
            upsert_question_set(content_hash, user_id, question_hashes, content_name_list)
        
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
        session.pop('content_name_list', None)
        session.pop('short_summary', None)
        session.pop('total_extracted_text', None)
        session.modified = True
        
        return jsonify({'success': True, 'message': 'Session content cleared.'})
    except Exception as e:
        print(f"Error clearing session content: {str(e)}")
        return jsonify({'error': str(e)}), 500

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
    
    