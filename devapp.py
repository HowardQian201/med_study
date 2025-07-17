import uvicorn
import os
import asyncio # Import asyncio

if __name__ == "__main__":
    # Set Windows-specific event loop policy for multiprocessing compatibility
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    port = int(os.environ.get("PORT", 5000))
    # For development, use reload=True which implies a single worker.
    # The 'workers' parameter is incompatible with reload=True and is therefore removed.
    # If you need concurrency, use 'gunicorn -c gunicorn.conf.py backend.main:app' or 'uvicorn backend.main:app --workers N'.
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=True # Enable auto-reloading for development convenience
    )