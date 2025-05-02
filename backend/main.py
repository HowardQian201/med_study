from flask import Flask, request, jsonify, session
from flask_cors import CORS
import tempfile
from pathlib import Path
import traceback
from logic import process_audio, gpt_summarize_transcript, set_process_priority, save_uploaded_file, transcribe_audio
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
app.config['SECRET_KEY'] = os.urandom(24)  # Generate a random secret key
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

        # Set session
        session['user_id'] = user['id']
        session['name'] = user['name']
        session['email'] = email
        
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
                'transcription': session.get('transcription', ''),
            })
        return jsonify({'authenticated': False})
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@app.route('/api/upload-and-extract', methods=['POST'])
def upload_and_extract():
    print("Starting upload and extract process")
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

        set_process_priority()
        temp_dir = Path(temp_dir)
        input_path = temp_dir / "input.mp4"
        processed_path = temp_dir / "processed.wav"

        # Validate and save uploaded file
        if 'file' not in request.files:
            raise Exception("No file part in the request")
        
        file = request.files['file']
        if file.filename == '':
            raise Exception("No selected file")
        
        total_bytes = save_uploaded_file(file, input_path)
        if total_bytes == 0:
            raise Exception("Received empty file")
        
        print(f"File received: {total_bytes / (1024*1024):.1f} MB")

        process_audio(input_path, processed_path)
        
        # Transcribe
        transcription = transcribe_audio(processed_path)
        if not transcription:
            raise Exception("No transcription produced")

        print("Transcription result:", transcription)
        print("Transcription time:", time.time() - start_time)
        session['transcription'] = transcription
        return jsonify({
            'success': True,
            'transcription': transcription
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

if __name__ == '__main__':
    app.run(debug=True)