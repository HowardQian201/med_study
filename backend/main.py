from flask import Flask, request, jsonify, session
from flask_cors import CORS
import tempfile
from pathlib import Path
import traceback
from logic import extract_text_from_pdf, gpt_summarize_transcript, set_process_priority, save_uploaded_file
import time
from flask_session import Session
import os
import re
from datetime import timedelta
import shutil
import atexit
import glob
import threading


app = Flask(__name__)
CORS(app, supports_credentials=True)  # Enable credentials for CORS

# Configure session
app.config['SECRET_KEY'] = 'your-fixed-secret-key-for-development'  # Use environment variable in production
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

def cleanup_expired_sessions():
    """Clean up expired session files"""
    try:
        session_dir = app.config['SESSION_FILE_DIR']
        if not os.path.exists(session_dir):
            return

        current_time = time.time()
        for session_file in glob.glob(os.path.join(session_dir, 'session_*')):
            try:
                # Check file modification time
                file_time = os.path.getmtime(session_file)
                # If file is older than session lifetime, delete it
                if current_time - file_time > app.config['PERMANENT_SESSION_LIFETIME'].total_seconds():
                    os.remove(session_file)
                    print(f"Cleaned up expired session: {session_file}")
            except Exception as e:
                print(f"Error cleaning up session file {session_file}: {str(e)}")
    except Exception as e:
        print(f"Error in session cleanup: {str(e)}")

def run_cleanup_periodically():
    """Run cleanup at regular intervals"""
    while True:
        cleanup_expired_sessions()
        time.sleep(app.config['CLEANUP_INTERVAL'])

# Start cleanup thread
cleanup_thread = threading.Thread(target=run_cleanup_periodically, daemon=True)
cleanup_thread.start()

# Cleanup on application exit
@atexit.register
def cleanup_on_exit():
    cleanup_expired_sessions()
    # Clean up any remaining temp directories
    for user_id, temp_dir in list(active_temp_dirs.items()):
        cleanup_temp_dir(user_id)


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
        session.pop('pdf_results', None)
        session.pop('user_id', None)
        session.pop('name', None)
        session.pop('email', None)
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
                'pdf_results': session.get('pdf_results', {})
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
        
        # Store results in session
        session['pdf_results'] = results
        
        return jsonify({
            'success': True,
            'results': results
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
            if 'pdf_results' in session:
                session['pdf_results'] = {}
            return jsonify({'success': True})
        return jsonify({'error': 'Unauthorized'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)