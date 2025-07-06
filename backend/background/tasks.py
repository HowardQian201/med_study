from celery import Celery
import os # For simulating file access

celery_app = Celery(
    'med_study',
    broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

@celery_app.task
def print_number_task(number):
    print(f"Celery task received number: {number}")
    return f"Processed number: {number}"

@celery_app.task
def process_pdf_task(file_path):
    """
    Placeholder task to simulate PDF text extraction.
    Will be implemented later.
    """
    print(f"Celery task (process_pdf_task) received file path: {file_path}")
    # Simulate some work
    import time
    time.sleep(5) # Simulate processing time
    print(f"Simulated processing for {file_path} complete.")
    return {"status": "completed", "file_path": file_path, "extracted_text_length": 0}
