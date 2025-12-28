"""
Run the Flask server

This script initializes and runs the Flask development server.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add the parent directory to Python path
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

# Load environment variables
load_dotenv()

# Import the app after setting up the path
from api.app import app

if __name__ == "__main__":
    # Get configuration from environment variables
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    
    # Run the Flask development server
    print(f"Starting server on http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)