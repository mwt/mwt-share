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
FILE_DIR_PATH = Path(app.config["UPLOAD_FOLDER"], app.config["FILE_DIR"])
FILE_DIR_PATH.mkdir(parents=True, exist_ok=True)

REDR_DIR_PATH = Path(app.config["UPLOAD_FOLDER"], app.config["REDR_DIR"])
REDR_DIR_PATH.mkdir(parents=True, exist_ok=True)

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


def short_unique_name(dir, ext="", max_length=16):
    """
    Generate a short unique name for a file/dir in a directory
    """
    # We try arbitrary filenames until we find one that doesn't exist
    # Realistically, this loop should only run once
    while True:
        # Generate a random filename
        filename_string = arbitrary_string(max_length)

        # Iterate characters until we find a filename that doesn't exist
        node_name = ext
        for char in filename_string:
            node_name = char + node_name
            node_path = Path(dir, node_name)
            # If the file/dir doesn't exist, we can use it
            if not node_path.exists():
                return node_name, node_path


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

    # Generate an unused random filename
    file_name, file_path = short_unique_name(FILE_DIR_PATH, ext=ext)

    with open(file_path, "wb") as f:
        f.write(data)
    return file_name


def shorten_url(url: str):
    """
    Shorten a url and return the shortened url
    """
    # Generate an unused random directory name
    folder_name, folder_path = short_unique_name(REDR_DIR_PATH)
    folder_path.mkdir(exist_ok=False)

    # Make an .htaccess file to redirect to the url
    redirect_content = f"RewriteEngine on\nRewriteRule ^(.*)$ {url} [R=307,L]"

    # Write the .htaccess file
    with open(Path(folder_path, ".htaccess"), "w", encoding="utf8") as f:
        f.write(redirect_content)
    return folder_name


@app.route("/", methods=["POST"])
def fhost():
    if request.method == "POST":
        if "file" in request.files:
            file = request.files["file"]
            filename = store_file(file)
            return url_for(".get_file", path=filename, _external=True)
        elif "url" in request.form:
            url = request.form["url"]
            return url
        elif "shorten" in request.form:
            url = request.form["shorten"]
            foldername = shorten_url(url)
            return url_for(".get_redr", path=foldername, _external=True)
        else:
            abort(400, "No file or url provided")
    else:
        abort(405, "Only POST requests are allowed")


# Should be handled by apache/liteSpeed
@app.route(f"/{app.config['FILE_DIR']}/<path:path>", methods=["GET"])
def get_file(path):
    if request.method == "GET":
        return send_from_directory(FILE_DIR_PATH, path)
    else:
        abort(405, "Only GET requests are allowed")


# Should be handled by apache/liteSpeed
@app.route(f"/{app.config['REDR_DIR']}/<path:path>", methods=["GET"])
def get_redr(path):
    if request.method == "GET":
        # Read the .htaccess file and redirect to the url
        with open(
            Path(
                app.config["UPLOAD_FOLDER"], app.config["REDR_DIR"], path, ".htaccess"
            ),
            "r",
            encoding="utf8",
        ) as f:
            # This is a silly hack to get the url
            # Obviously, I should use re, but don't feel like loading it
            return redirect(f.read()[36:-10], code=307)
    else:
        abort(405, "Only GET requests are allowed")
