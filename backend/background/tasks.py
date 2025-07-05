from .worker import celery_app

@celery_app.task
def print_number_task(number):
    print(f"Received number: {number}")
    return f"Successfully printed number: {number}"
