const imageButton = document.getElementById("imageButton");
const videoButton = document.getElementById("videoButton");

const imageInput = document.getElementById("imageInput");
const videoInput = document.getElementById("videoInput");

const audioButton = document.getElementById("audioButton");
const audioInput = document.getElementById("audioInput");

const preview = document.getElementById("preview");


// -----------------------------
// Image Upload
// -----------------------------

imageButton.addEventListener("click", function () {
    imageInput.click();
});

imageInput.addEventListener("change", function () {

    const file = imageInput.files[0];

    if (!file) {
        return;
    }

    const imageURL = URL.createObjectURL(file);

    preview.innerHTML = `
        <img src="${imageURL}" alt="Selected image">
    `;
});


// -----------------------------
// Video Upload
// -----------------------------

videoButton.addEventListener("click", function () {
    videoInput.click();
});

videoInput.addEventListener("change", function () {

    const file = videoInput.files[0];

    if (!file) {
        return;
    }

    const videoURL = URL.createObjectURL(file);

    preview.innerHTML = `
        <video controls>
            <source src="${videoURL}" type="${file.type}">
            Your browser does not support video playback.
        </video>
    `;
});

// -----------------------------
// Audio Upload
// -----------------------------

audioButton.addEventListener("click", function () {
    audioInput.click();
});

audioInput.addEventListener("change", function () {

    const file = audioInput.files[0];

    if (!file) {
        return;
    }

    const audioURL = URL.createObjectURL(file);

    preview.innerHTML = `
        <audio controls>
            <source src="${audioURL}" type="${file.type}">
            Your browser does not support audio playback.
        </audio>
    `;
});

// -----------------------------
// Camera
// -----------------------------

const cameraButton = document.getElementById("cameraButton");
const cameraSection = document.getElementById("cameraSection");
const cameraPreview = document.getElementById("cameraPreview");

let cameraStream;

cameraButton.addEventListener("click", async function () {

    cameraSection.style.display = "block";

    try {

        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: true
        });

        cameraPreview.srcObject = cameraStream;

    } catch (error) {

        console.error("Camera access denied:", error);

        alert("Unable to access the camera.");

    }

});


// -----------------------------
// Capture Photo
// -----------------------------

const captureButton = document.getElementById("captureButton");
const cameraCanvas = document.getElementById("cameraCanvas");

captureButton.addEventListener("click", async function () {

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

    const imageURL = cameraCanvas.toDataURL("image/png");

    preview.innerHTML = `
        <img src="${imageURL}" alt="Captured photo">
    `;

    cameraCanvas.toBlob(
    async (blob) => {

        const formData = new FormData();

        formData.append(
            "file",
            blob,
            "camera_capture.png"
        );

        try {

            const response =
            await fetch(
                "/upload-image",
                {
                    method: "POST",
                    body: formData
                }
            );

            const result =
            await response.json();

            resultDiv.innerHTML = `
                <p>${result.message}</p>
            `;

        } catch (error) {

            console.error(error);

        }

    },
    "image/png"
);
});


// -----------------------------
// Analyze Image
// -----------------------------

const analyzeButton = document.getElementById("analyzeButton");
const resultDiv = document.getElementById("result");

analyzeButton.addEventListener("click", async function () {

    const imageFile = imageInput.files[0];
    const videoFile = videoInput.files[0];
    const audioFile = audioInput.files[0];

    if (!imageFile && !videoFile && !audioFile) {
        alert("Please select a file first.");
        return;
    }

    const formData = new FormData();

    let endpoint = "";

    if (imageFile) {

        formData.append("file", imageFile);

        endpoint = "/upload-image";

    } else if (videoFile) {

        formData.append("file", videoFile);

        endpoint = "/upload-video";

    } else if (audioFile) {

        formData.append("file", audioFile);

        endpoint = "/upload-audio";

    }

    try {

        // Send the image to the FastAPI backend.
        // Nginx forwards this request to FastAPI on port 8000.
        const response = await fetch(endpoint, {
            method: "POST",
            body: formData
        });

        const result = await response.json();

        // Handle backend errors
        if (!response.ok) {

            resultDiv.innerHTML = `
                <p>Analysis failed.</p>
                <p>${result.detail || "An unknown error occurred."}</p>
            `;

            return;
        }

        // Display backend results

        if (endpoint === "/upload-image") {

            resultDiv.innerHTML = `
                <p>${result.message}</p>
                <p>Status: ${result.status}</p>
                <p>Analysis: ${result.analysis.result}</p>
                <p>Dimensions: ${result.analysis.width} × ${result.analysis.height}</p>
                <p>Format: ${result.analysis.format}</p>
                <p>Color Mode: ${result.analysis.color_mode}</p>
            `;

        } else {

            resultDiv.innerHTML = `
                <p>${result.message}</p>
                <p>Status: ${result.status}</p>
                <p>Filename: ${result.filename}</p>
                <p>Size: ${result.size} bytes</p>
            `;

        }

    } catch (error) {

        console.error("Error:", error);

        resultDiv.innerHTML = `
            <p>Unable to connect to the backend.</p>
        `;

    }

});

// -----------------------------
// Analyze Link
// -----------------------------

const linkButton =
document.getElementById("linkButton");

linkButton.addEventListener(
    "click",
    async function () {

        const url =
        document.getElementById("mediaURL").value;

        if (!url) {
            alert("Please enter a URL.");
            return;
        }

        const response =
        await fetch("/analyze-link", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                url: url
            })
        });

        const result =
        await response.json();

        resultDiv.innerHTML = `
            <p>${result.message}</p>
            <p>${result.url}</p>
        `;
    }
);