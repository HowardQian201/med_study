from io import BytesIO # Import BytesIO for in-memory binary streams
from backend.database import download_file_from_storage, update_pdf_text_and_summary, append_pdf_hash_to_user_pdfs, update_user_task_status # Import new database functions
from backend.logic import extract_text_from_pdf_memory # Import PDF extraction logic
from backend.open_ai_calls import generate_short_title # Import short title generation
from datetime import datetime, timezone # Import timezone

# Import the main Celery app instance from worker.py
from backend.background.worker import app


@app.task
def print_number_task(number):
    print(f"Celery task received number: {number}")
    return f"Processed number: {number}"

@app.task(bind=True, soft_time_limit=150, time_limit=155)
def process_pdf_task(self, file_hash, bucket_name, file_path, user_id, original_filename):
    """
    Celery task to: 
    1. Retrieve a PDF file from Supabase Storage using its storage_url and file_path.
    2. Extract text from the PDF.
    3. Generate a short title for the extracted text using AI.
    4. Update the 'pdfs' table in Supabase with the extracted text and short title.
    """
    def _update_status(state, message):
        """Helper to update both Celery state and Redis."""
        timestamp = datetime.now(timezone.utc).strftime("%m-%d %H:%M")
        full_message = f"{message} (UTC {timestamp})"
        self.update_state(state=state, meta={'message': full_message})
        update_user_task_status(user_id, self.request.id, original_filename, state, full_message)

    print(f"Starting process_pdf_task for file: {file_path}")
    
    try:

        # 1. Retrieve the PDF file from Supabase Storage
        _update_status('IN PROGRESS', '[1/5] Downloading PDF')
        download_result = download_file_from_storage(bucket_name, file_path)
        if not download_result['success']:
            raise ValueError(f"Failed to download PDF: {download_result.get('error', 'Unknown error')}")
        
        pdf_content_bytes = download_result['data']
        print(f"Successfully downloaded {len(pdf_content_bytes)} bytes for hash {file_hash}.")

        # 2. Extract text from the PDF
        _update_status('IN PROGRESS', '[2/5] Extracting text from PDF')
        extracted_text = extract_text_from_pdf_memory(BytesIO(pdf_content_bytes))
        if not extracted_text:
            raise ValueError("No text extracted from PDF.")
        
        cleaned_extracted_text = extracted_text.replace('\u0000', '').encode('utf-8', errors='ignore').decode('utf-8')
        print(f"Successfully extracted text (length: {len(cleaned_extracted_text)}) for hash {file_hash}.")

        # 3. Generate a short title for the extracted text
        _update_status('IN PROGRESS', '[3/5] Generating short title')
        try:
            short_title = generate_short_title(cleaned_extracted_text)
            print(f"Successfully generated short title: '{short_title}' for hash {file_hash}.")
        except Exception as e:
            # Not a critical failure, we just log it and continue.
            print(f"Warning: Failed to generate short title: {str(e)}")
            _update_status('IN PROGRESS', f"Warning: could not generate title ({e})")
            short_title = "Untitled PDF"

        # 4. Update the 'pdfs' table in Supabase with the extracted text and short title
        _update_status('IN PROGRESS', '[4/5] Saving extracted content to database')
        update_result = update_pdf_text_and_summary(file_hash, cleaned_extracted_text, short_title)
        if not update_result['success']:
            raise ValueError(f"Failed to update database: {update_result.get('error', 'Unknown error')}")
        
        # 5. Append the PDF hash to the user's list of PDFs
        _update_status('IN PROGRESS', '[5/5] Linking PDF to your account')
        append_result = append_pdf_hash_to_user_pdfs(user_id, file_hash)
        if not append_result['success']:
            raise ValueError(f"Failed to link PDF to user: {append_result.get('error', 'Unknown error')}")
        
        print(f"Successfully processed and updated database for file hash: {file_hash}.")
        _update_status('SUCCESS', 'PDF processing complete')
        return {"status": "completed", "file_hash": file_hash, "extracted_text_length": len(cleaned_extracted_text)}

    except Exception as e:
        error_msg = f"PDF processing failed: {str(e)}"
        print(error_msg)
        # Manually update our custom Redis store to ensure the 'FAILURE' state is immediately persisted.
        timestamp = datetime.now(timezone.utc).strftime("%m-%d %H:%M")
        full_message = f"{error_msg} (UTC {timestamp})"
        update_user_task_status(user_id, self.request.id, original_filename, 'FAILURE', full_message)
        # Now, raise the exception to let Celery handle its internal state.
        # This will mark the task as FAILURE in the Celery backend and store the traceback.
        raise e
