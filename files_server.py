from flask import Flask, send_from_directory, abort
import os

app = Flask(__name__)

# Directory where your files are stored
MEDIA_DIR = "media_files"

# Ensure the directory exists
os.makedirs(MEDIA_DIR, exist_ok=True)

@app.route('/media_files/<path:filename>', methods=['GET'])
def serve_media(filename):
    """Serve media files."""
    try:
        # Serve the file from the media directory
        return send_from_directory(MEDIA_DIR, filename)
    except FileNotFoundError:
        # If the file doesn't exist, return a 404 error
        abort(404)

@app.route('/')
def home():
    return "Media server is running. Use /media_files/<filename> to access files."

if __name__ == "__main__":
    # Run the server on localhost:8000
    app.run(host="0.0.0.0", port=8000)
