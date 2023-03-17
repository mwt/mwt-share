import sys
import string
import secrets
from pathlib import Path
from mimetypes import guess_extension
from flask import (
    Flask,
    abort,
    redirect,
    request,
    send_from_directory,
    url_for,
)
from magic import Magic

# Init app
app = Flask(
    __name__,
    instance_relative_config=True,
    static_folder="public_html",
    static_url_path="",
)

# Import configuation
app.config.update(
    UPLOAD_FOLDER="public_html",
    FHOST_EXT_OVERRIDE={
        "audio/flac": ".flac",
        "image/gif": ".gif",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/svg+xml": ".svg",
        "video/webm": ".webm",
        "video/x-matroska": ".mkv",
        "application/octet-stream": ".bin",
        "text/plain": ".txt",
        "text/x-diff": ".diff",
    },
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    FILE_DIR="f",
    REDR_DIR="l",
)
app.config.from_pyfile("config.py")

# Make folders if they don't exist
Path(app.config["UPLOAD_FOLDER"], app.config["FILE_DIR"]).mkdir(
    parents=True, exist_ok=True
)
Path(app.config["UPLOAD_FOLDER"], app.config["REDR_DIR"]).mkdir(
    parents=True, exist_ok=True
)

# Load magic to detect mime types
try:
    mimedetect = Magic(mime=True, mime_encoding=False)
except NameError:
    print(
        "Error: You have installed the wrong version of the 'magic' module. "
        + "Please install python-magic."
    )
    sys.exit(1)


def arbitrary_string(length: int) -> str:
    """
    Generate a random alphanumeric string of fixed length
    """
    alphabet = string.ascii_letters + string.digits
    password = "".join(secrets.choice(alphabet) for i in range(length))
    return password


def store_file(file):
    """
    Store a file in the uploads folder and return the filename
    """
    data = file.read()

    # Use magic to detect mime type
    mimeGuess = mimedetect.from_buffer(data)
    app.logger.debug(
        f"MIME - specified: '{file.content_type}' - detected: '{mimeGuess}'"
    )

    # Guess extension from mime type
    extGuess = guess_extension(mimeGuess)

    # Override extension if needed
    if mimeGuess in app.config["FHOST_EXT_OVERRIDE"]:
        ext = app.config["FHOST_EXT_OVERRIDE"][mimeGuess]
    elif extGuess:
        ext = extGuess
    else:
        ext = ".bin"

    app.logger.debug(f"Extension - detected: '{extGuess}' - using: '{ext}'")

    # We try arbitrary filenames until we find one that doesn't exist
    # Realistically, this loop should only run once
    while True:
        # Generate a random filename
        filenameString = arbitrary_string(16)

        # Iterate characters until we find a filename that doesn't exist
        fileName = ext
        for char in filenameString:
            fileName = char + fileName
            filePath = Path(
                app.config["UPLOAD_FOLDER"], app.config["FILE_DIR"], fileName
            )
            # If the file doesn't exist, we can use it
            if not filePath.is_file():
                with open(filePath, "wb") as f:
                    f.write(data)
                return fileName


@app.route("/", methods=["POST"])
def fhost():
    if request.method == "POST":
        if "file" in request.files:
            file = request.files["file"]
            filename = store_file(file)
            return url_for(".get", path=filename, _external=True)
        elif "url" in request.form:
            url = request.form["url"]
            return url
        elif "shorten" in request.form:
            shorten = request.form["shorten"]
            return shorten
        else:
            abort(400, "No file or url provided")
    else:
        abort(405, "Only POST requests are allowed")


# Should be handled by apache/liteSpeed
@app.route(f"/{app.config['FILE_DIR']}/<path:path>", methods=["GET"])
def get(path):
    if request.method == "GET":
        return send_from_directory(
            Path(app.config["UPLOAD_FOLDER"], app.config["FILE_DIR"]), path
        )
    else:
        abort(405, "Only GET requests are allowed")
