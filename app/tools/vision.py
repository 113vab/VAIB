import cv2
import time
import logging
from pathlib import Path
from PIL import Image
import google.generativeai as genai
from app.config import logger, DATA_DIR, GEMINI_API_KEY

def capture_webcam_frame() -> str:
    """
    Captures a frame from the user's webcam (primary camera device) and saves it to the webcam data directory.
    Returns the absolute path to the saved image file, or an error message if it fails.
    """
    webcam_dir = DATA_DIR / "webcam"
    webcam_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = int(time.time() * 1000)
    filename = f"webcam_{timestamp}.jpg"
    output_path = webcam_dir / filename
    
    try:
        logger.info("Opening webcam for frame capture...")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            # Try alternative index
            cap = cv2.VideoCapture(1)
            if not cap.isOpened():
                return "Failed to access webcam, Sir. No camera device found or it is in use."
        
        # Warmup delay for auto-exposure/focus to stabilize
        time.sleep(0.5)
        ret, frame = cap.read()
        cap.release()
        
        if not ret or frame is None:
            return "Failed to capture a valid frame from the webcam, Sir."
            
        cv2.imwrite(str(output_path), frame)
        logger.info(f"Webcam frame saved to: {output_path}")
        return str(output_path)
    except Exception as e:
        logger.error(f"Error capturing webcam frame: {e}")
        return f"Failed to capture webcam frame, Sir: {str(e)}"

def analyze_image_with_vision(image_path: str, prompt: str) -> str:
    """
    Analyze or perform OCR on a local image (e.g. screenshot, webcam capture, document) using Gemini Vision.
    
    Args:
        image_path: The absolute path of the local image file to analyze.
        prompt: Detailed instructions or questions about the image (e.g. 'Read the text in this image', 'What error is shown here?', 'Describe what you see').
    """
    if not GEMINI_API_KEY:
        return "I am currently in simulation mode, Sir. I cannot analyze the image without a valid Gemini API key."
        
    path = Path(image_path)
    if not path.exists():
        return f"Error: The image file at '{image_path}' does not exist, Sir."
        
    try:
        logger.info(f"Analyzing image '{image_path}' with Gemini Vision. Prompt: '{prompt}'")
        img = Image.open(path)
        
        # Configure genai client if not already configured
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        response = model.generate_content([prompt, img])
        
        if response.text:
            return response.text
        return "Gemini Vision analysis completed with no text response, Sir."
    except Exception as e:
        logger.error(f"Error during image analysis: {e}")
        return f"Failed to analyze the image, Sir: {str(e)}"
