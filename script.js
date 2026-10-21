
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

// Use the local Flask server during development.
// Use the same website address when deployed to AWS.
const AI_API =
    ["localhost", "127.0.0.1"].includes(window.location.hostname)
        ? "http://127.0.0.1:8000"
        : "";

// Currently selected media
let selectedFile = null;
let selectedType = null;
let cameraStream = null;
let recaptchaWidgetId = null;
let captchaToken = null;

const captchaSection =
    document.getElementById("captchaSection");

// Google calls this after the reCAPTCHA API loads.
function initializeRecaptcha() {
    if (recaptchaWidgetId !== null) {
        return;
    }

    if (
        typeof grecaptcha === "undefined" ||
        typeof grecaptcha.render !== "function"
    ) {
        resultDiv.textContent =
            "Human verification is still loading. Please wait a moment and click Analyze again.";
        return;
    }

    recaptchaWidgetId = grecaptcha.render(
        "recaptcha-container",
        {
            sitekey: "6LdcSPotAAAAAFTI6FyCnw0R3Meb-ga4EsoRJIui",

            callback: function (token) {
                captchaToken = token;
                runAnalysisAfterCaptcha(token);
            },

            "expired-callback": function () {
                captchaToken = null;
                resultDiv.textContent =
                    "Verification expired. Please verify again.";
            },

            "error-callback": function () {
                captchaToken = null;
                resultDiv.textContent =
                    "CAPTCHA failed to load. Please try again.";
            }
        }
    );
}

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
        result.detail ||
        result.error ||
        `Analysis failed (${response.status}).`
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

analyzeButton.addEventListener("click", function () {
    if (!selectedType) {
        alert("Please select media or text first.");
        return;
    }

    // Validate text before asking for CAPTCHA.
    if (selectedType === "text") {
        const wordCount = textInput.value
            .trim()
            .split(/\s+/)
            .filter(Boolean).length;

        if (wordCount < 40) {
            resultDiv.textContent =
                "Please enter at least 40 words.";
            return;
        }
    }

    captchaSection.hidden = false;
    if (recaptchaWidgetId === null) {
    initializeRecaptcha();
}

    resultDiv.textContent =
        "Please complete the human verification.";

    captchaSection.scrollIntoView({
        behavior: "smooth",
        block: "center"
    });
});

async function runAnalysisAfterCaptcha(token) {
    if (!token) {
        resultDiv.textContent =
            "Please complete the CAPTCHA first.";
        return;
    }

    let endpoint;
    let requestOptions;

    const headers = {
        "X-Recaptcha-Token": token
    };

    if (selectedType === "text") {
        const text = textInput.value.trim();

        endpoint = "/detect/text";

        requestOptions = {
            method: "POST",
            headers: {
                ...headers,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ text })
        };

    } else if (selectedType === "link") {
        const url = mediaURL.value.trim();

        if (!url) {
            resultDiv.textContent = "Please enter a URL.";
            return;
        }

        endpoint = "/detect/link";

        requestOptions = {
            method: "POST",
            headers: {
                ...headers,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ url })
        };

    } else {
        if (!selectedFile) {
            resultDiv.textContent =
                "Please select a file first.";
            return;
        }

        const endpoints = {
            image: "/detect/image",
            video: "/detect/video",
            audio: "/detect/audio"
        };

        endpoint = endpoints[selectedType];

        if (!endpoint) {
            resultDiv.textContent = "Unsupported media type.";
            return;
        }

        const formData = new FormData();
        formData.append("file", selectedFile);

        requestOptions = {
            method: "POST",
            headers,
            body: formData
        };
    }

    analyzeButton.disabled = true;
    linkButton.disabled = true;
    resultDiv.textContent = "Processing request...";

    try {
        const result = await sendAnalysis(
            endpoint,
            requestOptions
        );

        // The current backend does not return AI probabilities.
        if (
            typeof result.ai_probability === "number" &&
            typeof result.human_probability === "number" &&
            result.type !== undefined &&
            result.label !== undefined
        ) {
            displayResult(result);
        } else {
            resultDiv.textContent =
                result.message ||
                "The server received the request, but AI detection " +
                "results are not available yet.";
        }

    } catch (error) {
        console.error("Analysis error:", error);
        resultDiv.textContent = error.message;

    } finally {
        analyzeButton.disabled = false;
        linkButton.disabled = false;
        captchaToken = null;

        if (recaptchaWidgetId !== null) {
            grecaptcha.reset(recaptchaWidgetId);
        }
    }
}

// -----------------------------------------
// Analyze Link
// Image + Video URLs
// -----------------------------------------

// -----------------------------------------
// Analyze Link
// -----------------------------------------

linkButton.addEventListener("click", function () {
    const url = mediaURL.value.trim();

    if (!url) {
        resultDiv.textContent = "Please enter a URL.";
        return;
    }

    try {
        const parsedURL = new URL(url);

        if (!["http:", "https:"].includes(parsedURL.protocol)) {
            throw new Error("Invalid URL protocol.");
        }
    } catch {
        resultDiv.textContent =
            "Please enter a valid HTTP or HTTPS URL.";
        return;
    }

    selectedFile = null;
    selectedType = "link";

    captchaSection.hidden = false;
    if (recaptchaWidgetId === null) {
    initializeRecaptcha();
}

    resultDiv.textContent =
        "Please complete the human verification.";

    captchaSection.scrollIntoView({
        behavior: "smooth",
        block: "center"
    });
});

