import uvicorn
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=True  # Auto-reload on file changes (like Flask's debug mode)
    )