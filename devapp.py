import uvicorn
import os
import asyncio # Import asyncio

if __name__ == "__main__":
    # Set Windows-specific event loop policy for multiprocessing compatibility
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    port = int(os.environ.get("PORT", 5000))
    # Get the number of workers from an environment variable, default to 1 for basic local use.
    # On production platforms like Render, WEB_CONCURRENCY is often set to match CPU cores.
    workers = int(os.environ.get("WEB_CONCURRENCY", 1))

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        workers=workers # Use the configured number of workers for concurrency
    )