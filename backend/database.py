import os
import hashlib
import uuid
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import Dict, Any, List, Union, Optional
from datetime import datetime, timezone

# Load environment variables from .env file
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

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
    return upsert_to_table("pdfs", pdf_results)

def generate_file_hash(file_content: bytes, algorithm: str = "sha256") -> str:
    """
    Generate a unique hash for file content.
    
    Args:
        file_content (bytes): The raw file content as bytes
        algorithm (str): Hashing algorithm to use (default: "sha256")
    
    Returns:
        str: Hexadecimal hash string that uniquely identifies the file content
    """
    hash_obj = hashlib.new(algorithm)
    hash_obj.update(file_content)
    return hash_obj.hexdigest()

def generate_content_hash(content_set: set, user_id: int, algorithm: str = "sha256") -> str:
    """
    Generate a unique hash for a set of content (files, text, etc.) that includes the user_id.
    
    Args:
        content_set (set): Set of content items (bytes or strings)
        user_id (int): User ID to include in the hash
        algorithm (str): Hashing algorithm to use (default: "sha256")
    
    Returns:
        str: Hexadecimal hash string that uniquely identifies the combined content for this user
    """
    hash_obj = hashlib.new(algorithm)
    
    # Include user_id in the hash to make it unique per user
    hash_obj.update(str(user_id).encode('utf-8'))
    
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
        
        return {
            "success": True,
            "exists": len(result.data) > 0,
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
    summary: Optional[str] = ''
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
                'created_at': datetime.now(timezone.utc).isoformat()
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
                'created_at': datetime.now(timezone.utc).isoformat()
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
            questions_result = supabase.table('quiz_questions').select("question, created_at").in_('hash', question_hashes).execute()
            
            if questions_result.data:
                # Get the list of question objects
                all_questions = [item['question'] for item in questions_result.data]

                # Re-assign unique IDs to all questions to prevent front-end conflicts.
                # This handles both old integer IDs and ensures uniqueness for the session.
                for question in all_questions:
                    if isinstance(question, dict):
                        question['id'] = str(uuid.uuid4())

        return {
            "success": True,
            "data": {
                "summary": study_set.get('content_summary'),
                "short_summary": study_set.get('short_summary'),
                "total_extracted_text": study_set.get('text_content'),
                "content_hash": study_set.get('hash'),
                "content_name_list": study_set.get('metadata', {}).get('content_names', []),
                # The session expects a list containing one set of questions.
                "quiz_questions": [all_questions] if all_questions else []
            }
        }
        
    except Exception as e:
        print(f"Error getting full study set data: {e}")
        return {"success": False, "error": str(e), "data": None}

def upload_pdf_to_storage(file_content: bytes, file_hash: str, original_filename: str) -> Dict[str, Any]:
    """
    Uploads a PDF file to the Supabase Storage bucket.

    Args:
        file_content (bytes): The raw content of the PDF file.
        file_hash (str): The SHA-256 hash of the file content.
        original_filename (str): The original name of the file.

    Returns:
        Dict containing the result of the upload operation.
    """
    try:
        supabase = get_supabase_client()
        bucket_name = "pdfs"
        
        # Use the hash as the filename to prevent duplicates and ensure a unique path
        file_path = f"{file_hash}.pdf"
        
        # Upload the file. `file_options={"upsert": "false"}` prevents re-uploading.
        supabase.storage.from_(bucket_name).upload(
            path=file_path,
            file=file_content,
            file_options={"upsert": "false", "content-type": "application/pdf"}
        )

        # Get the public URL to store in our database metadata
        public_url = supabase.storage.from_(bucket_name).get_public_url(file_path)
        
        return {
            "success": True,
            "path": file_path,
            "public_url": public_url,
            'file_path': file_path,
            "message": f"File '{original_filename}' uploaded successfully to '{file_path}'."
        }
        
    except Exception as e:
        error_message = str(e)
        # If the error indicates the file already exists, we treat it as a success for our workflow.
        if "resource already exists" in error_message.lower():
             file_path = f"{file_hash}.pdf"
             public_url = get_supabase_client().storage.from_('pdfs').get_public_url(file_path)
             return {
                "success": True,
                "message": "File already exists in storage.",
                "path": file_path,
                "public_url": public_url
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
