from faster_whisper import WhisperModel
import torch
import hashlib
from pathlib import Path
import logging
import os
import json
import time
from pydub import AudioSegment

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TranscriptionCache:
    def __init__(self, cache_dir="shorts/cache/transcription"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
    def get_cache_key(self, audio_path):
        """Generate a unique cache key based on the audio file content"""
        logger.info(f"Generating cache key for {audio_path}")
        if not os.path.exists(audio_path):
            logger.error(f"Audio file does not exist: {audio_path}")
            return None
            
        with open(audio_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def get_cached_transcription(self, cache_key):
        """Retrieve cached transcription if it exists"""
        if not cache_key:
            logger.error("Invalid cache key")
            return None, False
            
        # First check progress file
        progress_file = self.cache_dir / f"{cache_key}_progress.json"
        if progress_file.exists():
            try:
                with open(progress_file, 'r', encoding='utf-8') as f:
                    progress_data = json.load(f)
                    if progress_data:
                        logger.info(f"Found partial transcription with {len(progress_data)} segments")
                        return progress_data, True
            except Exception as e:
                logger.error(f"Error reading progress file: {e}")
        
        # Then check complete transcription
        cache_file = self.cache_dir / f"{cache_key}_complete.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    complete_data = json.load(f)
                    if complete_data:
                        logger.info(f"Found complete transcription with {len(complete_data)} segments")
                        return complete_data, False
            except Exception as e:
                logger.error(f"Error reading complete cache file: {e}")
        
        return None, False

    def save_progress(self, cache_key, segments, is_complete=False):
        """Save transcription progress or complete transcription"""
        if not cache_key:
            logger.error("Cannot save: Invalid cache key")
            return False
            
        try:
            # Convert segments to serializable format if needed
            serializable_segments = []
            for segment in segments:
                if isinstance(segment, list) and len(segment) == 3:
                    text, start, end = segment
                    serializable_segments.append({
                        'text': str(text),
                        'start': float(start),
                        'end': float(end)
                    })
                else:
                    logger.error(f"Invalid segment format: {segment}")
                    return False
            
            if is_complete:
                # Save as complete transcription
                complete_file = self.cache_dir / f"{cache_key}_complete.json"
                progress_file = self.cache_dir / f"{cache_key}_progress.json"
                
                with open(complete_file, 'w', encoding='utf-8') as f:
                    json.dump(serializable_segments, f, indent=2)
                
                # Remove progress file if it exists
                if progress_file.exists():
                    progress_file.unlink()
                
                # Also save formatted text version for human reading
                text_file = self.cache_dir / f"{cache_key}_transcript.txt"
                formatted_text = format_transcription(segments)
                with open(text_file, 'w', encoding='utf-8') as f:
                    f.write(formatted_text)
                
                logger.info(f"Saved complete transcription: {len(serializable_segments)} segments")
            else:
                # Save as progress
                progress_file = self.cache_dir / f"{cache_key}_progress.json"
                with open(progress_file, 'w', encoding='utf-8') as f:
                    json.dump(serializable_segments, f, indent=2)
                logger.info(f"Saved progress: {len(serializable_segments)} segments")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save transcription: {e}")
            return False

def split_audio(audio_path, chunk_duration=30):
    """Split audio file into chunks"""
    try:
        audio = AudioSegment.from_wav(audio_path)
        chunks = []
        
        chunk_length = chunk_duration * 1000  # Convert to milliseconds
        for i in range(0, len(audio), chunk_length):
            chunk = audio[i:i + chunk_length]
            chunk_path = f"temp/chunk_{i//chunk_length}.wav"
            os.makedirs("temp", exist_ok=True)
            chunk.export(chunk_path, format="wav")
            chunks.append((chunk_path, i/1000))  # Store path and start time
            
        return chunks
    except Exception as e:
        logger.error(f"Error splitting audio: {e}")
        return []

def transcribe_audio(audio_path, chunk_duration=30):
    """
    Transcribe audio file to text using Whisper model with resumable capability.
    Returns list of [text, start_time, end_time] for each segment.
    """
    logger.info(f"Starting transcription for: {audio_path}")
    
    if not os.path.exists(audio_path):
        logger.error(f"Audio file not found: {audio_path}")
        return []
        
    file_size = os.path.getsize(audio_path)
    if file_size == 0:
        logger.error("Audio file is empty")
        return []
    
    # Initialize cache and check for existing transcription
    cache = TranscriptionCache()
    cache_key = cache.get_cache_key(audio_path)
    
    if not cache_key:
        logger.error("Failed to generate cache key")
        return []
    
    cached_result, is_partial = cache.get_cached_transcription(cache_key)
    
    if cached_result and not is_partial:
        logger.info("Using complete cached transcription")
        return [[s['text'], s['start'], s['end']] for s in cached_result]
    
    current_segments = []
    if cached_result and is_partial:
        current_segments = [[s['text'], s['start'], s['end']] 
                          for s in cached_result if isinstance(s, dict)]
        logger.info(f"Resuming from {len(current_segments)} cached segments")
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")
    
    try:
        model = WhisperModel("small.en", device=device)
        logger.info("Model loaded successfully")
        
        # Split audio into chunks
        last_chunk = len(current_segments) // 3 if current_segments else 0
        chunks = split_audio(audio_path, chunk_duration)
        
        for i, (chunk_path, start_time) in enumerate(chunks[last_chunk:], start=last_chunk):
            try:
                logger.info(f"Processing chunk {i+1}/{len(chunks)}")
                
                segments, info = model.transcribe(
                    audio=chunk_path,
                    beam_size=5,
                    language="en"
                )
                
                # Process segments
                new_segments = []
                for segment in segments:
                    text = segment.text.strip()
                    if text:
                        # Adjust timestamps to account for chunk position
                        new_segments.append([
                            text,
                            segment.start + start_time,
                            segment.end + start_time
                        ])
                
                if new_segments:
                    # Add new segments and save progress
                    current_segments.extend(new_segments)
                    if not cache.save_progress(cache_key, current_segments):
                        logger.error("Failed to save progress")
                
                # Clean up chunk file
                os.remove(chunk_path)
                
                # Small delay to prevent system stress
                time.sleep(0.1)
                
            except Exception as chunk_error:
                logger.error(f"Error processing chunk {i}: {chunk_error}")
                # Save progress before raising the error
                if current_segments:
                    cache.save_progress(cache_key, current_segments)
                raise
        
        # Mark as complete
        if current_segments:
            if cache.save_progress(cache_key, current_segments, is_complete=True):
                logger.info("Transcription completed and saved successfully")
            else:
                logger.error("Failed to save complete transcription")
        
        return current_segments
            
    except Exception as e:
        logger.error(f"Transcription Error: {str(e)}", exc_info=True)
        # Save progress even if there's an error
        if current_segments:
            cache.save_progress(cache_key, current_segments)
        return current_segments

def format_transcription(transcriptions):
    """Format transcriptions into a readable string"""
    if not transcriptions:
        logger.warning("No transcriptions to format")
        return ""
    
    try:
        formatted_lines = []
        for segment in transcriptions:
            if isinstance(segment, dict):
                start = segment['start']
                end = segment['end']
                text = segment['text']
            else:
                text, start, end = segment
            formatted_lines.append(f"{start:.2f} - {end:.2f}: {text}")
        
        formatted = "\n".join(formatted_lines)
        logger.debug(f"Formatted transcription:\n{formatted[:500]}...")
        return formatted
    except Exception as e:
        logger.error(f"Error formatting transcription: {e}")
        return ""

if __name__ == "__main__":
    audio_path = "audio.wav"
    
    try:
        transcriptions = transcribe_audio(audio_path)
        
        if transcriptions:
            trans_text = format_transcription(transcriptions)
            
            # Save both JSON and text formats
            cache = TranscriptionCache()
            cache_key = cache.get_cache_key(audio_path)
            
            if cache_key:
                # Save complete version if not already saved
                cache.save_progress(cache_key, transcriptions, is_complete=True)
            
            # Save formatted text output
            output_file = "transcription_output.txt"
            with open(output_file, "w", encoding='utf-8') as f:
                f.write(trans_text)
            
            print(f"\nTranscription completed and saved to {output_file}")
            print("\nFirst few lines of transcription:")
            print("\n".join(trans_text.split("\n")[:5]))
            
            print(f"\nTotal segments: {len(transcriptions)}")
            if transcriptions:
                total_duration = transcriptions[-1][2] if isinstance(transcriptions[-1], list) else transcriptions[-1]['end']
                start_time = transcriptions[0][1] if isinstance(transcriptions[0], list) else transcriptions[0]['start']
                print(f"Total duration: {total_duration - start_time:.2f} seconds")
        else:
            print("No transcription available.")
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}", exc_info=True)