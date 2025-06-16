import os
import requests
import re
from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from moviepy.editor import *
from typing import Dict

# --- Configuration ---
# IMPORTANT: You must set your ElevenLabs API Key in the Render dashboard
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Voice IDs from ElevenLabs for Peter and Brian (replace with your preferred voices)
VOICE_IDS = {
    "peter": "N2lVSenPjV6F_h5T2u2K", # Pre-made "Adam" voice
    "brian": "yoZ06aMzmToWyo4y4TfN", # Pre-made "Dorothy" voice
}
BACKGROUND_VIDEO_PATH = "static/background_minecraft.mp4"
CHARACTER_IMAGE_PATHS = {
    "peter": "static/peter.png",
    "brian": "static/brian.png",
}

# --- App Initialization ---
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# --- Helper Function: Text to Speech ---
def generate_audio_elevenlabs(text: str, voice_id: str, filename: str):
    """Generates audio using ElevenLabs API and saves it to a file."""
    if not ELEVENLABS_API_KEY:
        raise ValueError("ElevenLabs API key is not set.")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY,
    }
    data = {
        "text": text,
        "model_id": "eleven_monolingual_v1",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        with open(filename, "wb") as f:
            f.write(response.content)
        return True
    return False


# --- API Endpoints ---
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serves the main HTML page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/generate-video")
async def generate_video_endpoint(payload: Dict = Body(...)):
    """The main endpoint to generate the video."""
    script = payload.get("script", "")
    if not script:
        raise HTTPException(status_code=400, detail="Script is empty.")
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=500, detail="Server is missing API key configuration.")

    lines = [line.strip() for line in script.split('\n') if line.strip()]
    dialogue_clips = []
    temp_audio_files = []

    try:
        # 1. Generate audio for each line
        for i, line in enumerate(lines):
            match = re.match(r'\[(\w+)\]:\s*(.*)', line, re.IGNORECASE)
            if not match:
                continue

            character, text = match.groups()
            character = character.lower()
            
            if character not in VOICE_IDS:
                continue

            audio_filename = f"temp_audio_{i}.mp3"
            if generate_audio_elevenlabs(text, VOICE_IDS[character], audio_filename):
                audio_clip = AudioFileClip(audio_filename)
                dialogue_clips.append({"character": character, "text": text, "audio": audio_clip})
                temp_audio_files.append(audio_filename)
            else:
                raise HTTPException(status_code=500, detail=f"Failed to generate audio for line: {line}")

        if not dialogue_clips:
            raise HTTPException(status_code=400, detail="No valid dialogue lines found in script.")

        # 2. Stitch audio clips together
        final_audio = concatenate_audioclips([d["audio"] for d in dialogue_clips])
        final_video_duration = final_audio.duration

        # 3. Prepare video layers
        background_clip = VideoFileClip(BACKGROUND_VIDEO_PATH).subclip(0, final_video_duration).set_audio(final_audio)
        
        video_clips_to_compose = [background_clip]
        current_time = 0

        for clip_data in dialogue_clips:
            char_img_path = CHARACTER_IMAGE_PATHS[clip_data["character"]]
            audio_duration = clip_data["audio"].duration

            # Character image
            img_clip = (ImageClip(char_img_path)
                        .set_duration(audio_duration)
                        .set_start(current_time)
                        .set_position(("center", "center"))
                        .resize(height=300)) # Adjust size as needed

            # Caption text
            txt_clip = (TextClip(clip_data["text"], fontsize=40, color='white', font='Arial-Bold',
                                 stroke_color='black', stroke_width=2, size=(background_clip.w * 0.8, None), method='caption')
                        .set_duration(audio_duration)
                        .set_start(current_time)
                        .set_position(("center", 0.8), relative=True))

            video_clips_to_compose.extend([img_clip, txt_clip])
            current_time += audio_duration

        # 4. Compose final video
        final_video = CompositeVideoClip(video_clips_to_compose)
        output_filename = "final_video.mp4"
        final_video.write_videofile(output_filename, codec="libx264", audio_codec="aac", fps=24)

        return FileResponse(output_filename, media_type="video/mp4", filename="ai_generated_video.mp4")

    finally:
        # 5. Clean up temporary files
        for clip_data in dialogue_clips:
            clip_data["audio"].close() # Close MoviePy file handles
        # It's important to close clips before trying to delete files on some OSs
        for f in temp_audio_files:
            if os.path.exists(f):
                os.remove(f)
        if 'final_video' in locals() and final_video:
             final_video.close()
        if os.path.exists("final_video.mp4"):
            # The FileResponse needs the file to exist, it will be deleted by Render's ephemeral filesystem later
            pass