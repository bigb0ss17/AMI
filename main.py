import os
import logging
import uuid
from io import BytesIO

import requests
from PIL import Image
from pydantic import BaseModel
from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    Header,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# -----------------------------
# CAPTCHA verification
# -----------------------------

RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")

if not RECAPTCHA_SECRET_KEY:
    raise RuntimeError(
        "Missing RECAPTCHA_SECRET_KEY environment variable."
    )


def verify_recaptcha(token: str) -> bool:
    if not token:
        return False

    try:
        response = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={
                "secret": RECAPTCHA_SECRET_KEY,
                "response": token,
            },
            timeout=10,
        )

        response.raise_for_status()
        result = response.json()

        return result.get("success", False) is True

    except (requests.RequestException, ValueError) as error:
        logger.error("reCAPTCHA verification failed: %s", error)
        return False

app = FastAPI()


# -----------------------------
# Logging
# -----------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# -----------------------------
# CORS
# -----------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Recaptcha-Token"],
)


# -----------------------------
# Test endpoint
# -----------------------------

@app.get("/test")
def test():
    logger.info("Test endpoint was accessed")

    return {
        "message": "Hello from the backend!"
    }


# -----------------------------
# AI Analysis
# -----------------------------

def analyze_image(contents):
    """
    Analyze basic information about the uploaded image.
    """

    try:
        image = Image.open(BytesIO(contents))

        width, height = image.size
        image_format = image.format
        color_mode = image.mode

        logger.info(
            f"Image processed: "
            f"{width}x{height}, "
            f"format={image_format}, "
            f"mode={color_mode}"
        )

        return {
            "result": "Image processed successfully",
            "width": width,
            "height": height,
            "format": image_format,
            "color_mode": color_mode
        }

    except Exception as error:

        logger.error(
            f"Image processing failed: {error}"
        )

        raise HTTPException(
            status_code=400,
            detail="Unable to process the image."
        )

# -----------------------------
# Link request model
# -----------------------------

class LinkRequest(BaseModel):
    url: str
    
# -----------------------------
# Image upload
# -----------------------------


@app.post("/detect/image")
@app.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    captcha_token: str = Header(
        default="",
        alias="X-Recaptcha-Token"
    ),
):
    
    # Verify the CAPTCHA token
    if not verify_recaptcha(captcha_token):
        raise HTTPException(
            status_code=403,
            detail="Invalid reCAPTCHA verification."
        )

    analysis_id = str(uuid.uuid4())

    logger.info(
        f"Analysis started: {analysis_id}"
    )

    logger.info(
        f"Image upload received: {file.filename} "
        f"({file.content_type})"
    )

    # Allowed image types
    allowed_types = [
        "image/jpeg",
        "image/png",
        "image/webp"
    ]

    if file.content_type not in allowed_types:
        logger.warning(
            f"Rejected file: {file.filename} "
            f"({file.content_type})"
        )

        raise HTTPException(
            status_code=400,
            detail="Only JPG, PNG, and WEBP images are allowed."
        )

    # Read the file
    contents = await file.read()

    # Maximum file size: 10 MB
    max_size = 10 * 1024 * 1024

    if len(contents) > max_size:
        logger.warning(
            f"Rejected large file: {file.filename}"
        )

        raise HTTPException(
            status_code=400,
            detail="Image must be smaller than 10 MB."
        )

    logger.info(
        f"Image accepted successfully: {file.filename} "
        f"({len(contents)} bytes)"
    )

    # Analyze the image
    analysis = analyze_image(contents)

    logger.info(
        f"Image analysis completed: {file.filename}"
    )

    return {
        "analysis_id": analysis_id,
        "filename": file.filename,
        "message": "Image analyzed successfully!",
        "status": "analysis_complete",
        "analysis": analysis
    }

# -----------------------------
# Video upload
# -----------------------------

@app.post("/detect/video")
@app.post("/upload-video")
async def upload_video(
    file: UploadFile = File(...),
    captcha_token: str = Header(
        default="",
        alias="X-Recaptcha-Token"
    ),
):

    if not verify_recaptcha(captcha_token):
        raise HTTPException(
            status_code=403,
            detail="reCAPTCHA verification failed."
        )

    logger.info(
        f"Video upload received: {file.filename}"
    )

    allowed_types = [
        "video/mp4",
        "video/webm",
        "video/quicktime"
    ]

    if file.content_type not in allowed_types:

        logger.warning(
            f"Rejected video: {file.filename}"
        )

        raise HTTPException(
            status_code=400,
            detail="Only MP4, WEBM and MOV files are allowed."
        )

    contents = await file.read()

    max_size = 50 * 1024 * 1024

    if len(contents) > max_size:

        raise HTTPException(
            status_code=400,
            detail="Video must be smaller than 50 MB."
        )

    logger.info(
        f"Video accepted successfully: "
        f"{file.filename}"
    )

    return {
        "message": "Video uploaded successfully",
        "filename": file.filename,
        "size": len(contents),
        "status": "analysis_complete"
    }
    
# -----------------------------
# Audio upload
# -----------------------------

@app.post("/detect/audio")
@app.post("/upload-audio")
async def upload_audio(
    file: UploadFile = File(...),
    captcha_token: str = Header(
        default="",
        alias="X-Recaptcha-Token"
    ),
):

    if not verify_recaptcha(captcha_token):
        raise HTTPException(
            status_code=403,
            detail="reCAPTCHA verification failed."
        )

    logger.info(
        f"Audio upload received: {file.filename}"
    )

    allowed_types = [
        "audio/mpeg",
        "audio/wav",
        "audio/x-wav"
    ]

    if file.content_type not in allowed_types:

        logger.warning(
            f"Rejected audio: {file.filename}"
        )

        raise HTTPException(
            status_code=400,
            detail="Only MP3 and WAV files are allowed."
        )

    contents = await file.read()

    return {
        "message": "Audio uploaded successfully",
        "filename": file.filename,
        "size": len(contents),
        "status": "analysis_complete"
    }
    
# -----------------------------
# Text analysis endpoint
# -----------------------------

class TextRequest(BaseModel):
    text: str


@app.post("/detect/text")
async def detect_text(
    data: TextRequest,
    captcha_token: str = Header(
        default="",
        alias="X-Recaptcha-Token"
    ),
):
    if not verify_recaptcha(captcha_token):
        raise HTTPException(
            status_code=403,
            detail="reCAPTCHA verification failed."
        )

    text = data.text.strip()
    word_count = len(text.split())

    if word_count < 40:
        raise HTTPException(
            status_code=400,
            detail="Please provide at least 40 words."
        )

    raise HTTPException(
        status_code=501,
        detail=(
            "Text submission works, but an AI-text detection "
            "model has not been configured."
        )
    )

# -----------------------------
# Link analysis
# -----------------------------


@app.post("/detect/link")
@app.post("/upload-link")
async def upload_link(
    link: LinkRequest,
    captcha_token: str = Header(
        default="",
        alias="X-Recaptcha-Token"
    ),
):
    if not verify_recaptcha(captcha_token):
        raise HTTPException(
            status_code=403,
            detail="reCAPTCHA verification failed."
        )

    if link.url.split(":", 1)[0].lower() not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail="Only HTTP and HTTPS links are accepted."
        )

    logger.info("Link submitted: %s", link.url)

    return {
        "message": "Link received successfully.",
        "url": link.url,
        "status": "received",
    }
    
# -----------------------------
# Serve the website
# -----------------------------

app.mount("/", StaticFiles(directory=".", html=True), name="static")