import cv2
from moviepy.editor import VideoFileClip, CompositeVideoClip
import os
from pathlib import Path
import threading
import sys

def list_endscreen_templates():
    """
    List all available endscreen templates in the templates/end directory.
    
    Returns:
        list: List of template filenames
    """
    template_dir = Path("templates/end")
    if not template_dir.exists():
        print(f"Error: Template directory {template_dir} not found")
        return []
    
    # Get all video files in the template directory
    templates = [f.name for f in template_dir.glob("*.mp4")]
    return templates

def select_endscreen_template():
    """
    Prompt user to select an endscreen template from available options, with a timeout.
    
    Returns:
        str: Full path to selected template, or the first template if timeout occurs
    """
    templates = list_endscreen_templates()
    
    if not templates:
        print("No endscreen templates found in templates/end directory")
        return None
    
    # Display available templates
    print("\nAvailable endscreen templates:")
    for idx, template in enumerate(templates, 1):
        print(f"{idx}. {template}")
    
    # Get user selection with a timeout
    selection = [None]
    
    def get_user_input():
        try:
            selection[0] = input("\nSelect endscreen template number (or press Enter to skip): ").strip()
        except Exception:
            pass
    
    input_thread = threading.Thread(target=get_user_input)
    input_thread.daemon = True
    input_thread.start()
    input_thread.join(10)  # Wait for 10 seconds for user input
    
    # Use the first template if no input is provided
    if selection[0] is None or selection[0] == "":
        print("No input provided. Using the first available template.")
        return str(Path("templates/end") / templates[0])
    
    try:
        idx = int(selection[0]) - 1
        if 0 <= idx < len(templates):
            selected_template = templates[idx]
            return str(Path("templates/end") / selected_template)
        else:
            print("Invalid selection. Using the first available template.")
            return str(Path("templates/end") / templates[0])
    except ValueError:
        print("Invalid input. Using the first available template.")
        return str(Path("templates/end") / templates[0])

def add_endscreen(video_path, output_path, max_duration=60.0):
    try:
        # Prompt for template selection
        template_path = select_endscreen_template()
        if not template_path:
            print("No endscreen template selected, skipping...")
            return False

        # Load the main video
        main_video = VideoFileClip(video_path)

        # Load the endscreen template
        endscreen = VideoFileClip(template_path)

        # Check if adding endscreen would exceed max duration
        if main_video.duration + endscreen.duration > max_duration:
            print(f"Cannot add endscreen: Total duration would exceed {max_duration} seconds")
            main_video.close()
            endscreen.close()
            return False

        # Resize endscreen to match main video dimensions
        endscreen_resized = endscreen.resize(main_video.size)

        # Combine the videos
        final_video = CompositeVideoClip([
            main_video,
            endscreen_resized.set_start(main_video.duration)
        ])

        # Write the final video
        final_video.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile='temp-audio.m4a',
            remove_temp=True
        )

        # Clean up
        main_video.reader.close()
        if main_video.audio:
            main_video.audio.reader.close_proc()

        endscreen.reader.close()
        if endscreen.audio:
            endscreen.audio.reader.close_proc()

        final_video.reader.close()
        if final_video.audio:
            final_video.audio.reader.close_proc()

        main_video.close()
        endscreen.close()
        final_video.close()

        return True

    except Exception as e:
        print(f"Error adding endscreen: {str(e)}")
        return False

def check_duration(video_path):
    """
    Check the duration of a video file.
    
    Args:
        video_path (str): Path to the video file
        
    Returns:
        float: Duration of the video in seconds
    """
    try:
        video = VideoFileClip(video_path)
        duration = video.duration
        video.close()
        return duration
    except Exception as e:
        print(f"Error checking video duration: {str(e)}")
        return None
