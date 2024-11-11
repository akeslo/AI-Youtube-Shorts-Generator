import captacity
import os
import random
from moviepy.editor import VideoFileClip
import whisper

def add_captions_to_video(input_path, output_path, model_size="small"):
    """Add captions to a video using custom Whisper model while preserving audio."""
    try:
        print("Adding captions to video...")

        # Define 20 visually balanced color combinations
        color_combinations = [
            {'font_color': '#FFFFFF', 'stroke_color': '#000000', 'word_highlight_color': '#FFD700', 'line_count': 2},  # White text, black outline, gold highlight
            {'font_color': '#000000', 'stroke_color': '#FFFFFF', 'word_highlight_color': '#FF4500', 'line_count': 1},  # Black text, white outline, orange highlight
            {'font_color': '#FFD700', 'stroke_color': '#000000', 'word_highlight_color': '#00CED1', 'line_count': 2},  # Gold text, black outline, teal highlight
            {'font_color': '#32CD32', 'stroke_color': '#000000', 'word_highlight_color': '#FF4500', 'line_count': 1},  # Lime green text, black outline, orange highlight
            {'font_color': '#FF4500', 'stroke_color': '#FFFFFF', 'word_highlight_color': '#1E90FF', 'line_count': 2},  # Orange text, white outline, blue highlight
            {'font_color': '#FFFFFF', 'stroke_color': '#FF4500', 'word_highlight_color': '#32CD32', 'line_count': 1},  # White text, orange outline, lime highlight
            {'font_color': '#1E90FF', 'stroke_color': '#000000', 'word_highlight_color': '#FFD700', 'line_count': 2},  # Blue text, black outline, gold highlight
            {'font_color': '#8A2BE2', 'stroke_color': '#FFFFFF', 'word_highlight_color': '#FFFF00', 'line_count': 1},  # Purple text, white outline, yellow highlight
            {'font_color': '#FFFFFF', 'stroke_color': '#00008B', 'word_highlight_color': '#00FA9A', 'line_count': 2},  # White text, dark blue outline, spring green highlight
            {'font_color': '#FFD700', 'stroke_color': '#00008B', 'word_highlight_color': '#00CED1', 'line_count': 1},  # Gold text, dark blue outline, teal highlight
            {'font_color': '#1E90FF', 'stroke_color': '#FF4500', 'word_highlight_color': '#FFFFFF', 'line_count': 2},  # Blue text, orange outline, white highlight
            {'font_color': '#FF1493', 'stroke_color': '#000000', 'word_highlight_color': '#32CD32', 'line_count': 1},  # Pink text, black outline, lime highlight
            {'font_color': '#32CD32', 'stroke_color': '#FFFFFF', 'word_highlight_color': '#FF4500', 'line_count': 2},  # Lime green text, white outline, orange highlight
            {'font_color': '#FFFF00', 'stroke_color': '#8A2BE2', 'word_highlight_color': '#1E90FF', 'line_count': 1},  # Yellow text, purple outline, blue highlight
            {'font_color': '#00008B', 'stroke_color': '#FFD700', 'word_highlight_color': '#FFFFFF', 'line_count': 2},  # Dark blue text, gold outline, white highlight
            {'font_color': '#FF4500', 'stroke_color': '#1E90FF', 'word_highlight_color': '#FFFFFF', 'line_count': 1},  # Orange text, blue outline, white highlight
            {'font_color': '#FFFFFF', 'stroke_color': '#8A2BE2', 'word_highlight_color': '#FFD700', 'line_count': 2},  # White text, purple outline, gold highlight
            {'font_color': '#32CD32', 'stroke_color': '#8A2BE2', 'word_highlight_color': '#FFFFFF', 'line_count': 1},  # Lime green text, purple outline, white highlight
            {'font_color': '#FF1493', 'stroke_color': '#FFFFFF', 'word_highlight_color': '#00CED1', 'line_count': 2},  # Pink text, white outline, teal highlight
            {'font_color': '#FFFFFF', 'stroke_color': '#32CD32', 'word_highlight_color': '#FF1493', 'line_count': 1},  # White text, lime outline, pink highlight
        ]

        # Randomly select a color combination
        selected_colors = random.choice(color_combinations)
        
        # Create a temporary output path for the captioned video
        temp_output = f"temp_{os.path.basename(output_path)}"
        
        # Load and run Whisper transcription
        print("Loading Whisper model...")
        model = whisper.load_model(model_size)
        
        print("Transcribing video...")
        result = model.transcribe(
            input_path,
            word_timestamps=True,
            fp16=False
        )
        
        # Convert Whisper segments to Captacity format
        segments = []
        for segment in result["segments"]:
            words = []
            if "words" in segment:
                for word in segment["words"]:
                    words.append({
                        "word": word["word"],
                        "start": word["start"],
                        "end": word["end"]
                    })
            
            segments.append({
                "text": segment["text"],
                "start": segment["start"],
                "end": segment["end"],
                "words": words
            })
        
        # Add captions with custom transcription and selected colors, adjusting font and positioning
        captacity.add_captions(
            video_file=input_path,
            output_file=temp_output,
            font_size=60,
            font_color=selected_colors['font_color'],
            stroke_width=2,
            stroke_color=selected_colors['stroke_color'],
            highlight_current_word=True,
            word_highlight_color=selected_colors['word_highlight_color'],
            line_count=selected_colors['line_count'],
            padding=50,
            position=('center', 'bottom'),
            shadow_strength=2,
            shadow_blur=1,
            print_info=True,
            use_local_whisper=True,
            segments=segments
        )
        
        if not os.path.exists(temp_output):
            print("Failed to generate captioned video")
            return False
            
        try:
            print("Processing final video with audio...")
            # Load the original video to get its audio
            original_video = VideoFileClip(input_path)
            
            # Load the captioned video
            captioned_video = VideoFileClip(temp_output)
            
            # Set the audio from the original video
            final_video = captioned_video.set_audio(original_video.audio)
            
            # Write the final video with audio
            final_video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac'
            )
            
            # Clean up
            original_video.close()
            captioned_video.close()
            final_video.close()
            
            if os.path.exists(temp_output):
                os.remove(temp_output)
                
            print("Successfully added captions with audio")
            return True
            
        except Exception as e:
            print(f"Error processing video with audio: {str(e)}")
            # If something goes wrong, try to clean up
            if 'original_video' in locals():
                original_video.close()
            if 'captioned_video' in locals():
                captioned_video.close()
            if 'final_video' in locals():
                final_video.close()
            if os.path.exists(temp_output):
                os.remove(temp_output)
            return False
            
    except Exception as e:
        print(f"Error adding captions: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False
