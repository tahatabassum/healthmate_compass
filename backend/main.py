"""
Entry point for HealthMate Compass backend server.
Works everywhere: Render, Railway, Docker, Localhost.
Automatically handles PYTHONPATH and dynamic PORT.
"""
import os
import sys

# Ensure backend root directory is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import uvicorn
from app.main import app

if __name__ == "__main__":
    port_str = os.environ.get("PORT", "10000")
    try:
        port = int(port_str)
    except ValueError:
        port = 10000
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Starting HealthMate Compass API server on {host}:{port}...")
    uvicorn.run("app.main:app", host=host, port=port, log_level="info")
