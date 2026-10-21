"""
Basic AI detection API: text, images, and audio.

Setup:
    pip install flask flask-cors transformers torch pillow numpy
    # Audio decoding also needs ffmpeg installed on your system:
    #   macOS:   brew install ffmpeg
    #   Ubuntu:  sudo apt install ffmpeg
    #   Windows: winget install ffmpeg

Run:
    python app.py

Endpoints (all return JSON with ai_probability, human_probability, label):
    POST /detect/text    JSON body: {"text": "..."}
    POST /detect/image   multipart form, file field name: "file"
    POST /detect/audio   multipart form, file field name: "file"
    POST /detect         alias for /detect/text (backwards compatible)
    GET  /health
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from transformers import pipeline
from transformers.pipelines.audio_utils import ffmpeg_read
from PIL import Image, UnidentifiedImageError

app = Flask(__name__)
CORS(app)  # lets your frontend call this from a different origin/port
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB upload limit

AI_THRESHOLD = 0.5

# Labels (lowercased) that the models use to mean "AI-generated"
AI_LABELS = {"fake", "artificial", "ai", "ai-generated", "spoof", "deepfake"}

# ---------------------------------------------------------------------------
# Models (each downloads on first run and is loaded once at startup)
# Swap any model name below for a newer detector from Hugging Face if you like.
# ---------------------------------------------------------------------------
print("Loading models...")

text_detector = pipeline(
    "text-classification",
    model="openai-community/roberta-base-openai-detector",
    truncation=True,
    max_length=512,
)

image_detector = pipeline(
    "image-classification",
    model="Organika/sdxl-detector",
)

audio_detector = pipeline(
    "audio-classification",
    model="MelodyMachine/Deepfake-audio-detection-V2",
)

print("Models ready.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def build_response(kind, ai_prob, **extra):
    return jsonify({
        "type": kind,
        "ai_probability": round(ai_prob, 4),
        "human_probability": round(1 - ai_prob, 4),
        "label": "AI" if ai_prob >= AI_THRESHOLD else "Human",
        **extra,
    })


def ai_probability_from_scores(results):
    """results: list of {"label": str, "score": float} covering all classes."""
    return sum(r["score"] for r in results if r["label"].lower() in AI_LABELS)


def get_uploaded_file():
    f = request.files.get("file")
    if f is None or f.filename == "":
        return None
    return f


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------
MIN_WORDS = 40       # very short text is unreliable
CHUNK_WORDS = 250    # keeps each chunk under the 512-token limit


def split_into_chunks(text, size=CHUNK_WORDS):
    words = text.split()
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size)]


def text_ai_score(chunk):
    result = text_detector(chunk)[0]
    score = result["score"]
    return score if result["label"].lower() in AI_LABELS else 1 - score


@app.route("/detect", methods=["POST"])
@app.route("/detect/text", methods=["POST"])
def detect_text():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({"error": "No text provided."}), 400

    word_count = len(text.split())
    if word_count < MIN_WORDS:
        return jsonify({
            "error": f"Please provide at least {MIN_WORDS} words (got {word_count})."
        }), 400

    chunks = split_into_chunks(text)
    # Weight chunks by length so a tiny last chunk doesn't skew the result
    weights = [len(c.split()) for c in chunks]
    scores = [text_ai_score(c) for c in chunks]
    ai_prob = sum(s * w for s, w in zip(scores, weights)) / sum(weights)

    return build_response("text", ai_prob, chunks=len(chunks), word_count=word_count)


# ---------------------------------------------------------------------------
# Image
# ---------------------------------------------------------------------------
@app.route("/detect/image", methods=["POST"])
def detect_image():
    f = get_uploaded_file()
    if f is None:
        return jsonify({"error": "No image uploaded (use form field 'file')."}), 400

    try:
        image = Image.open(f.stream).convert("RGB")
    except (UnidentifiedImageError, OSError):
        return jsonify({"error": "Could not read that file as an image."}), 400

    results = image_detector(image, top_k=None)
    ai_prob = ai_probability_from_scores(results)

    return build_response("image", ai_prob, width=image.width, height=image.height)


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------
MAX_AUDIO_SECONDS = 30  # only the first 30s is analyzed to keep things fast


@app.route("/detect/audio", methods=["POST"])
def detect_audio():
    f = get_uploaded_file()
    if f is None:
        return jsonify({"error": "No audio uploaded (use form field 'file')."}), 400

    sampling_rate = audio_detector.feature_extractor.sampling_rate

    try:
        # Decodes mp3/wav/m4a/ogg/flac etc. into a float array (needs ffmpeg)
        audio = ffmpeg_read(f.read(), sampling_rate)
    except Exception:
        return jsonify({
            "error": "Could not decode that audio file. Check the format and that ffmpeg is installed."
        }), 400

    if len(audio) < sampling_rate:  # under 1 second
        return jsonify({"error": "Audio is too short (need at least 1 second)."}), 400

    duration = len(audio) / sampling_rate
    audio = audio[: sampling_rate * MAX_AUDIO_SECONDS]

    results = audio_detector(
        {"raw": audio, "sampling_rate": sampling_rate}, top_k=None
    )
    ai_prob = ai_probability_from_scores(results)

    return build_response(
        "audio",
        ai_prob,
        duration_seconds=round(duration, 1),
        analyzed_seconds=round(min(duration, MAX_AUDIO_SECONDS), 1),
    )

# ---------------------------------------------------------------------------
# Video
# ---------------------------------------------------------------------------
MAX_VIDEO_FRAMES = 16 # frames sampled per video (more = slower but steadier)
MIN_VIDEO_FRAMES_OK = 3 # need at least this many readable frames
VIDEO_AUDIO_WEIGHT = 0.25 # share of the final score given to the audio track
 
 
def probe_video(path):
"""Returns (duration_seconds, has_audio). Raises on failure."""
out = subprocess.run(
["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
"-of", "json", path],
capture_output=True, check=True, timeout=30,
)
info = json.loads(out.stdout)
duration = float(info.get("format", {}).get("duration", 0) or 0)
kinds = {s.get("codec_type") for s in info.get("streams", [])}
if "video" not in kinds:
raise ValueError("no video stream")
return duration, "audio" in kinds
 
 
def extract_frame(path, timestamp):
"""Grabs one frame at `timestamp` seconds as a PIL image (or None)."""
proc = subprocess.run(
["ffmpeg", "-v", "error", "-ss", f"{timestamp:.3f}", "-i", path,
"-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
capture_output=True, timeout=30,
)
if proc.returncode != 0 or not proc.stdout:
return None
try:
return Image.open(io.BytesIO(proc.stdout)).convert("RGB")
except (UnidentifiedImageError, OSError):
return None
 
 
@app.route("/detect/video", methods=["POST"])
def detect_video():
f = get_uploaded_file()
if f is None:
return jsonify({"error": "No video uploaded (use form field 'file')."}), 400
 
suffix = os.path.splitext(f.filename)[1] or ".mp4"
tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
try:
f.save(tmp)
tmp.close()
 
try:
duration, has_audio = probe_video(tmp.name)
except FileNotFoundError:
return jsonify({"error": "ffmpeg/ffprobe is not installed on the server."}), 500
except Exception:
return jsonify({"error": "Could not read that file as a video."}), 400
 
if duration <= 0:
return jsonify({"error": "Could not determine video length."}), 400
 
# Evenly spaced timestamps, avoiding the very first/last instant
n = MAX_VIDEO_FRAMES
timestamps = [duration * (i + 0.5) / n for i in range(n)]
 
frame_scores = []
for t in timestamps:
frame = extract_frame(tmp.name, t)
if frame is None:
continue
results = image_detector(frame, top_k=None)
frame_scores.append(ai_probability_from_scores(results))
 
if len(frame_scores) < MIN_VIDEO_FRAMES_OK:
return jsonify({"error": "Could not extract enough frames from that video."}), 400
 
visual_prob = sum(frame_scores) / len(frame_scores)
ai_prob = visual_prob
audio_prob = None
 
if has_audio:
try:
sampling_rate = audio_detector.feature_extractor.sampling_rate
with open(tmp.name, "rb") as vf:
audio = ffmpeg_read(vf.read(), sampling_rate)
if len(audio) >= sampling_rate:
audio = audio[: sampling_rate * MAX_AUDIO_SECONDS]
audio_results = audio_detector(
{"raw": audio, "sampling_rate": sampling_rate}, top_k=None
)
audio_prob = ai_probability_from_scores(audio_results)
ai_prob = (
(1 - VIDEO_AUDIO_WEIGHT) * visual_prob
+ VIDEO_AUDIO_WEIGHT * audio_prob
)
except Exception:
audio_prob = None # audio is a bonus signal; ignore failures
 
return build_response(
"video",
ai_prob,
duration_seconds=round(duration, 1),
frames_analyzed=len(frame_scores),
visual_ai_probability=round(visual_prob, 4),
audio_ai_probability=None if audio_prob is None else round(audio_prob, 4),
frame_scores=[round(s, 4) for s in frame_scores],
)
finally:
try:
os.unlink(tmp.name)
except OSError:
pass
 
 
@app.route("/health", methods=["GET"])
def health():
return jsonify({"status": "ok"})
 
 
if __name__ == "__main__":
app.run(host="0.0.0.0", port=5000, debug=False)

