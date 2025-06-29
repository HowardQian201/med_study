import os
import hashlib
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import Dict, Any, List, Union, Optional

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

def generate_content_hash(content_set: set, algorithm: str = "sha256") -> str:
    """
    Generate a unique hash for a set of content (files, text, etc.).
    
    Args:
        content_set (set): Set of content items (bytes or strings)
        algorithm (str): Hashing algorithm to use (default: "sha256")
    
    Returns:
        str: Hexadecimal hash string that uniquely identifies the combined content
    """
    hash_obj = hashlib.new(algorithm)
    
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
