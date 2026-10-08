
import io
import os
import subprocess
import tempfile
import ipaddress
import socket
from urllib.parse import urlsplit

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from PIL import Image, UnidentifiedImageError
from transformers import pipeline
from transformers.pipelines.audio_utils import ffmpeg_read

app = Flask(__name__)
CORS(app)

MAX_BYTES = 25 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_BYTES

AI_THRESHOLD = 0.5
MAX_AUDIO_SECONDS = 30
MIN_WORDS = 40
CHUNK_WORDS = 250

AI_LABELS = {
    "fake", "artificial", "ai", "ai-generated",
    "spoof", "deepfake"
}

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".webm", ".mkv", ".avi"
}

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"
}

# -----------------------------------------
# Load Models
# -----------------------------------------

print("Loading models...")

text_detector = pipeline(
    "text-classification",
    model="openai-community/roberta-base-openai-detector",
    truncation=True,
    max_length=512
)

image_detector = pipeline(
    "image-classification",
    model="Organika/sdxl-detector"
)

audio_detector = pipeline(
    "audio-classification",
    model="MelodyMachine/Deepfake-audio-detection-V2"
)

print("Models ready.")


# -----------------------------------------
# Shared Helpers
# -----------------------------------------

def ai_probability_from_scores(results):
    return sum(
        item["score"]
        for item in results
        if item["label"].strip().lower() in AI_LABELS
    )


def build_response(kind, ai_prob, **extra):
    return jsonify({
        "type": kind,
        "ai_probability": round(ai_prob, 4),
        "human_probability": round(1 - ai_prob, 4),
        "label": "AI" if ai_prob >= AI_THRESHOLD else "Human",
        **extra
    })


def get_uploaded_file():
    file = request.files.get("file")
    if file is None or not file.filename:
        return None
    return file


def analyze_image(image):
    image = image.convert("RGB")
    predictions = image_detector(image, top_k=None)

    print("IMAGE MODEL RAW RESULTS:", predictions, flush=True)

    ai_prob = ai_probability_from_scores(predictions)

    print("IMAGE CALCULATED AI SCORE:", ai_prob, flush=True)

    return build_response(
        "image",
        ai_prob,
        width=image.width,
        height=image.height
    )


def analyze_video_path(video_path):
    scores = []

    for second in (1, 3, 5, 7, 9):
        command = [
            "ffmpeg",
            "-nostdin",
            "-v", "error",
            "-ss", str(second),
            "-i", video_path,
            "-frames:v", "1",
            "-f", "image2pipe",
            "-vcodec", "mjpeg",
            "pipe:1"
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            timeout=30,
            check=False
        )

        if result.returncode != 0 or not result.stdout:
            continue

        with Image.open(io.BytesIO(result.stdout)) as frame:
            image = frame.convert("RGB")

        predictions = image_detector(image, top_k=None)

        print(
            f"VIDEO FRAME {second}s RAW RESULTS:",
            predictions,
            flush=True
        )

        scores.append(ai_probability_from_scores(predictions))

    if not scores:
        return jsonify({
            "error": "Could not extract frames from the video."
        }), 400

    return build_response(
        "video",
        sum(scores) / len(scores),
        frames_analyzed=len(scores)
    )


def split_into_chunks(value, size=CHUNK_WORDS):
    words = value.split()
    return [
        " ".join(words[i:i + size])
        for i in range(0, len(words), size)
    ]


def text_ai_score(chunk):
    result = text_detector(chunk)[0]
    print("TEXT MODEL RAW RESULT:", result, flush=True)

    if result["label"].strip().lower() in AI_LABELS:
        return result["score"]

    return 1 - result["score"]


# -----------------------------------------
# Text Detection
# -----------------------------------------

@app.route("/detect", methods=["POST"])
@app.route("/detect/text", methods=["POST"])
def detect_text():
    data = request.get_json(silent=True) or {}
    value = (data.get("text") or "").strip()

    if not value:
        return jsonify({"error": "No text provided."}), 400

    count = len(value.split())

    if count < MIN_WORDS:
        return jsonify({
            "error": f"Please provide at least {MIN_WORDS} words (got {count})."
        }), 400

    chunks = split_into_chunks(value)
    weights = [len(chunk.split()) for chunk in chunks]
    scores = [text_ai_score(chunk) for chunk in chunks]

    ai_prob = sum(
        score * weight
        for score, weight in zip(scores, weights)
    ) / sum(weights)

    return build_response(
        "text",
        ai_prob,
        chunks=len(chunks),
        word_count=count
    )


# -----------------------------------------
# Image Detection
# -----------------------------------------

@app.route("/detect/image", methods=["POST"])
def detect_image():
    file = get_uploaded_file()

    if file is None:
        return jsonify({
            "error": "No image uploaded (use form field 'file')."
        }), 400

    try:
        with Image.open(file.stream) as image:
            return analyze_image(image)
    except (UnidentifiedImageError, OSError, ValueError):
        return jsonify({
            "error": "Could not read that file as an image."
        }), 400


# -----------------------------------------
# Audio Detection
# -----------------------------------------

@app.route("/detect/audio", methods=["POST"])
def detect_audio():
    file = get_uploaded_file()

    if file is None:
        return jsonify({
            "error": "No audio uploaded (use form field 'file')."
        }), 400

    sampling_rate = audio_detector.feature_extractor.sampling_rate

    try:
        audio = ffmpeg_read(file.read(), sampling_rate)
    except Exception as error:
        print("AUDIO ERROR:", repr(error), flush=True)
        return jsonify({
            "error": "Could not decode the audio file."
        }), 400

    if len(audio) < sampling_rate:
        return jsonify({
            "error": "Audio is too short (need at least 1 second)."
        }), 400

    duration = len(audio) / sampling_rate
    audio = audio[:sampling_rate * MAX_AUDIO_SECONDS]

    predictions = audio_detector(
        {"raw": audio, "sampling_rate": sampling_rate},
        top_k=None
    )

    print("AUDIO MODEL RAW RESULTS:", predictions, flush=True)

    return build_response(
        "audio",
        ai_probability_from_scores(predictions),
        duration_seconds=round(duration, 1),
        analyzed_seconds=round(min(duration, MAX_AUDIO_SECONDS), 1)
    )


# -----------------------------------------
# Video Detection
# -----------------------------------------

@app.route("/detect/video", methods=["POST"])
def detect_video():
    file = get_uploaded_file()

    if file is None:
        return jsonify({
            "error": "No video uploaded (use form field 'file')."
        }), 400

    extension = os.path.splitext(file.filename)[1].lower()

    if extension not in VIDEO_EXTENSIONS:
        return jsonify({
            "error": "Unsupported video file extension."
        }), 400

    video_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=extension, delete=False
        ) as temporary:
            video_path = temporary.name
            file.save(temporary)

        return analyze_video_path(video_path)

    except FileNotFoundError:
        return jsonify({
            "error": "FFmpeg was not found by the Flask server."
        }), 500

    except subprocess.TimeoutExpired:
        return jsonify({
            "error": "Video frame extraction timed out."
        }), 500

    except Exception as error:
        print("VIDEO ERROR:", repr(error), flush=True)
        return jsonify({"error": "Video analysis failed."}), 500

    finally:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)


# -----------------------------------------
# Link Detection
# -----------------------------------------

def validate_public_url(url):
    """Reject local/private destinations and unsupported URLs."""
    parts = urlsplit(url)

    if parts.scheme not in ("http", "https"):
        raise ValueError("Only HTTP and HTTPS links are supported.")

    if not parts.hostname or parts.username or parts.password:
        raise ValueError("Invalid or unsupported URL.")

    if parts.port not in (None, 80, 443):
        raise ValueError("Custom URL ports are not supported.")

    # Resolve DNS and reject private, loopback and reserved IPs.
    try:
        addresses = socket.getaddrinfo(
            parts.hostname,
            parts.port or (443 if parts.scheme == "https" else 80),
            type=socket.SOCK_STREAM
        )
    except socket.gaierror:
        raise ValueError("Could not resolve the URL hostname.")

    for entry in addresses:
        address = ipaddress.ip_address(entry[4][0])
        if not address.is_global:
            raise ValueError("Private or local network URLs are not allowed.")


@app.route("/detect/link", methods=["POST"])
def detect_link():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({"error": "Please provide a URL."}), 400

    try:
        validate_public_url(url)
    except (ValueError, OverflowError) as error:
        return jsonify({"error": str(error)}), 400

    response = None
    video_path = None

    try:
        # Do not follow redirects. They could point to local services.
        response = requests.get(
            url,
            stream=True,
            timeout=(5, 20),
            allow_redirects=False,
            headers={"User-Agent": "AmI-AI-Detector/1.0"}
        )

        if 300 <= response.status_code < 400:
            return jsonify({
                "error": "Redirecting links are not supported yet."
            }), 400

        response.raise_for_status()

        content_type = response.headers.get(
            "Content-Type", ""
        ).split(";")[0].lower().strip()

        content_length = response.headers.get("Content-Length")

        if content_length:
            if int(content_length) > MAX_BYTES:
                return jsonify({
                    "error": "Linked media exceeds the 25 MB limit."
                }), 413

        extension = os.path.splitext(
            urlsplit(url).path
        )[1].lower()

        is_image = content_type.startswith("image/")
        is_video = content_type.startswith("video/")

        if not is_image and not is_video:
            return jsonify({
                "error": (
                    "This link does not point directly to an image "
                    "or video. Webpage links are not supported yet."
                )
            }), 400

        downloaded = 0

        # Stream into a temporary file rather than keeping a large
        # download in memory.
        suffix = extension if extension in (
            IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
        ) else (".mp4" if is_video else ".jpg")

        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False
        ) as temporary:
            video_path = temporary.name

            for chunk in response.iter_content(chunk_size=65536):
                if not chunk:
                    continue

                downloaded += len(chunk)

                if downloaded > MAX_BYTES:
                    return jsonify({
                        "error": "Linked media exceeds the 25 MB limit."
                    }), 413

                temporary.write(chunk)

        if is_image:
            try:
                with Image.open(video_path) as image:
                    return analyze_image(image)
            except (UnidentifiedImageError, OSError, ValueError):
                return jsonify({
                    "error": "The linked file is not a readable image."
                }), 400

        return analyze_video_path(video_path)

    except requests.RequestException as error:
        print("LINK DOWNLOAD ERROR:", repr(error), flush=True)
        return jsonify({
            "error": "Could not download media from that URL."
        }), 400

    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        print("LINK VIDEO ERROR:", repr(error), flush=True)
        return jsonify({
            "error": "Could not process the linked video with FFmpeg."
        }), 500

    except Exception as error:
        print("LINK ERROR:", repr(error), flush=True)
        return jsonify({
            "error": "Link analysis failed."
        }), 500

    finally:
        if response is not None:
            response.close()

        if video_path and os.path.exists(video_path):
            os.remove(video_path)


# -----------------------------------------
# Health Check
# -----------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


# -----------------------------------------
# Start Server
# -----------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
