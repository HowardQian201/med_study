import os

# gunicorn.conf.py
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"  # Use the PORT env var
workers = 1
timeout = 180  # 3 minutes for AI processing
keepalive = 2
max_requests = 100  # Restart worker after 100 requests to prevent memory buildup
max_requests_jitter = 20
preload_app = True
worker_class = "sync"

# Memory optimizations
worker_tmp_dir = "/dev/shm"  # Use tmpfs for faster worker communication
worker_connections = 1000

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190