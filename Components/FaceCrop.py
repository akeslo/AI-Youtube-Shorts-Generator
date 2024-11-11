import os
import cv2
import numpy as np
import ffmpeg
from moviepy.editor import *
from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install
from Components.Speaker import detect_faces_and_speakers, Frames

# Set up Rich console and logging
console = Console()
install()
global Fps

# Set up temp directory path
temp_dir = "temp/"
os.makedirs(temp_dir, exist_ok=True)  # Ensure temp directory exists at startup

def ensure_temp_directory():
    """Ensures that the temp directory exists"""
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
        console.log(f"[bold cyan]Created temp directory at {temp_dir}[/bold cyan]")

def debug_video_info(video_path):
    """Print debug information about the video file"""
    try:
        video = VideoFileClip(video_path)
        console.log(f"[bold cyan]Video Debug Info:[/bold cyan]")
        console.log(f"Video path: {video_path}")
        console.log(f"Audio stream present: {video.audio is not None}")
        console.log(f"Video duration: {video.duration:.2f} seconds")
        console.log(f"Video size: {video.size}")
        console.log(f"Video fps: {video.fps}")
        video.close()
    except Exception as e:
        console.log(f"[bold red]Error getting video info:[/bold red] {str(e)}")

def extract_audio(input_video_path, output_audio_path):
    """Extract audio from video to a separate file"""
    try:
        ensure_temp_directory()
        console.log(f"Attempting to extract audio from: {input_video_path}")
        video = VideoFileClip(input_video_path)
        
        if video.audio is None:
            console.log("[bold red]No audio stream found in input video[/bold red]")
            video.close()
            return False
        
        # Extract and save audio
        console.log("Audio stream found, extracting to file...")
        video.audio.write_audiofile(output_audio_path)
        video.audio.close()
        video.close()
        
        if os.path.exists(output_audio_path):
            console.log(f"[bold green]Audio extracted successfully to: {output_audio_path}[/bold green]")
            return True
        else:
            console.log("[bold red]Audio file wasn't created[/bold red]")
            return False
            
    except Exception as e:
        console.log(f"[bold red]Error extracting audio:[/bold red] {str(e)}")
        return False

def crop_to_vertical(input_video_path, output_video_path):
    console.log("\n[bold]Starting video processing...[/bold]")
    debug_video_info(input_video_path)
    
    # Ensure temp directory exists before extracting audio
    ensure_temp_directory()
    temp_audio_path = os.path.join(temp_dir, "temp_audio.mp3")
    if not extract_audio(input_video_path, temp_audio_path):
        console.log("[bold yellow]Warning: Proceeding without audio[/bold yellow]")
    
    console.log("\nStarting face and speaker detection...")
    temp_dec_out = os.path.join(temp_dir, "DecOut.mp4")
    detect_faces_and_speakers(input_video_path, temp_dec_out)
    
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    cap = cv2.VideoCapture(input_video_path)
    
    if not cap.isOpened():
        console.log("[bold red]Error: Could not open video.[/bold red]")
        return False

    # Get video properties
    original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    vertical_height = int(original_height)
    vertical_width = int(vertical_height * 9 / 16)
    
    console.log(f"\n[bold cyan]Video Properties:[/bold cyan]")
    console.log(f"Original Dimensions: {original_width}x{original_height}")
    console.log(f"Target Vertical Dimensions: {vertical_width}x{vertical_height}")
    console.log(f"FPS: {fps}")
    console.log(f"Total Frames: {total_frames}")

    if original_width < vertical_width:
        console.log("[bold red]Error: Original video width is less than desired vertical width.[/bold red]")
        return False

    x_start = (original_width - vertical_width) // 2
    x_end = x_start + vertical_width
    half_width = vertical_width // 2

    # Create temporary video file
    temp_output = os.path.join(temp_dir, "temp_output.mp4")
    fourcc = cv2.VideoWriter_fourcc(*'avc1')
    out = cv2.VideoWriter(temp_output, fourcc, fps, (vertical_width, vertical_height))
    global Fps
    Fps = fps

    frame_count = 0
    console.log("\nProcessing frames...")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        
        x, y, w, h = x_start, 0, vertical_width, vertical_height
        if len(faces) > 0:
            for f in faces:
                x1, y1, w1, h1 = f
                center = x1 + w1 // 2
                if center > x_start and center < x_end:
                    x, y, w, h = x1, y1, w1, h1
                    break
            
        centerX = x + (w // 2)
        if frame_count == 0 or (x_start - (centerX - half_width)) < 1:
            pass
        else:
            x_start = centerX - half_width
            x_end = centerX + half_width
            
        frame_count += 1
        cropped_frame = frame[:, x_start:x_end]
        
        if cropped_frame.shape[1] == 0:
            x_start = (original_width - vertical_width) // 2
            x_end = x_start + vertical_width
            cropped_frame = frame[:, x_start:x_end]
        
        out.write(cropped_frame)
        
        if frame_count % 100 == 0:
            console.log(f"Processed {frame_count}/{total_frames} frames")
    
    cap.release()
    out.release()

    if not os.path.exists(temp_output):
        console.log("[bold red]Error: temp_output.mp4 was not created successfully.[/bold red]")
        return False

    # Combine video with audio using FFmpeg
    try:
        console.log("\nCombining video and audio using FFmpeg...")
        
        video_stream = ffmpeg.input(temp_output)
        if os.path.exists(temp_audio_path):
            audio_stream = ffmpeg.input(temp_audio_path)
            ffmpeg.output(
                video_stream, 
                audio_stream, 
                output_video_path,
                acodec='aac',
                audio_bitrate='192k',
                vcodec='copy'
            ).overwrite_output().run(capture_stdout=True, capture_stderr=True)
            console.log("[bold green]Successfully combined video and audio[/bold green]")
        else:
            ffmpeg.output(
                video_stream, 
                output_video_path,
                vcodec='copy'
            ).overwrite_output().run(capture_stdout=True, capture_stderr=True)
            console.log("[bold yellow]Created video without audio (no audio found)[/bold yellow]")
            
    except ffmpeg.Error as e:
        console.log(f"[bold red]FFmpeg error:[/bold red] {e.stderr.decode()}")
        return False

    console.log(f"\n[bold green]Cropping complete. Video saved to: {output_video_path}[/bold green]")
    return True

def combine_videos(video_with_audio, video_without_audio, output_filename):
    try:
        console.log("\n[bold]Starting final video combination...[/bold]")
        debug_video_info(video_with_audio)
        
        # Extract audio from source video
        temp_audio_path = os.path.join(temp_dir, "final_audio.mp3")
        ensure_temp_directory()
        
        console.log("\nExtracting audio from source video...")
        
        if not extract_audio(video_with_audio, temp_audio_path):
            console.log("[bold red]Failed to extract audio from source video[/bold red]")
            return False
            
        # Combine the cropped video with the original audio
        console.log("\nCombining final video with audio...")
        video_stream = ffmpeg.input(video_without_audio)
        audio_stream = ffmpeg.input(temp_audio_path)
        
        ffmpeg.output(
            video_stream,
            audio_stream,
            output_filename,
            acodec='aac',
            audio_bitrate='192k',
            vcodec='copy'
        ).overwrite_output().run(capture_stdout=True, capture_stderr=True)
            
        console.log(f"[bold green]Final video saved successfully as: {output_filename}[/bold green]")
        return True
        
    except ffmpeg.Error as e:
        console.log(f"[bold red]Error combining final video and audio:[/bold red] {e.stderr.decode()}")
        return False

if __name__ == "__main__":
    input_video_path = "/Users/akeslo/Scrypting/AI-Youtube-Shorts-Generator/yt_source/s.mp4"
    output_video_path = os.path.join(temp_dir, 'Cropped_output_video.mp4')
    final_video_path = 'final_video_with_audio.mp4'
    
    console.log("[bold magenta]Starting Video Processing Pipeline[/bold magenta]")
    
    if crop_to_vertical(input_video_path, output_video_path):
        if combine_videos(input_video_path, output_video_path, final_video_path):
            console.log("[bold green]Video processing completed successfully![/bold green]")
        else:
            console.log("[bold red]Failed to combine videos with audio.[/bold red]")
    else:
        console.log("[bold red]Failed to crop video.[/bold red]")
