from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
import traceback
from .logic import extract_text_from_pdf_memory, gpt_summarize_transcript, set_process_priority, generate_quiz_questions, generate_focused_questions, log_memory_usage, check_memory, get_container_memory_limit, upload_to_r2
from flask_session import Session
import os
import re
from datetime import timedelta
import shutil
import atexit
import glob
import gc
from io import BytesIO


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

# Store active temp directories
active_temp_dirs = {}

# Mock user database (replace with actual database in production)
USERS = {
    'test@example.com': {
        'name': 'Test User',
        'password': 'password123',  # In production, store hashed passwords
        'id': 1
    }
}
# Email validation regex
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

Session(app)


# Cleanup on application exit
@atexit.register
def cleanup_on_exit():
    print("cleanup_on_exit()")
    try:
        # Clean up any remaining temp directories
        for user_id, temp_dir in list(active_temp_dirs.items()):
            cleanup_temp_dir(user_id)
            
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


def cleanup_temp_dir(user_id):
    """Clean up temporary directory for a user"""
    if user_id in active_temp_dirs:
        try:
            temp_dir = active_temp_dirs[user_id]
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            del active_temp_dirs[user_id]
        except Exception as e:
            print(f"Error cleaning up temp directory for user {user_id}: {str(e)}")

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

        user = USERS.get(email)
        if not user or user['password'] != password:
            return jsonify({'message': 'Invalid credentials'}), 401

        # Clear any existing session data
        session.clear()
        
        # Set new session data
        session['user_id'] = user['id']
        session['name'] = user['name']
        session['email'] = email
        
        # Ensure PDF results are empty on fresh login
        session['pdf_results'] = {}
        session['user_text'] = ""
        session['summary'] = ""
        session['quiz_questions'] = []
        
        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'message': str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    print("logout()")
    try:
        # Clean up temp directory before clearing session
        if 'user_id' in session:
            cleanup_temp_dir(session['user_id'])
        
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
        
        user_id = session['user_id']
        
        # Get memory limits for file size validation
        try:
            memory_limit = get_container_memory_limit()
            available_memory = memory_limit * 0.7  # Use only 70% of available memory
            max_file_size = min(available_memory * 0.3, 20 * 1024 * 1024)  # Max 30% of available or 20MB
            print(f"Memory limit: {memory_limit/(1024*1024):.0f}MB, Max file size: {max_file_size/(1024*1024):.1f}MB")
        except:
            max_file_size = 10 * 1024 * 1024  # Default 10MB limit
        
        # Clean up any existing temp directory for this user (for cleanup consistency)
        cleanup_temp_dir(user_id)

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
        
        # Process each file
        for file in files:
            if file.filename == '':
                continue
                
            log_memory_usage(f"processing {file.filename}")
            
            filename = file.filename
            
            # Read the file into an in-memory buffer to prevent "closed file" errors.
            file_content = file.read()

            # Create separate, isolated buffers for each operation
            r2_buffer = BytesIO(file_content)
            pdf_buffer = BytesIO(file_content)
            
            # Check memory before processing each file
            check_memory()
            
            print(f"Processing file: {filename}")
            
            # Extract text from PDF directly from memory without saving to disk
            if filename.endswith('.pdf'):

                # # Upload the file to R2 before any other processing
                # r2_url = upload_to_r2(r2_buffer, filename, user_id)
                # if r2_url:
                #     print(f"File '{filename}' stored in R2 at: {r2_url}")
                # else:
                #     print(f"Skipped or failed to upload '{filename}' to R2. Continuing with local processing.")

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
                    
        log_memory_usage("after file processing")
        
        # Combine PDF text and user text
        filenames = ""
        for key, value in results.items():
            filenames += key + " "
            total_extracted_text += value
                
        # Add user text if provided
        print(f"User text: {user_text[:100]}")
        if user_text:
            total_extracted_text += f"\n\nAdditional Notes:\n{user_text}"
            if filenames:
                filenames += "+ Additional Text"
            else:
                filenames = "User Text"
        
        if not total_extracted_text:
            raise Exception("No text could be extracted from PDFs and no additional text provided")
        
        log_memory_usage("before summarization")
        
        filenames = filenames.strip()
        
        print(f"Text length being sent to AI: {len(total_extracted_text)} characters")
        
        summary = gpt_summarize_transcript(total_extracted_text)
        
        # Clear the large text variable immediately
        del total_extracted_text
        gc.collect()
        
        log_memory_usage("after summarization")
        
        # Store results in session
        session['summary'] = summary
        session['pdf_results'] = results
        session['user_text'] = user_text  # Store user text separately
        
        log_memory_usage("upload complete")
        
        return jsonify({
            'success': True,
            'results': summary
        })

    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        log_memory_usage("upload error")
        return jsonify({'error': str(e)}), 500
    finally:
        # Force garbage collection to clean up memory
        log_memory_usage("final cleanup")
        gc.collect()

@app.route('/api/cleanup', methods=['POST'])
def cleanup():
    """Endpoint to manually trigger cleanup"""
    print("cleanup()")
    try:
        # Allow cleanup even if no user session exists
        user_id = session.get('user_id')
        if user_id:
            cleanup_temp_dir(user_id)
            return jsonify({'success': True, 'message': 'Cleanup completed for authenticated user'})
        else:
            # Still return success for unauthenticated requests
            # This allows frontend cleanup calls to succeed even after logout/session expiry
            return jsonify({'success': True, 'message': 'No cleanup needed - no active session'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear-results', methods=['POST'])
def clear_results():
    """Endpoint to clear PDF results from session"""
    print("clear_results()")
    try:
        if 'user_id' in session:
            if 'summary' in session:
                session['pdf_results'] = {}
                session['summary'] = ""
                session['user_text'] = ""  # Clear user text as well
                session['quiz_questions'] = []
            return jsonify({'success': True})
        return jsonify({'error': 'Unauthorized'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-quiz', methods=['GET'])
def generate_quiz():
    """Endpoint to generate quiz questions from the stored summary"""
    print("generate_quiz()")
    try:
        # Check if user is authenticated
        if 'user_id' not in session:
            print(f"No user_id in session - returning 401")
            return jsonify({'error': 'Unauthorized'}), 401
            
        # Check if there's a summary to work with
        summary = session.get('summary', '')
        if not summary:
            print(f"No summary available - returning 400")
            return jsonify({'error': 'No summary available. Please upload PDFs first.'}), 400
        
        # Check if we already have questions for this summary (prevent duplicates)
        existing_questions = session.get('quiz_questions', [])
        if existing_questions:
            latest_questions = existing_questions[-1]
            print(f"Found existing questions ({len(latest_questions)} questions) - returning cached")
            return jsonify({
                'success': True,
                'questions': latest_questions
            })
            
        # Generate questions
        questions = generate_quiz_questions(summary)
        
        # Store questions in session
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

@app.route('/api/generate-more-questions', methods=['POST'])
def generate_more_questions():
    """Endpoint to generate additional questions based on user performance"""
    print("generate_more_questions()")
    try:
        # Check if user is authenticated
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
            
        # Check if there's a summary to work with
        summary = session.get('summary', '')
        if not summary:
            return jsonify({'error': 'No summary available. Please upload PDFs first.'}), 400
            
        # Get the request data
        data = request.json
        incorrect_question_ids = data.get('incorrectQuestionIds', [])
        previous_questions = data.get('previousQuestions', [])
        print(incorrect_question_ids)
        print(previous_questions)
        
        # Generate new questions
        new_questions = generate_focused_questions(summary, incorrect_question_ids, previous_questions)
        
        # Store new questions in session
        quiz_questions = session.get('quiz_questions', [])
        quiz_questions.append(new_questions)
        session['quiz_questions'] = quiz_questions
        session.modified = True
        
        return jsonify({
            'success': True,
            'questions': new_questions
        })
    except Exception as e:
        print(f"Error generating more questions: {str(e)}")
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
    """Endpoint to regenerate the summary from stored PDF text and optional new user text"""
    print("regenerate_summary()")
    try:
        # Check if user is authenticated
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        
        # Get request data
        data = request.json or {}
        new_user_text = data.get('userText', '').strip() if data.get('userText') else ''
        
        # Get stored data
        pdf_results = session.get('pdf_results', {})
        stored_user_text = session.get('user_text', '')
        
        # Use new user text if provided, otherwise use stored user text
        user_text = new_user_text if new_user_text else stored_user_text
        
        # Must have either PDF text or user text
        if not pdf_results and not user_text:
            return jsonify({'error': 'No PDF text or user text available. Please upload PDFs or enter text.'}), 400
        
        # Combine all text sources
        total_extracted_text = ""
        filenames = ""
        
        # Add PDF text
        for key, value in pdf_results.items():
            filenames += key + " "
            total_extracted_text += value
        
        # Add user text if provided
        if user_text:
            total_extracted_text += f"\n\nAdditional Notes:\n{user_text}"
            if filenames:
                filenames += "+ Additional Text"
            else:
                filenames = "User Text"
        
        filenames = filenames.strip()
        
        # Generate new summary
        summary = gpt_summarize_transcript(total_extracted_text)
        summary = f"Summary of: {filenames}\n\n{summary}"
        
        # Update session with new data
        session['summary'] = summary
        session['user_text'] = user_text  # Update stored user text
        session['quiz_questions'] = []  # Clear questions since summary changed
        
        return jsonify({
            'success': True,
            'summary': summary
        })
    except Exception as e:
        print(f"Error regenerating summary: {str(e)}")
        traceback.print_exc()
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
    
    
# if __name__ == '__main__':
#     # app.run(debug=True)
#     app.run(host='0.0.0.0', port=5000)