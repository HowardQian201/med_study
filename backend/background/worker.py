from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()


REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

celery_app = Celery(
    'medstudy_worker',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['backend.background.tasks']
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)
