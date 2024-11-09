from moviepy.video.io.VideoFileClip import VideoFileClip
import os
import shutil

def extract_audio(video_path, temp_dir="temp"):
    """
    Extracts audio from a video file and saves it to a temporary directory.
    Args:
    - video_path (str): Path to the video file.
    - temp_dir (str): Directory to store temporary audio file.
    
    Returns:
    - str: Path to the extracted audio file.
    """
    os.makedirs(temp_dir, exist_ok=True)
    try:
        video_clip = VideoFileClip(video_path)
        audio_path = os.path.join(temp_dir, "audio.wav")
        video_clip.audio.write_audiofile(audio_path)
        video_clip.close()
        print(f"Extracted audio to: {audio_path}")
        return audio_path
    except Exception as e:
        print(f"An error occurred while extracting audio: {e}")
        return None

def crop_video(input_file, output_file, start_time, end_time):
    """
    Crops a video file to the specified start and end times.
    
    Args:
    - input_file (str): Path to the input video file.
    - output_file (str): Path to save the cropped video.
    - start_time (float): Start time in seconds.
    - end_time (float): End time in seconds.
    """
    with VideoFileClip(input_file) as video:
        cropped_video = video.subclip(start_time, end_time)
        cropped_video.write_videofile(output_file, codec='libx264')

def generate_multiple_shorts(input_file, segments, output_dir="shorts", temp_dir="temp"):
    """
    Generates multiple video shorts based on specified time segments.
    
    Args:
    - input_file (str): Path to the input video file.
    - segments (list): List of tuples (start_time, end_time) for each short.
    - output_dir (str): Directory to save the generated shorts.
    - temp_dir (str): Directory to store temporary files.

    Returns:
    - list: Paths to the generated short video files.
    """
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)
    
    shorts_paths = []
    for i, (start, end) in enumerate(segments):
        output_file = os.path.join(output_dir, f"Short_{i+1}.mp4")
        print(f"Creating short: {output_file} from {start} to {end} seconds")
        crop_video(input_file, output_file, start, end)
        shorts_paths.append(output_file)
    
    # Cleanup temp files
    shutil.rmtree(temp_dir)
    print(f"Temporary files in '{temp_dir}' have been removed.")
    return shorts_paths

# Example usage
if __name__ == "__main__":
    input_file = "Example.mp4"  # Replace with your actual input video path
    segments = [(10, 20), (30, 40), (50, 60)]  # Define start and end times for each short
    generate_multiple_shorts(input_file, segments)
