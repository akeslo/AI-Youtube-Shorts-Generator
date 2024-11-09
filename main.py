from Components.YoutubeDownloader import download_youtube_video
from Components.Edit import extract_audio, crop_video, generate_multiple_shorts
from Components.Transcription import transcribe_audio
from Components.LanguageTasks import GetHighlight
from Components.FaceCrop import crop_to_vertical, combine_videos
from Components.AIMon import monitor_cpu_usage
import os
import shutil
import threading

# Start CPU monitoring in a separate thread
monitor_thread = threading.Thread(target=monitor_cpu_usage, args=(), daemon=True)
monitor_thread.start()

# Set up directories
output_dir = "shorts"
os.makedirs(output_dir, exist_ok=True)

# Get video URL input
url = input("Enter YouTube video URL: ")
Vid = download_youtube_video(url)
if Vid:
    Vid = Vid.replace(".webm", ".mp4")
    print(f"Downloaded video at {Vid}")

    # Extract audio from video
    Audio = extract_audio(Vid)
    if Audio:
        # Transcribe audio and get transcription text
        transcriptions = transcribe_audio(Audio)
        if transcriptions:
            TransText = ""
            for transcription in transcriptions:
                # Expecting each transcription entry to have start and end times
                if len(transcription) == 3:
                    text, start, end = transcription
                    TransText += f"{start} - {end}: {text}\n"
                elif len(transcription) == 2:
                    text, start = transcription
                    TransText += f"{start}: {text}\n"
                else:
                    print("Unexpected transcription format")

            # Get multiple highlights from transcriptions
            segments = GetHighlight(TransText)
            if segments:
                # Generate multiple shorts based on the extracted highlights
                print(f"Creating shorts for segments: {segments}")
                generate_multiple_shorts(Vid, segments, output_dir=output_dir)

                # Process each short for face cropping and combining, then clean up
                for i, (start, end) in enumerate(segments):
                    short_path = os.path.join(output_dir, f"Short_{i+1}.mp4")
                    cropped_short = os.path.join(output_dir, f"Cropped_Short_{i+1}.mp4")
                    final_short = os.path.join(output_dir, f"Final_Short_{i+1}.mp4")

                    # Perform face cropping and combine videos
                    crop_to_vertical(short_path, cropped_short)
                    combine_videos(short_path, cropped_short, final_short)
                    print(f"Processed and saved final short at {final_short}")

                    # Clean up intermediate files
                    if os.path.exists(short_path):
                        os.remove(short_path)
                    if os.path.exists(cropped_short):
                        os.remove(cropped_short)

                # Final cleanup of video and audio files if specified
                if os.path.exists(Vid):
                    os.remove(Vid)
                if os.path.exists(Audio):
                    os.remove(Audio)
                
                print("Cleanup complete: Only final shorts remain in the output directory.")
            else:
                print("No highlights found for creating shorts.")
        else:
            print("Transcription returned no results.")
    else:
        print("Failed to extract audio from the video.")
else:
    print("Failed to download the video.")
