import os
from pytubefix import YouTube
import ffmpeg

def get_video_size(stream):
    """Calculate video size in MB."""
    return stream.filesize / (1024 * 1024)

def download_youtube_video(url):
    """
    Downloads a YouTube video, merging video and audio streams if needed.

    Args:
    - url (str): URL of the YouTube video.

    Returns:
    - str: Path to the final video file.
    """
    try:
        yt = YouTube(url)
        video_streams = yt.streams.filter(type="video").order_by('resolution').desc()
        audio_stream = yt.streams.filter(only_audio=True).first()

        print("Available video streams:")
        for i, stream in enumerate(video_streams):
            size = get_video_size(stream)
            stream_type = "Progressive" if stream.is_progressive else "Adaptive"
            print(f"{i}. Resolution: {stream.resolution}, Size: {size:.2f} MB, Type: {stream_type}")

        choice = int(input("Enter the number of the video stream to download: "))
        selected_stream = video_streams[choice]

        if not os.path.exists('yt_source'):
            os.makedirs('yt_source')

        print(f"Downloading video: {yt.title}")
        video_file = selected_stream.download(output_path='yt_source', filename_prefix="video_")

        # Handle separate audio download and merge if needed
        if not selected_stream.is_progressive:
            print("Downloading audio...")
            audio_file = audio_stream.download(output_path='yt_source', filename_prefix="audio_")

            print("Merging video and audio...")
            output_file = os.path.join('yt_source', f"{yt.title}.mp4")
            stream = ffmpeg.input(video_file)
            audio = ffmpeg.input(audio_file)
            stream = ffmpeg.output(stream, audio, output_file, vcodec='libx264', acodec='aac', strict='experimental')
            ffmpeg.run(stream, overwrite_output=True)

            # Optional cleanup of temporary video and audio files
            os.remove(video_file)
            os.remove(audio_file)
        else:
            output_file = video_file

        print(f"Downloaded: {yt.title} to 'yt_source' folder")
        print(f"File path: {output_file}")
        return output_file

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        print("Please make sure you have the latest version of pytube and ffmpeg-python installed.")
        print("You can update them by running:")
        print("pip install --upgrade pytube ffmpeg-python")
        print("Also, ensure that ffmpeg is installed on your system and available in your PATH.")

if __name__ == "__main__":
    youtube_url = input("Enter YouTube video URL: ")
    download_youtube_video(youtube_url)
