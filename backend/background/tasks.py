from celery import Celery
import os
from io import BytesIO # Import BytesIO for in-memory binary streams
from backend.database import download_file_from_storage, update_pdf_text_and_summary, append_pdf_hash_to_user_pdfs # Import new database functions
from backend.logic import extract_text_from_pdf_memory # Import PDF extraction logic
from backend.open_ai_calls import generate_short_title # Import short title generation
from dotenv import load_dotenv

load_dotenv()
celery_app = Celery(
    'med_study',
    broker=os.getenv("REDIS_URL"),
    backend=os.getenv("REDIS_URL")
)

@celery_app.task
def print_number_task(number):
    print(f"Celery task received number: {number}")
    return f"Processed number: {number}"

@celery_app.task
def process_pdf_task(file_hash, original_filename, bucket_name, file_path, user_id):
    """
    Celery task to: 
    1. Retrieve a PDF file from Supabase Storage using its storage_url and file_path.
    2. Extract text from the PDF.
    3. Generate a short title for the extracted text using AI.
    4. Update the 'pdfs' table in Supabase with the extracted text and short title.
    """
    print(f"Starting process_pdf_task for file hash: {file_hash}")

    # 1. Retrieve the PDF file from Supabase Storage
    download_result = download_file_from_storage(bucket_name, file_path)
    if not download_result['success']:
        error_msg = f"Failed to download PDF with hash {file_hash}: {download_result.get('error', 'Unknown error')}"
        print(error_msg)
        return {"status": "failed", "message": error_msg}
    
    pdf_content_bytes = download_result['data']
    print(f"Successfully downloaded {len(pdf_content_bytes)} bytes for hash {file_hash}.")

    # 2. Extract text from the PDF
    try:
        # extract_text_from_pdf_memory expects a BytesIO object
        extracted_text = extract_text_from_pdf_memory(BytesIO(pdf_content_bytes))
        if not extracted_text:
            raise Exception("No text extracted from PDF.")
        print(f"Successfully extracted text (length: {len(extracted_text)}) for hash {file_hash}.")
    except Exception as e:
        error_msg = f"Failed to extract text from PDF {file_hash}: {str(e)}"
        print(error_msg)
        return {"status": "failed", "message": error_msg}

    # 3. Generate a short title for the extracted text
    try:
        short_title = generate_short_title(extracted_text)
        print(f"Successfully generated short title: '{short_title}' for hash {file_hash}.")
    except Exception as e:
        error_msg = f"Failed to generate short title for PDF {file_hash}: {str(e)}"
        print(error_msg)
        # It's okay to proceed without a short title if it fails, just log it.
        short_title = "No Summary"

    # 4. Update the 'pdfs' table in Supabase with the extracted text and short title
    update_result = update_pdf_text_and_summary(file_hash, extracted_text, short_title)
    if not update_result['success']:
        error_msg = f"Failed to update database for PDF {file_hash}: {update_result.get('error', 'Unknown error')}"
        print(error_msg)
        return {"status": "failed", "message": error_msg}
    
    # 5. Append the PDF hash to the user's list of PDFs
    append_result = append_pdf_hash_to_user_pdfs(user_id, file_hash)
    if not append_result['success']:
        error_msg = f"Failed to append PDF hash {file_hash} to user {user_id}'s PDFs: {append_result.get('error', 'Unknown error')}"
        print(error_msg)
        return {"status": "failed", "message": error_msg}
    
    print(f"Successfully processed and updated database for file hash: {file_hash}.")
    return {"status": "completed", "file_hash": file_hash, "extracted_text_length": len(extracted_text)}

