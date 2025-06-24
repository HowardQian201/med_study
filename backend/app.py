from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
import tempfile
from pathlib import Path
import traceback
from logic import extract_text_from_pdf, gpt_summarize_transcript, set_process_priority, save_uploaded_file, generate_quiz_questions, generate_focused_questions
import time
from flask_session import Session
import os
import re
from datetime import timedelta
import shutil
import atexit
import glob


app = Flask(__name__)

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
    print("Starting multiple file upload and extract process")
    temp_dir = None
    try:
        # Check if user is authenticated
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401

        start_time = time.time()
        
        # Clean up any existing temp directory for this user
        cleanup_temp_dir(session['user_id'])

        # Create new temp directory
        temp_dir = tempfile.mkdtemp()
        active_temp_dirs[session['user_id']] = temp_dir
        temp_dir = Path(temp_dir)

        set_process_priority()
        
        # Check if files were uploaded
        if 'files' not in request.files:
            raise Exception("No files part in the request")
        
        files = request.files.getlist('files')
        if len(files) == 0:
            raise Exception("No files selected")
        
        results = session['pdf_results']
        total_extracted_text = ""
        
        # Process each file
        for file in files:
            if file.filename == '':
                continue
                
            # Create a unique filename for each file
            filename = file.filename
            input_path = temp_dir / filename
            
            # Save the file
            total_bytes = save_uploaded_file(file, input_path)
            if total_bytes == 0:
                continue
            
            print(f"File received: {filename}, {total_bytes / (1024*1024):.1f} MB")
            
            # Extract text from PDF
            extracted_text = extract_text_from_pdf(input_path)
            if extracted_text:
                results[filename] = extracted_text
                
        
        if not results:
            raise Exception("No text could be extracted from any of the PDFs")

        print(results.keys())
        print(f"Extraction completed for {len(results)} files in {time.time() - start_time:.2f} seconds")
        
        filenames = ""
        for key, value in results.items():
            filenames += key + " "
            total_extracted_text += value
        filenames = filenames.strip()
        summary = gpt_summarize_transcript(total_extracted_text)
        summary = f"Summary of: {filenames}\n\n{summary}"
                
        # Store results in session
        session['summary'] = summary
        session['pdf_results'] = results
        
        return jsonify({
            'success': True,
            'results': summary
        })

    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        # Clean up temp directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                if 'user_id' in session:
                    del active_temp_dirs[session['user_id']]
            except Exception as e:
                print(f"Error cleaning up temp directory: {str(e)}")

@app.route('/api/cleanup', methods=['POST'])
def cleanup():
    """Endpoint to manually trigger cleanup"""
    try:
        if 'user_id' in session:
            cleanup_temp_dir(session['user_id'])
            return jsonify({'success': True})
        return jsonify({'error': 'Unauthorized'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear-results', methods=['POST'])
def clear_results():
    """Endpoint to clear PDF results from session"""
    try:
        if 'user_id' in session:
            if 'summary' in session:
                session['pdf_results'] = {}
                session['summary'] = ""
                session['quiz_questions'] = []
            return jsonify({'success': True})
        return jsonify({'error': 'Unauthorized'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-quiz', methods=['GET'])
def generate_quiz():
    """Endpoint to generate quiz questions from the stored summary"""
    try:
        # Check if user is authenticated
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
            
        # Check if there's a summary to work with
        summary = session.get('summary', '')
        if not summary:
            return jsonify({'error': 'No summary available. Please upload PDFs first.'}), 400
            
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
        
        print(f"Added new question set. Total sets now: {len(quiz_questions)}")
        print(f"New set has {len(new_questions)} questions")
        
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
    try:
        # Check if user is authenticated
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
            
        # Get stored questions
        questions = session.get('quiz_questions', [])
        questions = questions[-1] if questions else []
        
        return jsonify({
            'success': True,
            'questions': questions
        })
    except Exception as e:
        print(f"Error retrieving quiz questions: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-all-quiz-questions', methods=['GET'])
def get_all_quiz_questions():
    """Endpoint to retrieve all stored quiz questions from previous sessions"""
    try:
        # Check if user is authenticated
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
            
        # Get all stored questions
        all_questions = session.get('quiz_questions', [])
        
        print(f"Retrieved {len(all_questions)} question sets from session")
        for i, question_set in enumerate(all_questions):
            print(f"  Set {i+1}: {len(question_set)} questions")
        
        return jsonify({
            'success': True,
            'questions': all_questions
        })
    except Exception as e:
        print(f"Error retrieving all quiz questions: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/regenerate-summary', methods=['POST'])
def regenerate_summary():
    """Endpoint to regenerate the summary from stored PDF text"""
    try:
        # Check if user is authenticated
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
            
        # Check if there's PDF text to work with
        pdf_results = session.get('pdf_results', {})
        if not pdf_results:
            return jsonify({'error': 'No PDF text available. Please upload PDFs first.'}), 400
        
        # Combine all PDF text
        total_extracted_text = ""
        filenames = ""
        for key, value in pdf_results.items():
            filenames += key + " "
            total_extracted_text += value
        filenames = filenames.strip()
        
        # Generate new summary
        summary = gpt_summarize_transcript(total_extracted_text)
        summary = f"Summary of: {filenames}\n\n{summary}"
        
        # Update session
        session['summary'] = summary
        
        return jsonify({
            'success': True,
            'summary': summary
        })
    except Exception as e:
        print(f"Error regenerating summary: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    

if __name__ == '__main__':
    # app.run(debug=True)
    app.run(host='0.0.0.0', port=5000)