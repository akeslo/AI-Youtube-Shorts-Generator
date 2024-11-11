from moviepy.video.io.VideoFileClip import VideoFileClip
import os
import shutil
from rich.console import Console
from rich.progress import Progress
from rich import print

console = Console()

def get_temp_dir():
    """
    Creates and returns the path to the temp directory in the parent folder.
    """
    temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir

def extract_audio(video_path):
    """
    Extracts audio from a video file and saves it to a temporary directory.
    Args:
    - video_path (str): Path to the video file.
    
    Returns:
    - str: Path to the extracted audio file.
    """
    temp_dir = get_temp_dir()
    try:
        video_clip = VideoFileClip(video_path)
        audio_path = os.path.join(temp_dir, "audio.wav")
        with Progress(console=console) as progress:
            task = progress.add_task("[cyan]Extracting audio...", total=100)
            video_clip.audio.write_audiofile(audio_path)
            progress.update(task, completed=100)
        video_clip.close()
        console.log(f"[green]Extracted audio to: {audio_path}")
        return audio_path
    except Exception as e:
        console.log(f"[red]An error occurred while extracting audio: {e}")
        return None

def crop_video(input_file, output_file, start_time, end_time):
    """
    Crops a video while preserving audio.
    """
    temp_dir = get_temp_dir()
    temp_audio = os.path.join(temp_dir, "temp-audio.m4a")
    
    with VideoFileClip(input_file) as video:
        # Check if video has audio
        if video.audio is None:
            console.log("[yellow]Warning: Input video has no audio track")
            cropped_video = video.subclip(start_time, end_time)
        else:
            cropped_video = video.subclip(start_time, end_time)
        
        console.log(f"[blue]Cropping video from {start_time}s to {end_time}s")
        # Explicitly include audio and set audio codec
        cropped_video.write_videofile(
            output_file,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile=temp_audio,
            remove_temp=True,
            audio=True
        )

def generate_multiple_shorts(input_file, segments, output_dir="shorts", filename="short"):
    """
    Generates multiple video shorts based on specified time segments.
    
    Args:
    - input_file (str): Path to the input video file.
    - segments (list): List of tuples (start_time, end_time) for each short.
    - output_dir (str): Directory to save the generated shorts.
    - filename (str): Base name for each generated short video file.

    Returns:
    - list: Paths to the generated short video files.
    """
    temp_dir = get_temp_dir()
    os.makedirs(output_dir, exist_ok=True)
    
    shorts_paths = []
    try:
        # Verify input file exists and has audio
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file not found: {input_file}")
            
        with VideoFileClip(input_file) as video:
            if video.audio is None:
                console.log("[yellow]Warning: Input video has no audio track")
        
        for i, (start, end) in enumerate(segments):
            output_file = os.path.join(output_dir, f"{filename}_{i+1}.mp4")
            console.log(f"[cyan]Creating short video: {output_file} from {start} to {end} seconds")
            crop_video(input_file, output_file, start, end)
            shorts_paths.append(output_file)
        
        return shorts_paths
    
    except Exception as e:
        console.log(f"[red]Error generating shorts: {e}")
        return []
    
    finally:
        # Cleanup temp files
        if os.path.exists(temp_dir):
            console.log(f"[yellow]Cleaning up temporary files in {temp_dir}")
            shutil.rmtree(temp_dir)

# Example usage
if __name__ == "__main__":
    input_file = "/Users/akeslo/Scrypting/AI-Youtube-Shorts-Generator/yt_source/video_Chaos Erupts After Man Drives Stolen Car Off 25 Foot Embankment in North Caldwell, NJ.mp4"
    segments = [(10, 20), (100, 120), (200, 230)]  # Define start and end times for each short
    generate_multiple_shorts(input_file, segments)