from flask_cors import CORS

import io

import os

import subprocess

import tempfile

import ipaddress

import socket

import http.client

import ssl

import threading

from urllib.parse import urlsplit



from flask import Flask, jsonify, request

from PIL import Image, UnidentifiedImageError

from transformers import pipeline

from transformers.pipelines.audio_utils import ffmpeg_read





app = Flask(__name__)



CORS(
    app,
    resources={
        r"/detect/*": {
            "origins": [
                "http://127.0.0.1:5500",
                "http://localhost:5500",
            ]
        }
    }
)



# Maximum upload size: 25 MB

MAX_BYTES = 25 * 1024 * 1024

app.config["MAX_CONTENT_LENGTH"] = MAX_BYTES

app.config["MAX_FORM_MEMORY_SIZE"] = 1024 * 1024



AI_THRESHOLD = 0.5

MAX_AUDIO_SECONDS = 30

MIN_WORDS = 40

CHUNK_WORDS = 250



# Allow only one AI analysis at a time on our small EC2 server.

analysis_lock = threading.Lock()



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



Image.MAX_IMAGE_PIXELS = 25_000_000





# -----------------------------------------

# Load Models

# -----------------------------------------



print("Loading models...", flush=True)



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



print("Models ready.", flush=True)





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

    ai_prob = max(0.0, min(1.0, float(ai_prob)))



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

    ai_prob = ai_probability_from_scores(predictions)



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

            "-threads", "1",

            "-ss", str(second),

            "-i", video_path,

            "-frames:v", "1",

            "-vf", "scale=640:640:force_original_aspect_ratio=decrease",

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



    if result["label"].strip().lower() in AI_LABELS:

        return result["score"]



    return 1 - result["score"]





def busy_response():

    return jsonify({

        "error": "The AI detector is busy. Please try again shortly."

    }), 503





# -----------------------------------------

# Text Detection

# -----------------------------------------



@app.route("/detect", methods=["POST"])

@app.route("/detect/text", methods=["POST"])

def detect_text():

    data = request.get_json(silent=True) or {}

    value = data.get("text", "")



    if not isinstance(value, str):

        return jsonify({"error": "Text must be a string."}), 400



    value = value.strip()



    if len(value) > 20000:

        return jsonify({"error": "Text is too long."}), 413



    count = len(value.split())



    if count < MIN_WORDS:

        return jsonify({

            "error": f"Please provide at least {MIN_WORDS} words (got {count})."

        }), 400



    if not analysis_lock.acquire(blocking=False):

        return busy_response()



    try:

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

    finally:

        analysis_lock.release()





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



    if not analysis_lock.acquire(blocking=False):

        return busy_response()



    try:

        with Image.open(file.stream) as image:

            image.load()

            return analyze_image(image)



    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):

        return jsonify({

            "error": "Could not read that file as an image."

        }), 400



    finally:

        analysis_lock.release()





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



    if not analysis_lock.acquire(blocking=False):

        return busy_response()



    try:

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



        return build_response(

            "audio",

            ai_probability_from_scores(predictions),

            duration_seconds=round(duration, 1),

            analyzed_seconds=round(min(duration, MAX_AUDIO_SECONDS), 1)

        )



    finally:

        analysis_lock.release()





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



    if not analysis_lock.acquire(blocking=False):

        return busy_response()



    video_path = None



    try:

        with tempfile.NamedTemporaryFile(

            suffix=extension,

            delete=False

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



        analysis_lock.release()





# -----------------------------------------

# Secure Direct Media Link Download

# -----------------------------------------



def validate_public_url(url):

    if not isinstance(url, str) or len(url) > 2048:

        raise ValueError("Invalid URL.")



    parts = urlsplit(url)



    if parts.scheme not in ("http", "https"):

        raise ValueError("Only HTTP and HTTPS links are supported.")



    if not parts.hostname or parts.username or parts.password:

        raise ValueError("Invalid or unsupported URL.")



    try:

        port = parts.port

    except ValueError:

        raise ValueError("Invalid URL port.")



    if port not in (None, 80, 443):

        raise ValueError("Custom URL ports are not supported.")



    if parts.scheme == "http" and port not in (None, 80):

        raise ValueError("HTTP links must use port 80.")



    if parts.scheme == "https" and port not in (None, 443):

        raise ValueError("HTTPS links must use port 443.")



    hostname = parts.hostname



    if hostname.endswith("."):

        hostname = hostname[:-1]



    try:

        addresses = socket.getaddrinfo(

            hostname,

            port or (443 if parts.scheme == "https" else 80),

            type=socket.SOCK_STREAM

        )

    except socket.gaierror:

        raise ValueError("Could not resolve the URL hostname.")



    public_addresses = []



    for entry in addresses:

        address = ipaddress.ip_address(entry[4][0])



        if not address.is_global:

            raise ValueError(

                "Private or local network URLs are not allowed."

            )



        public_addresses.append(str(address))



    if not public_addresses:

        raise ValueError("No public IP address found.")



    return parts, hostname, public_addresses[0]





class PinnedHTTPConnection(http.client.HTTPConnection):

    def __init__(self, hostname, pinned_ip, port=80, timeout=20):

        super().__init__(hostname, port=port, timeout=timeout)

        self.pinned_ip = pinned_ip



    def connect(self):

        self.sock = socket.create_connection(

            (self.pinned_ip, self.port),

            timeout=self.timeout

        )





class PinnedHTTPSConnection(http.client.HTTPSConnection):

    def __init__(self, hostname, pinned_ip, port=443, timeout=20):

        super().__init__(

            hostname,

            port=port,

            timeout=timeout,

            context=ssl.create_default_context()

        )

        self.pinned_ip = pinned_ip



    def connect(self):

        raw_socket = socket.create_connection(

            (self.pinned_ip, self.port),

            timeout=self.timeout

        )



        try:

            self.sock = self._context.wrap_socket(

                raw_socket,

                server_hostname=self.host

            )

        except Exception:

            raw_socket.close()

            raise





def download_public_media(url):

    parts, hostname, pinned_ip = validate_public_url(url)



    if parts.scheme == "https":

        connection = PinnedHTTPSConnection(

            hostname, pinned_ip, timeout=20

        )

    else:

        connection = PinnedHTTPConnection(

            hostname, pinned_ip, timeout=20

        )



    temporary_path = None



    try:

        path = parts.path or "/"



        if parts.query:

            path += "?" + parts.query



        host_header = hostname



        if ":" in hostname:

            host_header = f"[{hostname}]"



        connection.request(

            "GET",

            path,

            headers={

                "Host": host_header,

                "User-Agent": "AmI-AI-Detector/1.0",

                "Accept": "image/*, video/*",

                "Connection": "close"

            }

        )



        response = connection.getresponse()



        if 300 <= response.status < 400:

            raise ValueError(

                "Redirecting links are not supported."

            )



        if response.status != 200:

            raise ValueError(

                f"Media download failed (HTTP {response.status})."

            )



        content_type = response.getheader(

            "Content-Type", ""

        ).split(";")[0].lower().strip()



        is_image = content_type.startswith("image/")

        is_video = content_type.startswith("video/")



        if not is_image and not is_video:

            raise ValueError(

                "This link does not point directly to an image or video."

            )



        content_length = response.getheader("Content-Length")



        if content_length:

            try:

                if int(content_length) > MAX_BYTES:

                    raise ValueError(

                        "Linked media exceeds the 25 MB limit."

                    )

            except ValueError as error:

                if "exceeds" in str(error):

                    raise

                raise ValueError("Invalid media content length.")



        extension = os.path.splitext(parts.path)[1].lower()



        if is_video:

            suffix = (

                extension if extension in VIDEO_EXTENSIONS

                else ".mp4"

            )

        else:

            suffix = (

                extension if extension in IMAGE_EXTENSIONS

                else ".jpg"

            )



        with tempfile.NamedTemporaryFile(

            suffix=suffix,

            delete=False

        ) as temporary:

            temporary_path = temporary.name

            downloaded = 0



            while True:

                chunk = response.read(65536)



                if not chunk:

                    break



                downloaded += len(chunk)



                if downloaded > MAX_BYTES:

                    raise ValueError(

                        "Linked media exceeds the 25 MB limit."

                    )



                temporary.write(chunk)



        return temporary_path, is_image



    except Exception:

        if temporary_path and os.path.exists(temporary_path):

            os.remove(temporary_path)

        raise



    finally:

        connection.close()





# -----------------------------------------

# Link Detection

# -----------------------------------------



@app.route("/detect/link", methods=["POST"])

def detect_link():

    data = request.get_json(silent=True) or {}

    url = data.get("url", "")



    if not url:

        return jsonify({

            "error": "Please provide a URL."

        }), 400



    if not analysis_lock.acquire(blocking=False):

        return busy_response()



    media_path = None



    try:

        media_path, is_image = download_public_media(url)



        if is_image:

            try:

                with Image.open(media_path) as image:

                    image.load()

                    return analyze_image(image)

            except (

                UnidentifiedImageError,

                OSError,

                ValueError,

                Image.DecompressionBombError

            ):

                return jsonify({

                    "error": "The linked file is not a readable image."

                }), 400



        return analyze_video_path(media_path)



    except ValueError as error:

        return jsonify({"error": str(error)}), 400



    except (OSError, http.client.HTTPException) as error:

        print("LINK DOWNLOAD ERROR:", repr(error), flush=True)

        return jsonify({

            "error": "Could not download media from that URL."

        }), 400



    except (FileNotFoundError, subprocess.TimeoutExpired) as error:

        print("LINK VIDEO ERROR:", repr(error), flush=True)

        return jsonify({

            "error": "Could not process the linked video."

        }), 500



    except Exception as error:

        print("LINK ERROR:", repr(error), flush=True)

        return jsonify({

            "error": "Link analysis failed."

        }), 500



    finally:

        if media_path and os.path.exists(media_path):

            os.remove(media_path)



        analysis_lock.release()





# -----------------------------------------

# Health Check

# -----------------------------------------



@app.route("/health", methods=["GET"])

def health():

    return jsonify({"status": "ok"})





# -----------------------------------------

# Development Server

# -----------------------------------------



if __name__ == "__main__":

    app.run(

        host="127.0.0.1",

        port=5000,

        debug=False

    )
