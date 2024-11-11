from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
import os

def add_logo_to_video(cropped_video_path, logo_path="logo.png", logo_height=60, margin=(10, 10), fps=30, position="top_left", output_filename=None):
    """
    Adds a smaller logo to the specified corner of the cropped video with a specified margin, including audio in the final video.

    Parameters:
        cropped_video_path (str): Path to the cropped video file.
        logo_path (str): Path to the logo image file.
        logo_height (int): Desired height for the logo in pixels.
        margin (tuple): Margin from the edges in pixels (default is (10, 10)).
        fps (int): Frames per second for the output video.
        position (str): Position of the logo ('top_left' or 'top_right').
        output_filename (str): Optional custom name for the output file (default is the input filename with "_with_logo").
    """
    # Load the cropped video
    with VideoFileClip(cropped_video_path) as video_clip:
        # Check if video has audio
        if video_clip.audio is None:
            print("Warning: Input video has no audio.")
        
        # Load and configure the logo image
        logo = (ImageClip(logo_path)
                .set_duration(video_clip.duration)
                .resize(height=logo_height))

        # Set the position of the logo based on the 'position' argument
        if position == "top_left":
            logo = logo.set_position((margin[0], margin[1]))
        elif position == "top_right":
            logo = logo.set_position((video_clip.w - logo.w - margin[0], margin[1]))

        # Combine video and logo
        video_with_logo = CompositeVideoClip([video_clip, logo])

        # Define the output path
        if output_filename is None:
            output_filename = os.path.splitext(cropped_video_path)[0] + "_with_logo.mp4"
        
        # Ensure audio is included in the output
        video_with_logo.write_videofile(output_filename, fps=fps, audio=True, audio_codec='aac', codec='libx264')
        print(f"Saved final video with logo at: {output_filename}")

