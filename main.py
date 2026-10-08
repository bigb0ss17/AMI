from PIL import Image
from io import BytesIO
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import uuid
from pydantic import BaseModel

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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    
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

@app.post("/upload-video")
async def upload_video(file: UploadFile = File(...)):

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

@app.post("/upload-audio")
async def upload_audio(file: UploadFile = File(...)):

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
# Link analysis
# -----------------------------

@app.post("/analyze-link")
async def analyze_link(link: LinkRequest):

    logger.info(
        f"Link submitted: {link.url}"
    )

    return {
        "message": "Link received",
        "url": link.url,
        "status": "analysis_complete"
    }
    
# -----------------------------
# Serve the website
# -----------------------------

app.mount("/", StaticFiles(directory=".", html=True), name="static")