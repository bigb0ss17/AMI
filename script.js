const imageButton = document.getElementById("imageButton");
const videoButton = document.getElementById("videoButton");

const imageInput = document.getElementById("imageInput");
const videoInput = document.getElementById("videoInput");

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

captureButton.addEventListener("click", function () {

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

});


// -----------------------------
// Analyze Image
// -----------------------------

const analyzeButton = document.getElementById("analyzeButton");
const resultDiv = document.getElementById("result");

analyzeButton.addEventListener("click", async function () {

    const file = imageInput.files[0];

    if (!file) {
        alert("Please select an image first.");
        return;
    }

    const formData = new FormData();

    formData.append("file", file);

    try {

        // Send the image to the FastAPI backend.
        // Nginx forwards this request to FastAPI on port 8000.
        const response = await fetch("/upload-image", {
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
        resultDiv.innerHTML = `
            <p>${result.message}</p>
            <p>Status: ${result.status}</p>
            <p>Analysis: ${result.analysis.result}</p>
            <p>Dimensions: ${result.analysis.width} × ${result.analysis.height}</p>
            <p>Format: ${result.analysis.format}</p>
            <p>Color Mode: ${result.analysis.color_mode}</p>
        `;

    } catch (error) {

        console.error("Error:", error);

        resultDiv.innerHTML = `
            <p>Unable to connect to the backend.</p>
        `;

    }

});