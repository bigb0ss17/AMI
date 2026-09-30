# AI Media Detection

A web application designed to analyze uploaded media and eventually determine whether an image or video is AI-generated.

The project currently includes a frontend built with HTML, CSS, and JavaScript and a Python/FastAPI backend. The backend has also been deployed to an AWS EC2 instance with CloudWatch logging.

> **Current Status:** The website, backend communication, image processing, AWS hosting, and backend logging are working. The actual AI detection model still needs to be integrated.

---

## Project Structure

```text
AI_Media_Detection/
│
├── index.html
├── style.css
├── script.js
│
└── backend/
    └── main.py
```

### `index.html`
Contains the structure of the website, including the media upload, camera, preview, analyze, and results sections.

### `style.css`
Controls the appearance and layout of the website.

### `script.js`
Handles frontend functionality, including:

- Selecting images
- Selecting videos
- Previewing media locally
- Accessing the device camera
- Capturing a photo
- Sending images to the backend
- Displaying backend results

### `backend/main.py`
Contains the Python/FastAPI backend.

The backend currently handles:

- FastAPI server
- `/test` endpoint
- `/upload-image` endpoint
- Image uploads
- File type validation
- File size validation
- Image processing
- Backend responses
- Application logging
- CORS configuration

---

# How the Application Works

## Image Preview

When a user selects an image, JavaScript previews the image directly in the browser.

```text
Select Image
     ↓
JavaScript
     ↓
Local Preview
```

The backend is **not required for image previewing**.

## Image Analysis

When the user clicks **Analyze Media**, the selected image is sent to the FastAPI backend.

```text
User selects image
        ↓
Frontend preview
        ↓
User clicks Analyze Media
        ↓
POST /upload-image
        ↓
FastAPI Backend
        ↓
Validate Image
        ↓
Process Image
        ↓
Return Results
        ↓
Display Results on Website
```

---

# Backend

The backend is written in **Python** using **FastAPI**.

FastAPI allows the frontend and backend to communicate through API endpoints.

## Test Endpoint

```text
GET /test
```

Used to verify that the backend server is running.

Example response:

```json
{
    "message": "Hello from the backend!"
}
```

## Image Upload Endpoint

```text
POST /upload-image
```

Receives an image from the frontend.

The backend currently checks:

- File type
- File size
- Image properties

Supported image types:

```text
JPG / JPEG
PNG
WEBP
```

Maximum image size:

```text
10 MB
```

The backend can also return image information such as:

- Width
- Height
- Image format
- Color mode

---

# Running the Project Locally

## 1. Install Python

Make sure Python is installed.

Check with:

```bash
python --version
```

or:

```bash
python3 --version
```

---

## 2. Open the Project

Open the `AI_Media_Detection` folder in Visual Studio Code.

Open a terminal inside the project folder.

---

## 3. Create a Virtual Environment

Windows:

```powershell
python -m venv venv
```

Activate it:

```powershell
venv\Scripts\activate
```

Mac/Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 4. Install Backend Dependencies

```bash
pip install fastapi uvicorn python-multipart Pillow
```

---

## 5. Start FastAPI

Depending on the location of `main.py`, run:

```bash
uvicorn backend.main:app --reload
```

The backend should start at:

```text
http://127.0.0.1:8000
```

FastAPI documentation is available at:

```text
http://127.0.0.1:8000/docs
```

The `/docs` page can be used to test API endpoints manually.

---

# AWS Deployment

The backend has also been deployed using **Amazon Web Services (AWS)**.

Current AWS architecture:

```text
Internet
   ↓
AWS EC2
   ↓
Nginx
   ↓
FastAPI
   ↓
Image Processing
```

## EC2

Amazon EC2 provides the Linux server that runs the application.

Instead of requiring the backend to run only on a developer's computer, the application can run remotely on AWS.

## Nginx

Nginx acts as a reverse proxy.

Public HTTP requests arrive on:

```text
Port 80
```

Nginx forwards backend requests internally to FastAPI:

```text
127.0.0.1:8000
```

## systemd

FastAPI is configured as a Linux system service named:

```text
ai-media-detection
```

This allows the backend to continue running without keeping an SSH terminal open.

Check the backend service with:

```bash
sudo systemctl status ai-media-detection
```

Restart it with:

```bash
sudo systemctl restart ai-media-detection
```

---

# Backend Logging

The backend records important application activity.

Logs are stored on the EC2 server at:

```text
/var/log/ai-media-detection/backend.log
```

Examples of logged events include:

```text
Server startup
Test endpoint accessed
Image upload received
Invalid image rejected
Image accepted
Image analysis completed
HTTP requests
```

View the logs on EC2 with:

```bash
cat /var/log/ai-media-detection/backend.log
```

For live logs:

```bash
tail -f /var/log/ai-media-detection/backend.log
```

---

# AWS CloudWatch

The project uses **AWS CloudWatch** for centralized backend logging.

```text
FastAPI
   ↓
backend.log
   ↓
CloudWatch Agent
   ↓
AWS CloudWatch
```

CloudWatch allows the team to view backend activity through the AWS Console instead of logging directly into the EC2 server.

Current CloudWatch log group:

```text
/ai-media-detection/backend
```

---

# AWS IAM

An AWS IAM role is attached to the EC2 instance.

The role allows the EC2 server to send logs to CloudWatch without storing AWS access keys directly inside the application.

**Do not place AWS access keys, passwords, or private `.pem` keys in this GitHub repository.**

---

# Important Security Notes

Do **NOT** upload any of the following to GitHub:

```text
*.pem
.env
AWS access keys
Passwords
API secrets
Private credentials
```

The EC2 `.pem` private key should remain private.

A `.gitignore` file should eventually include:

```gitignore
venv/
__pycache__/
*.pyc
.env
*.pem
```

---

# Current Features

- Image upload
- Video selection and preview
- Local image preview
- Local video preview
- Device camera access
- Camera photo capture
- Analyze Media button
- Frontend-to-backend communication
- FastAPI REST API
- Image upload endpoint
- Server-side image validation
- Image metadata processing
- File size validation
- Backend application logging
- AWS EC2 deployment
- Nginx reverse proxy
- FastAPI systemd service
- AWS CloudWatch logging
- IAM role for CloudWatch permissions

---

# Features Still in Development

## AI Detection Model

The main remaining feature is connecting an actual AI detection model to the backend.

Currently, the backend prepares and processes the image, but the final AI-generated probability system still needs to be implemented.

Eventually the backend should return something similar to:

```json
{
    "prediction": "AI Generated",
    "confidence": 0.87
}
```

## Video Analysis

Video selection and preview are available on the frontend, but backend video analysis still needs to be implemented.

## URL Analysis

Future versions should allow users to paste a link to an image or video for analysis.

## Additional Improvements

Possible future work includes:

- AI image classification
- AI video classification
- Confidence scores
- Improved result display
- URL-based media analysis
- Better error handling
- HTTPS
- Domain name
- Database integration
- Additional AWS monitoring

---

# Development Workflow

When making changes:

1. Pull the latest version of the repository.
2. Create or work on the assigned feature.
3. Test the feature locally.
4. Commit the changes.
5. Push the changes to GitHub.
6. Inform the group about major backend or frontend changes.

Avoid editing the same major file simultaneously when possible to reduce merge conflicts.

---

# Sprint Progress

## Sprint 1

Completed work includes:

- Initial website structure
- Website styling
- Image upload
- Video upload
- Media preview
- Camera functionality
- FastAPI backend
- Frontend/backend communication
- Image upload API
- Backend image validation
- Image processing
- Backend logging
- AWS EC2 deployment
- Nginx configuration
- systemd backend service
- CloudWatch logging
- IAM permissions

## Next Sprint

Primary goals:

- Integrate the AI detection model
- Return actual AI detection results
- Continue video backend development
- Improve frontend result display
- Continue testing and documentation

---

# Team Notes

When working locally, remember that frontend previewing and backend analysis are separate processes.

**Frontend:**

```text
HTML + CSS + JavaScript
```

Handles the interface, buttons, camera, and local media preview.

**Backend:**

```text
Python + FastAPI
```

Handles API requests, validation, processing, logging, and eventually AI inference.

**Cloud Infrastructure:**

```text
AWS EC2 + Nginx + CloudWatch + IAM
```

Handles remote hosting, request routing, backend services, permissions, and centralized logging.

---

# Project Goal

The final goal is to allow a user to submit an image or video and receive an AI-generated media prediction from the backend.

```text
Upload Media
     ↓
Preview
     ↓
Analyze
     ↓
Backend
     ↓
AI Detection Model
     ↓
Prediction + Confidence
     ↓
Display Result
```
