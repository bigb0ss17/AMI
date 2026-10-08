
const imageButton = document.getElementById("imageButton");
const videoButton = document.getElementById("videoButton");
const audioButton = document.getElementById("audioButton");
const textButton = document.getElementById("textButton");

const imageInput = document.getElementById("imageInput");
const videoInput = document.getElementById("videoInput");
const audioInput = document.getElementById("audioInput");

const textSection = document.getElementById("textSection");
const textInput = document.getElementById("textInput");

const preview = document.getElementById("preview");
const analyzeButton = document.getElementById("analyzeButton");
const resultDiv = document.getElementById("result");

const linkButton = document.getElementById("linkButton");
const mediaURL = document.getElementById("mediaURL");

// Local Flask AI detection API
const AI_API = "http://127.0.0.1:5000";

// Currently selected media
let selectedFile = null;
let selectedType = null;
let cameraStream = null;

// -----------------------------------------
// Helper: Switch Media Type
// -----------------------------------------

function selectMedia(file, type) {
    selectedFile = file;
    selectedType = type;

    resultDiv.textContent = "";
    textSection.hidden = true;
}

// -----------------------------------------
// Helper: Display Detection Results
// -----------------------------------------

function displayResult(result) {
    const aiPercent =
        (result.ai_probability * 100).toFixed(2);

    const humanPercent =
        (result.human_probability * 100).toFixed(2);

    resultDiv.innerHTML = `
        <h2>Detection Result</h2>
        <p><strong>Media Type:</strong> ${result.type}</p>
        <p><strong>Prediction:</strong> ${result.label}</p>
        <p><strong>AI Detection Score:</strong> ${aiPercent}%</p>
        <p><strong>Human Detection Score:</strong> ${humanPercent}%</p>
    `;

    if (result.frames_analyzed !== undefined) {
        const frames = document.createElement("p");
        frames.textContent =
            `Video Frames Analyzed: ${result.frames_analyzed}`;

        resultDiv.appendChild(frames);
    }

    if (result.word_count !== undefined) {
        const words = document.createElement("p");
        words.textContent =
            `Words Analyzed: ${result.word_count}`;

        resultDiv.appendChild(words);
    }

    if (result.analyzed_seconds !== undefined) {
        const seconds = document.createElement("p");
        seconds.textContent =
            `Audio Seconds Analyzed: ${result.analyzed_seconds}`;

        resultDiv.appendChild(seconds);
    }
}

// -----------------------------------------
// Helper: Send Request to Flask
// -----------------------------------------

async function sendAnalysis(endpoint, options) {
    const response = await fetch(
        `${AI_API}${endpoint}`,
        options
    );

    const rawResponse = await response.text();

    let result;

    try {
        result = JSON.parse(rawResponse);
    } catch {
        throw new Error(
            `Server error (${response.status}). Check Flask terminal.`
        );
    }

    if (!response.ok) {
        throw new Error(
            result.error || `Analysis failed (${response.status}).`
        );
    }

    return result;
}

// -----------------------------------------
// Image Upload
// -----------------------------------------

imageButton.addEventListener("click", function () {
    imageInput.click();
});

imageInput.addEventListener("change", function () {
    const file = imageInput.files[0];

    if (!file) return;

    selectMedia(file, "image");

    const imageURL = URL.createObjectURL(file);

    preview.innerHTML = `
        <img src="${imageURL}" alt="Selected image">
    `;
});

// -----------------------------------------
// Video Upload
// -----------------------------------------

videoButton.addEventListener("click", function () {
    videoInput.click();
});

videoInput.addEventListener("change", function () {
    const file = videoInput.files[0];

    if (!file) return;

    selectMedia(file, "video");

    const videoURL = URL.createObjectURL(file);

    preview.innerHTML = `
        <video controls>
            <source src="${videoURL}" type="${file.type}">
            Your browser does not support video playback.
        </video>
    `;
});

// -----------------------------------------
// Audio Upload
// -----------------------------------------

audioButton.addEventListener("click", function () {
    audioInput.click();
});

audioInput.addEventListener("change", function () {
    const file = audioInput.files[0];

    if (!file) return;

    selectMedia(file, "audio");

    const audioURL = URL.createObjectURL(file);

    preview.innerHTML = `
        <audio controls>
            <source src="${audioURL}" type="${file.type}">
            Your browser does not support audio playback.
        </audio>
    `;
});

// -----------------------------------------
// Text AI Detection
// -----------------------------------------

textButton.addEventListener("click", function () {
    selectedFile = null;
    selectedType = "text";

    textSection.hidden = false;

    preview.innerHTML = `
        <p>
            Text selected. Paste your writing above,
            then click Analyze Media.
        </p>
    `;

    resultDiv.textContent = "";
    textInput.focus();
});

// -----------------------------------------
// Camera
// -----------------------------------------

const cameraButton = document.getElementById("cameraButton");
const cameraSection = document.getElementById("cameraSection");
const cameraPreview = document.getElementById("cameraPreview");

cameraButton.addEventListener("click", async function () {
    textSection.hidden = true;
    cameraSection.style.display = "block";

    try {
        if (!cameraStream) {
            cameraStream = await navigator.mediaDevices.getUserMedia({
                video: true
            });
        }

        cameraPreview.srcObject = cameraStream;

    } catch (error) {
        console.error("Camera access denied:", error);
        alert("Unable to access the camera.");
    }
});

// -----------------------------------------
// Capture Photo
// -----------------------------------------

const captureButton = document.getElementById("captureButton");
const cameraCanvas = document.getElementById("cameraCanvas");

captureButton.addEventListener("click", function () {
    if (!cameraStream || !cameraPreview.videoWidth) {
        alert("Please start the camera first.");
        return;
    }

    const context = cameraCanvas.getContext("2d");

    cameraCanvas.width = cameraPreview.videoWidth;
    cameraCanvas.height = cameraPreview.videoHeight;

    context.drawImage(
        cameraPreview,
        0,
        0,
        cameraCanvas.width,
        cameraCanvas.height
    );

    cameraCanvas.toBlob(function (blob) {
        if (!blob) {
            alert("Unable to capture photo.");
            return;
        }

        const file = new File(
            [blob],
            "camera_capture.png",
            { type: "image/png" }
        );

        selectMedia(file, "image");

        const imageURL = URL.createObjectURL(blob);

        preview.innerHTML = `
            <img src="${imageURL}" alt="Captured photo">
        `;

    }, "image/png");
});

// -----------------------------------------
// Analyze Media
// Image + Video + Audio + Text
// -----------------------------------------

analyzeButton.addEventListener("click", async function () {
    if (!selectedType) {
        alert("Please select media or text first.");
        return;
    }

    let endpoint;
    let requestOptions;

    if (selectedType === "text") {
        const text = textInput.value.trim();
        const wordCount = text.split(/\s+/).filter(Boolean).length;

        if (wordCount < 40) {
            resultDiv.textContent =
                "Please enter at least 40 words.";
            return;
        }

        endpoint = "/detect/text";

        requestOptions = {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ text: text })
        };

    } else {
        if (!selectedFile) {
            alert("Please select a file first.");
            return;
        }

        const endpoints = {
            image: "/detect/image",
            video: "/detect/video",
            audio: "/detect/audio"
        };

        if (!endpoints[selectedType]) {
            resultDiv.textContent = "Unsupported media type.";
            return;
        }

        endpoint = endpoints[selectedType];

        const formData = new FormData();
        formData.append("file", selectedFile);

        requestOptions = {
            method: "POST",
            body: formData
        };
    }

    resultDiv.textContent = "Analyzing...";
    analyzeButton.disabled = true;

    try {
        const result = await sendAnalysis(
            endpoint,
            requestOptions
        );

        displayResult(result);

    } catch (error) {
        console.error("AI API Error:", error);
        resultDiv.textContent = error.message;

    } finally {
        analyzeButton.disabled = false;
    }
});

// -----------------------------------------
// Analyze Link
// Image + Video URLs
// -----------------------------------------

linkButton.addEventListener("click", async function () {
    const url = mediaURL.value.trim();

    if (!url) {
        alert("Please enter a URL.");
        return;
    }

    try {
        const parsedURL = new URL(url);

        if (!["http:", "https:"].includes(parsedURL.protocol)) {
            throw new Error(
                "Please enter an HTTP or HTTPS URL."
            );
        }

    } catch (error) {
        resultDiv.textContent =
            "Please enter a valid HTTP or HTTPS URL.";
        return;
    }

    resultDiv.textContent = "Analyzing link...";
    linkButton.disabled = true;

    try {
        const result = await sendAnalysis(
            "/detect/link",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ url: url })
            }
        );

        displayResult(result);

    } catch (error) {
        console.error("Link Error:", error);
        resultDiv.textContent = error.message;

    } finally {
        linkButton.disabled = false;
    }
});
