import os

# gunicorn.conf.py
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"  # Use the PORT env var
workers = 1
timeout = 120  # 2 minutes
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
preload_app = True