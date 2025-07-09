import os
import hashlib
import uuid
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import Dict, Any, List, Union, Optional
from datetime import datetime, timezone
import io # Import io module for BytesIO and other stream types
import redis
import json

# Load environment variables from .env file
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# Redis Configuration
REDIS_URL = os.getenv("REDIS_URL")
redis_client = None
if REDIS_URL:
    try:
        # decode_responses=True makes redis client return strings instead of bytes
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        # Test connection to ensure it's working
        redis_client.ping()
        print("Successfully connected to Redis.")
    except redis.exceptions.ConnectionError as e:
        print(f"Warning: Could not connect to Redis at {REDIS_URL}. Task status persistence will be disabled. Error: {e}")
        redis_client = None

def get_supabase_client() -> Client:
    """Create and return a Supabase client."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY environment variables")
    
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def upsert_to_table(
    table_name: str, 
    data: Union[Dict[str, Any], List[Dict[str, Any]]], 
    on_conflict: Optional[str] = None,
    returning: str = "*"
) -> Dict[str, Any]:
    """
    Upsert data to a Supabase table (insert or update if exists).
    
    Args:
        table_name (str): Name of the table to upsert to
        data (Union[Dict, List[Dict]]): Data to upsert - can be a single record or list of records
        on_conflict (Optional[str]): Column to use for conflict resolution (default: primary key)
        returning (str): Columns to return after upsert (default: "*" for all columns)
    
    Returns:
        Dict containing the result data and metadata
        
    Raises:
        Exception: If upsert operation fails
    """
    try:
        supabase = get_supabase_client()
        
        # Perform upsert operation
        query = supabase.table(table_name).upsert(data)
        
        # Add on_conflict if specified
        if on_conflict:
            query = query.on_conflict(on_conflict)
        
        # Execute and return result
        result = query.execute()
        
        return {
            "success": True,
            "data": result.data,
            "count": len(result.data) if result.data else 0,
            "table": table_name
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "table": table_name,
            "data": None,
            "count": 0
        }

# Example usage functions for common patterns
def upsert_pdf_results(pdf_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upsert pdf results data to pdfs table.
    
    Args:
        pdf_results (Dict): Pdf results data with fields like id, user_id, pdf_id, etc.
    
    Returns:
        Dict containing the result
    """
    print("upsert_pdf_results()")
    return upsert_to_table("pdfs", pdf_results)

def generate_file_hash(file_input: Union[io.BytesIO, str], algorithm: str = "sha256", chunk_size: int = 4096) -> str:
    """
    Generate a unique hash for file content. Can take a BytesIO stream or a file path.
    If a stream is provided, its position will be reset to the beginning after hashing.
    
    Args:
        file_input (Union[io.BytesIO, str]): The file content as a binary stream (BytesIO) or a file path (str).
        algorithm (str): Hashing algorithm to use (default: "sha256").
        chunk_size (int): Size of chunks to read for hashing.
    
    Returns:
        str: Hexadecimal hash string that uniquely identifies the file content.
    """
    print("generate_file_hash()")
    hash_obj = hashlib.new(algorithm)

    if isinstance(file_input, str): # It's a file path
        with open(file_input, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hash_obj.update(chunk)
    elif isinstance(file_input, io.BytesIO): # It's a BytesIO stream
        original_pos = file_input.tell() # Store original position
        file_input.seek(0) # Go to the beginning of the stream
        
        while True:
            chunk = file_input.read(chunk_size)
            if not chunk:
                break
            hash_obj.update(chunk)
            
        file_input.seek(original_pos) # Reset stream position
    else:
        raise TypeError("file_input must be a BytesIO stream or a file path string.")

    return hash_obj.hexdigest()

def generate_content_hash(content_set: set, user_id: int, is_quiz_mode: bool = False, algorithm: str = "sha256") -> str:
    """
    Generate a unique hash for a set of content (files, text, etc.) that includes the user_id and quiz mode.
    
    Args:
        content_set (set): Set of content items (bytes or strings)
        user_id (int): User ID to include in the hash
        is_quiz_mode (bool): Whether this is quiz mode (affects hash generation)
        algorithm (str): Hashing algorithm to use (default: "sha256")
    
    Returns:
        str: Hexadecimal hash string that uniquely identifies the combined content for this user and mode
    """
    hash_obj = hashlib.new(algorithm)
    
    # Include user_id and quiz mode in the hash to make it unique per user and mode
    hash_obj.update(str(user_id).encode('utf-8'))
    hash_obj.update(str(is_quiz_mode).encode('utf-8'))
    
    # Sort the content to ensure consistent hashing regardless of set order
    sorted_content = sorted(content_set, key=lambda x: x if isinstance(x, bytes) else str(x).encode('utf-8'))
    
    for content in sorted_content:
        if isinstance(content, str):
            hash_obj.update(content.encode('utf-8'))
        elif isinstance(content, bytes):
            hash_obj.update(content)
        else:
            # Convert other types to string then bytes
            hash_obj.update(str(content).encode('utf-8'))
    
    return hash_obj.hexdigest()

def check_file_exists(file_hash: str) -> Dict[str, Any]:
    """
    Check if a file with the given hash already exists in the database.
    
    Args:
        file_hash (str): The file hash to check for
    
    Returns:
        Dict containing the result and existing file data if found
    """
    try:
        supabase = get_supabase_client()
        
        result = supabase.table('pdfs').select("*").eq('hash', file_hash).execute()
        
        # Check if file exists and has a valid title (not "Untitled")
        exists = len(result.data) > 0
        if exists and result.data[0].get('short_summary') == "Untitled":
            exists = False
        
        return {
            "success": True,
            "exists": exists,
            "data": result.data[0] if result.data else None,
            "count": len(result.data)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "exists": False,
            "data": None,
            "count": 0
        }


def upsert_quiz_questions_batch(questions_with_hashes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Batch upsert multiple quiz questions with individual hashes.
    
    Args:
        questions_with_hashes (List[Dict]): List of objects with 'hash' and 'question' fields
                                          [{"hash": "abc123...", "question": {...}}, ...]
    
    Returns:
        Dict containing the result
    """
    return upsert_to_table("quiz_questions", questions_with_hashes)

def authenticate_user(email: str, password: str) -> Dict[str, Any]:
    """
    Authenticate a user by checking email and password against the users table.
    
    Args:
        email (str): User's email address
        password (str): User's password (plain text - should be hashed in production)
    
    Returns:
        Dict containing authentication result and user data if successful
    """
    try:
        supabase = get_supabase_client()
        
        # Query for user with matching email and password
        result = supabase.table('users').select("*").eq('email', email).eq('password', password).execute()
        
        if result.data and len(result.data) > 0:
            user_data = result.data[0]
            return {
                "success": True,
                "authenticated": True,
                "user": {
                    "id": user_data.get("id"),
                    "name": user_data.get("name"),
                    "email": user_data.get("email")
                }
            }
        else:
            return {
                "success": True,
                "authenticated": False,
                "user": None,
                "message": "Invalid email or password"
            }
        
    except Exception as e:
        return {
            "success": False,
            "authenticated": False,
            "user": None,
            "error": str(e),
            "error_type": type(e).__name__
        }

def upsert_question_set(
    content_hash: str, 
    user_id: int, 
    question_hashes: List[str], 
    content_names: List[str], 
    total_extracted_text: Optional[str] = '', 
    short_summary: Optional[str] = '', 
    summary: Optional[str] = '',
    is_quiz: Optional[bool] = False
) -> Dict[str, Any]:
    """
    Upsert a question set to the question_sets table.
    
    If content_hash exists, append new question_hashes to the existing list.
    If not, create a new record. For new records, total_extracted_text and short_summary are required.
    
    Args:
        content_hash (str): The hash of the content (PDFs, user text)
        user_id (int): The ID of the user
        question_hashes (List[str]): List of hashes of the generated questions
        content_names (List[str]): List of names of the content files/sources
        total_extracted_text (Optional[str]): The full text content that was summarized.
        short_summary (Optional[str]): A short, AI-generated title for the content.
        summary (Optional[str]): The full summary text.
        is_quiz (Optional[bool]): Whether this is a quiz set (True) or study set (False).
    
    Returns:
        Dict containing the result
    """
    try:
        print("Upserting question set to database")
        supabase = get_supabase_client()
        
        # Check if a record with this content_hash already exists for this user
        existing_set = supabase.table('question_sets').select("metadata").eq('hash', content_hash).eq('user_id', user_id).execute()
        
        if existing_set.data:
            # If exists, append to question_hashes in metadata
            existing_metadata = existing_set.data[0].get('metadata', {})
            existing_question_hashes = existing_metadata.get('question_hashes', [])
            
            # Use a set to avoid duplicates, then convert back to list
            updated_hashes = list(set(existing_question_hashes + question_hashes))
            
            # Prepare data for update
            update_data = {
                'metadata': {
                    'question_hashes': updated_hashes,
                    'content_names': existing_metadata.get('content_names', content_names)
                },
                'created_at': datetime.now(timezone.utc).isoformat(),
                'is_quiz': is_quiz
            }

            result = supabase.table('question_sets').update(update_data).eq('hash', content_hash).eq('user_id', user_id).execute()
            
            print("Upserted question set to database (Append)")
            return {"success": True, "operation": "append", "data": result.data}

        else:
            new_metadata = {
                'question_hashes': question_hashes,
                'content_names': content_names
            }
            
            insert_data = {
                'hash': content_hash,
                'user_id': user_id,
                'metadata': new_metadata,
                'text_content': total_extracted_text,
                'short_summary': short_summary,
                'content_summary': summary,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'is_quiz': is_quiz
            }

            result = supabase.table('question_sets').insert(insert_data).execute()

            print("Upserted question set to database (Insert)")
            return {"success": True, "operation": "insert", "data": result.data}

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }

def get_question_sets_for_user(user_id: int) -> Dict[str, Any]:
    """
    Retrieves all question sets for a given user, ordered by most recent.
    
    Args:
        user_id (int): The ID of the user.
        
    Returns:
        Dict containing the result.
    """
    try:
        supabase = get_supabase_client()
        result = supabase.table('question_sets').select(
            "*"
        ).eq('user_id', user_id).order('created_at', desc=True).execute()
        
        return {"success": True, "data": result.data}
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }

def get_full_study_set_data(content_hash: str, user_id: int) -> Dict[str, Any]:
    """
    Retrieves the full data for a study set, including all related questions.

    Args:
        content_hash (str): The hash identifying the study set.
        user_id (int): The ID of the user.

    Returns:
        A dictionary with the full study set data.
    """
    try:
        supabase = get_supabase_client()
        
        # 1. Get the question set base data
        set_result = supabase.table('question_sets').select("*").eq('hash', content_hash).eq('user_id', user_id).maybe_single().execute()
        
        if not set_result.data:
            return {"success": False, "error": "Study set not found"}
            
        study_set = set_result.data
        question_hashes = study_set.get('metadata', {}).get('question_hashes', [])
        
        all_questions = []
        if question_hashes:
            # Get all questions associated with the set
            questions_result = supabase.table('quiz_questions').select("hash, question, created_at, starred").in_('hash', question_hashes).execute()
            
            if questions_result.data:
                # Get the list of question objects
                all_questions = []
                for item in questions_result.data:
                    item['question']['id'] = str(uuid.uuid4())
                    item['question']['starred'] = item['starred']
                    item['question']['hash'] = item['hash']
                    all_questions.append(item['question'])

        return {
            "success": True,
            "data": {
                "summary": study_set.get('content_summary'),
                "short_summary": study_set.get('short_summary'),
                "total_extracted_text": study_set.get('text_content'),
                "content_hash": study_set.get('hash'),
                "content_name_list": study_set.get('metadata', {}).get('content_names', []),
                # The session expects a list containing one set of questions.
                "quiz_questions": [all_questions] if all_questions else [],
                "is_quiz": study_set.get('is_quiz', False)
            }
        }
        
    except Exception as e:
        print(f"Error getting full study set data: {e}")
        return {"success": False, "error": str(e), "data": None}

def upload_pdf_to_storage(file_input: Union[io.BytesIO, str], file_hash: str, original_filename: str, bucket_name: str) -> Dict[str, Any]:
    """
    Uploads a PDF file to the Supabase Storage bucket. Can take a BytesIO stream or a file path.

    Args:
        file_input (Union[io.BytesIO, str]): The raw content of the PDF file as a binary stream (BytesIO) or a file path (str).
        file_hash (str): The SHA-256 hash of the file content.
        original_filename (str): The original name of the file.

    Returns:
        Dict containing the result of the upload operation.
    """
    print("upload_pdf_to_storage()")
    try:
        supabase = get_supabase_client()
        
        # Use the hash as the filename to prevent duplicates and ensure a unique path
        file_path = f"{file_hash}.pdf"
        
        # Determine if we're uploading from a stream or a file path
        if isinstance(file_input, str): # It's a file path
            upload_file_arg = file_input # Pass the path directly
        elif isinstance(file_input, io.BytesIO): # It's a BytesIO stream
            upload_file_arg = file_input # Pass the BytesIO object
        else:
            raise TypeError("file_input must be a BytesIO stream or a file path string.")

        supabase.storage.from_(bucket_name).upload(
            path=file_path,
            file=upload_file_arg,
            file_options={"upsert": "false", "content-type": "application/pdf"}
        )
        
        return {
            "success": True,
            "path": file_path,
            "message": f"File '{original_filename}' uploaded successfully to '{file_path}'."
        }
        
    except Exception as e:
        error_message = str(e)
        if "resource already exists" in error_message.lower():
             file_path = f"{file_hash}.pdf"
             return {
                "success": True,
                "message": "File already exists in storage.",
                "path": file_path,
             }

        return {
            "success": False,
            "error": error_message,
            "error_type": type(e).__name__
        }

def update_question_set_title(content_hash, user_id, new_title):
    """
    Updates the 'short_summary' (title) of a specific question set.
    """
    print("Updating question set title")
    if not new_title or not isinstance(new_title, str) or not new_title.strip():
        return {"success": False, "error": "New title must be a non-empty string."}
        
    try:
        supabase = get_supabase_client()
        
        # Update the record in the question_sets table
        result = supabase.table('question_sets').update({
            'short_summary': new_title.strip(),
            'created_at': datetime.now(timezone.utc).isoformat()
        }).eq('hash', content_hash).eq('user_id', user_id).execute()
        
        if len(result.data) == 0:
            return {"success": False, "error": "No matching set found to update or no change made."}
            
        return {"success": True, "data": result.data}
    except Exception as e:
        print(f"Error updating question set title: {e}")
        return {"success": False, "error": str(e)}

def touch_question_set(content_hash: str, user_id: int) -> Dict[str, Any]:
    """Updates the created_at timestamp of a specific question set to the current time."""
    print(f"Touching question set {content_hash}.")
    try:
        supabase = get_supabase_client()
        
        result = supabase.table('question_sets').update({
            'created_at': datetime.now(timezone.utc).isoformat()
        }).eq('hash', content_hash).eq('user_id', user_id).execute()

        if result.data and len(result.data) > 0:
            return {"success": True, "data": result.data}
        else:
            # This is not a critical error for the calling function, so just log it.
            print(f"Could not find question set with hash {content_hash} for user {user_id} to touch.")
            return {"success": False, "error": "Set not found to update timestamp"}

    except Exception as e:
        print(f"Error touching question set: {e}")
        return {"success": False, "error": str(e)}


def update_question_starred_status(question_hash: str, starred_status: bool) -> Dict[str, Any]:
    """
    Updates the 'starred' status of a quiz question in the database.
    """
    try:
        supabase = get_supabase_client()
        
        result = supabase.table('quiz_questions').update({
            'starred': starred_status
        }).eq('hash', question_hash).execute()

        if result.data and len(result.data) > 0:
            return {"success": True, "data": result.data[0]}
        else:
            return {"success": False, "error": "Question not found or status already set."}

    except Exception as e:
        print(f"Error updating starred status for question {question_hash}: {e}")
        return {"success": False, "error": str(e)}

def star_all_questions_by_hashes(question_hashes: List[str], starred_status: bool) -> Dict[str, Any]:
    """
    Updates the 'starred' status of multiple quiz questions in the database.
    
    Args:
        question_hashes (List[str]): List of question hashes to update
        starred_status (bool): The starred status to set for all questions
    
    Returns:
        Dict containing the result of the bulk update operation
    """
    try:
        if not question_hashes:
            return {"success": True, "data": [], "updated_count": 0, "requested_count": 0}
        
        supabase = get_supabase_client()
        
        # Use the 'in_' filter to update multiple records at once
        result = supabase.table('quiz_questions').update({
            'starred': starred_status
        }).in_('hash', question_hashes).execute()

        updated_count = len(result.data) if result.data else 0
        
        return {
            "success": True, 
            "data": result.data,
            "updated_count": updated_count,
            "requested_count": len(question_hashes)
        }

    except Exception as e:
        print(f"Error bulk updating starred status for {len(question_hashes)} questions: {e}")
        return {
            "success": False, 
            "error": str(e),
            "updated_count": 0,
            "requested_count": len(question_hashes)
        }

def delete_question_set_and_questions(content_hash: str, user_id: int) -> Dict[str, Any]:
    """
    Deletes a question set and all its associated questions from the database.
    
    Args:
        content_hash (str): The hash of the content/question set to delete
        user_id (int): The ID of the user (for verification)
    
    Returns:
        Dict containing the result of the delete operation
    """
    try:
        supabase = get_supabase_client()
        
        # First, get the question set to retrieve the question hashes
        set_result = supabase.table('question_sets').select("metadata").eq('hash', content_hash).eq('user_id', user_id).maybe_single().execute()
        
        if not set_result.data:
            return {"success": False, "error": "Question set not found or you don't have permission to delete it"}
        
        question_hashes = set_result.data.get('metadata', {}).get('question_hashes', [])
        
        # Delete all associated questions if they exist
        if question_hashes:
            questions_delete_result = supabase.table('quiz_questions').delete().in_('hash', question_hashes).execute()
            print(f"Deleted {len(questions_delete_result.data) if questions_delete_result.data else 0} questions")
        
        # Delete the question set
        set_delete_result = supabase.table('question_sets').delete().eq('hash', content_hash).eq('user_id', user_id).execute()
        
        if not set_delete_result.data:
            return {"success": False, "error": "Failed to delete question set"}
        
        return {
            "success": True,
            "deleted_questions": len(question_hashes),
            "deleted_sets": len(set_delete_result.data)
        }
        
    except Exception as e:
        print(f"Error deleting question set {content_hash}: {e}")
        return {"success": False, "error": str(e)}

def check_question_set_exists(content_hash: str, user_id: int) -> Dict[str, Any]:
    """
    Check if a question set exists for a given user and content hash.
    
    Args:
        content_hash (str): The hash of the content to check for
        user_id (int): The ID of the user
    
    Returns:
        Dict containing the result and question set data if found
    """
    try:
        supabase = get_supabase_client()
        
        result = supabase.table('question_sets').select("*").eq('hash', content_hash).eq('user_id', user_id).maybe_single().execute()
        
        return {
            "success": True,
            "exists": result.data is not None,
            "data": result.data,
            "question_count": len(result.data.get('metadata', {}).get('question_hashes', [])) if result.data else 0
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "exists": False,
            "data": None,
            "question_count": 0
        }

def insert_feedback(user_id: int, user_email: str, user_name: str, feedback_text: str) -> Dict[str, Any]:
    """
    Inserts a new feedback entry into the 'feedback' table.

    Args:
        user_id (int): The ID of the user submitting feedback.
        user_email (str): The email of the user.
        user_name (str): The name of the user.
        feedback_text (str): The feedback message.

    Returns:
        Dict containing the result of the insert operation.
    """
    try:
        supabase = get_supabase_client()
        
        data = {
            "user_id": user_id,
            "user_email": user_email,
            "user_name": user_name,
            "feedback": feedback_text,
        }
        
        result = supabase.table('feedback').insert(data).execute()
        
        if result.data:
            return {"success": True, "data": result.data[0]}
        else:
            return {"success": False, "error": "No data returned on feedback insert."}

    except Exception as e:
        print(f"Error inserting feedback: {e}")
        return {"success": False, "error": str(e)}

def append_pdf_hash_to_user_pdfs(user_id: int, pdf_hash: str) -> Dict[str, Any]:
    """
    Appends a PDF hash to the 'pdfs' JSON object column in the 'users' table.
    Updates the timestamp even if hash already exists.
    
    Args:
        user_id (int): The ID of the user.
        pdf_hash (str): The hash of the PDF file to append.
        
    Returns:
        Dict containing the result of the update operation.
    """
    print(f"Appending hash {pdf_hash[:8]}... to user {user_id} pdfs.")

    try:
        supabase = get_supabase_client()
        
        # First, get the current user data
        user_result = supabase.table('users').select('pdfs').eq('id', user_id).maybe_single().execute()
        
        if not user_result.data:
            return {"success": False, "error": "User not found."}
        
        # Initialize empty dict if pdfs is None
        current_pdfs = user_result.data.get('pdfs') or {}
        
        # Always update/add the hash with current timestamp
        current_pdfs[pdf_hash] = {
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        # Update the 'pdfs' column with the new object
        result = supabase.table('users').update({
            'pdfs': current_pdfs
        }).eq('id', user_id).execute()

        if result.data and len(result.data) > 0:
            return {"success": True, "data": result.data[0]}
        else:
            return {"success": False, "error": "User not found or update failed."}

    except Exception as e:
        print(f"Error appending PDF hash to user {user_id} pdfs: {e}")
        return {"success": False, "error": str(e)}

def get_user_associated_pdf_metadata(user_id: int) -> Dict[str, Any]:
    """
    Retrieves metadata (hash, filename, text) for all PDFs associated with a user
    from the 'pdfs' table, based on the 'pdfs' JSON object in the 'users' table.
    
    Args:
        user_id (int): The ID of the user.
        
    Returns:
        Dict containing the result and a list of PDF metadata including updated_at timestamps.
    """
    try:
        supabase = get_supabase_client()
        
        # 1. Get the PDF hashes and timestamps from the user's profile
        user_profile_result = supabase.table('users').select('pdfs').eq('id', user_id).maybe_single().execute()
        
        if not user_profile_result.data:
            return {"success": False, "error": "User profile not found.", "data": []}
            
        pdfs_object = user_profile_result.data.get('pdfs', {})
        
        if not pdfs_object:
            return {"success": True, "data": []} # No PDFs associated with user
            
        pdf_hashes = list(pdfs_object.keys())
            
        # 2. Fetch the corresponding PDF metadata from the 'pdfs' table
        pdfs_metadata_result = supabase.table('pdfs').select("hash, filename, short_summary").in_('hash', pdf_hashes).execute()
        
        # 3. Add the updated_at timestamp from the user's pdfs object to each PDF's metadata
        enriched_metadata = []
        for pdf in pdfs_metadata_result.data:
            pdf_hash = pdf['hash']
            pdf['created_at'] = pdfs_object[pdf_hash].get('updated_at')
            enriched_metadata.append(pdf)
            
        # Sort by updated_at timestamp in descending order (most recent first)
        enriched_metadata.sort(key=lambda x: x['created_at'] if x['created_at'] else '', reverse=True)
        
        return {"success": True, "data": enriched_metadata}
        
    except Exception as e:
        print(f"Error getting user associated PDF metadata for user {user_id}: {e}")
        return {"success": False, "error": str(e), "data": []}

def get_pdf_text_by_hashes(pdf_hashes: List[str]) -> Dict[str, Any]:
    """
    Retrieves the text content for a list of PDF hashes from the 'pdfs' table.
    
    Args:
        pdf_hashes (List[str]): A list of PDF hashes.
        
    Returns:
        Dict containing the result and a dictionary of {hash: text} pairs.
    """
    try:
        supabase = get_supabase_client()
        
        if not pdf_hashes:
            return {"success": True, "data": {}}
            
        result = supabase.table('pdfs').select("hash, filename, text").in_('hash', pdf_hashes).execute()
        
        text_map = {item['hash']: {'text': item['text'], 'filename': item['filename']} for item in result.data}
        
        return {"success": True, "data": text_map}
        
    except Exception as e:
        print(f"Error getting PDF text by hashes: {e}")
        return {"success": False, "error": str(e), "data": {}}

def download_file_from_storage(bucket_name: str, file_path: str) -> Dict[str, Any]:
    """
    Downloads a file from the Supabase Storage bucket.

    Args:
        file_hash (str): The hash of the file to download.

    Returns:
        Dict containing the result of the download operation, including file content as bytes.
    """
    try:
        supabase = get_supabase_client()

        # Download the file
        file_content_bytes = supabase.storage.from_(bucket_name).download(file_path)

        if file_content_bytes:
            return {"success": True, "data": file_content_bytes, "message": f"File {file_path} downloaded successfully."}
        else:
            return {"success": False, "error": "File content is empty or not found.", "data": None}

    except Exception as e:
        error_message = str(e)
        print(f"Error downloading file {file_path} from storage: {error_message}")
        return {"success": False, "error": error_message, "data": None}

def update_pdf_text_and_summary(file_hash: str, extracted_text: str, short_summary: str) -> Dict[str, Any]:
    """
    Updates the 'text' and 'short_summary' fields for a PDF in the 'pdfs' table.

    Args:
        file_hash (str): The hash of the PDF to update.
        extracted_text (str): The extracted text content of the PDF.
        short_summary (str): The AI-generated short summary of the PDF.

    Returns:
        Dict containing the result of the update operation.
    """
    try:
        supabase = get_supabase_client()
        
        update_data = {
            'text': extracted_text,
            'short_summary': short_summary
        }

        result = supabase.table('pdfs').update(update_data).eq('hash', file_hash).execute()

        if result.data and len(result.data) > 0:
            return {"success": True, "data": result.data[0], "message": "PDF text and summary updated successfully."}
        else:
            return {"success": False, "error": "PDF not found or update failed.", "data": None}

    except Exception as e:
        error_message = str(e)
        print(f"Error updating PDF text and summary for hash {file_hash}: {error_message}")
        return {"success": False, "error": error_message, "data": None}


# --- Redis Task Management Functions ---

def update_user_task_status(user_id: int, task_id: str, filename: str, status: str, message: str) -> Dict[str, Any]:
    """
    Updates a user's task status in a Redis hash.

    Args:
        user_id (int): The ID of the user.
        task_id (str): The Celery task ID.
        filename (str): The name of the file being processed.
        status (str): The current status of the task (e.g., 'PROGRESS', 'SUCCESS', 'FAILURE').
        message (str): A descriptive message for the current status.

    Returns:
        Dict containing the result of the Redis operation.
    """
    print(f"Updating task status for user {user_id} with task_id {task_id}, filename {filename}, status {status}, message {message}.")
    if not redis_client:
        # If redis is not available, we don't treat it as a hard error, but log it.
        # The application can proceed without Redis-based task persistence.
        print("Warning: Redis client not available. Skipping task status update.")
        return {"success": False, "error": "Redis client not available."}

    try:
        key = f"user_tasks:{user_id}"
        task_data = {
            "task_id": task_id,
            "filename": filename,
            "status": status,
            "message": message,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        # Store the dictionary as a JSON string
        redis_client.hset(key, task_id, json.dumps(task_data))
        
        # Expire tasks after 36 hours so Redis doesn't fill up with old completed tasks
        redis_client.expire(key, 60 * 60 * 36)

        return {"success": True}
    except Exception as e:
        print(f"Error updating task status in Redis for user {user_id}: {e}")
        return {"success": False, "error": str(e)}

def get_user_tasks(user_id: int) -> Dict[str, Any]:
    """
    Retrieves all tasks and their statuses for a given user from Redis.

    Args:
        user_id (int): The ID of the user.

    Returns:
        Dict containing a list of task data dictionaries.
    """
    if not redis_client:
        return {"success": True, "data": []} # Return empty list if no redis

    try:
        key = f"user_tasks:{user_id}"
        tasks_raw = redis_client.hgetall(key)
        
        # hgetall with decode_responses=True returns a dict of str:str
        # We just need to parse the JSON string values
        tasks = [json.loads(task_json) for task_json in tasks_raw.values()]
        
        # Sort tasks by last updated timestamp, most recent first
        tasks.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
        
        return {"success": True, "data": tasks}
    except Exception as e:
        print(f"Error retrieving tasks from Redis for user {user_id}: {e}")
        return {"success": False, "error": str(e), "data": []}

def delete_user_tasks_by_status(user_id: int, statuses_to_clear: List[str]) -> Dict[str, Any]:
    """
    Deletes tasks from a user's Redis task hash based on their status.

    Args:
        user_id (int): The ID of the user.
        statuses_to_clear (List[str]): A list of statuses for tasks to be cleared (e.g., ['SUCCESS', 'FAILURE']).

    Returns:
        Dict containing the result of the Redis operation and count of deleted tasks.
    """
    if not redis_client:
        return {"success": False, "error": "Redis client not available."}

    try:
        key = f"user_tasks:{user_id}"
        tasks_raw = redis_client.hgetall(key)
        
        tasks_to_delete = []
        for task_id, task_json in tasks_raw.items():
            task_data = json.loads(task_json)
            if task_data.get('status') in statuses_to_clear:
                tasks_to_delete.append(task_id)
        
        if tasks_to_delete:
            deleted_count = redis_client.hdel(key, *tasks_to_delete) # Use * to unpack list into args
            print(f"Deleted {deleted_count} tasks for user {user_id} with statuses {statuses_to_clear}.")
            return {"success": True, "deleted_count": deleted_count}
        else:
            print(f"No tasks to delete for user {user_id} with statuses {statuses_to_clear}.")
            return {"success": True, "deleted_count": 0}

    except Exception as e:
        print(f"Error deleting tasks from Redis for user {user_id}: {e}")
        return {"success": False, "error": str(e), "deleted_count": 0}

def remove_pdf_hashes_from_user(user_id: int, pdf_hashes_to_remove: List[str]) -> Dict[str, Any]:
    """
    Removes a list of PDF hashes from the 'pdfs' JSON object column in the 'users' table.
    
    Args:
        user_id (int): The ID of the user.
        pdf_hashes_to_remove (List[str]): A list of PDF hashes to remove.
        
    Returns:
        Dict containing the result of the update operation.
    """
    print(f"Attempting to remove hashes {pdf_hashes_to_remove} from user {user_id} pdfs.")

    try:
        supabase = get_supabase_client()
        
        # First, get the current user data to filter the hashes
        user_result = supabase.table('users').select('pdfs').eq('id', user_id).maybe_single().execute()
        
        if not user_result.data or len(user_result.data) == 0:
            return {"success": False, "error": "User not found.", "deleted_count": 0}
        
        current_pdfs = user_result.data.get('pdfs', {})
        
        initial_count = len(current_pdfs)
        
        # Remove the specified hashes from the pdfs object
        for hash_to_remove in pdf_hashes_to_remove:
            current_pdfs.pop(hash_to_remove, None)
        
        deleted_count = initial_count - len(current_pdfs)

        if deleted_count == 0:
            print(f"No matching PDFs found to remove for user {user_id}.")
            return {"success": True, "message": "No matching PDFs found to remove.", "deleted_count": 0}

        # Update the 'pdfs' column with the filtered object
        result = supabase.table('users').update({
            'pdfs': current_pdfs
        }).eq('id', user_id).execute()

        if result.data and len(result.data) > 0:
            return {"success": True, "data": result.data[0], "deleted_count": deleted_count}
        else:
            return {"success": False, "error": "User not found or update failed.", "deleted_count": 0}

    except Exception as e:
        print(f"Error removing PDF hashes from user {user_id} pdfs: {e}")
        return {"success": False, "error": str(e), "deleted_count": 0}
