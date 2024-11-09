from faster_whisper import WhisperModel
import torch
import hashlib
from pathlib import Path
import logging
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TranscriptionCache:
    def __init__(self, cache_dir="cache"):
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
            return None
            
        cache_file = self.cache_dir / f"{cache_key}.txt"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    logger.info("Using cached transcription...")
                    lines = f.readlines()
                    if not lines:
                        logger.warning("Cache file exists but is empty")
                        return None
                    
                    # Parse lines in the format "start - end: text"
                    result = []
                    for line in lines:
                        try:
                            time_part, text = line.strip().split(': ', 1)
                            start, end = time_part.split(' - ')
                            result.append([text, float(start), float(end)])
                        except ValueError as e:
                            logger.warning(f"Skipping malformed line: {line.strip()}, Error: {e}")
                    
                    if result:
                        logger.info(f"Successfully loaded {len(result)} segments from cache")
                        return result
                    else:
                        logger.warning("No valid segments found in cache file")
                        return None
            except Exception as e:
                logger.error(f"Cache file corrupted, transcribing again... Error: {e}")
        return None
    
    def save_transcription(self, cache_key, transcription):
        """Save transcription to cache"""
        if not cache_key:
            logger.error("Cannot save transcription: Invalid cache key")
            return
            
        cache_file = self.cache_dir / f"{cache_key}.txt"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                f.write(transcription)
            logger.info(f"Saved transcription to cache: {cache_file}")
            # Verify the file was written
            if os.path.exists(cache_file) and os.path.getsize(cache_file) > 0:
                logger.info(f"Cache file successfully written: {os.path.getsize(cache_file)} bytes")
            else:
                logger.warning("Cache file appears to be empty after writing")
        except Exception as e:
            logger.error(f"Failed to save transcription to cache: {e}")

def transcribe_audio(audio_path):
    """
    Transcribe audio file to text using Whisper model.
    Returns list of [text, start_time, end_time] for each segment.
    """
    logger.info(f"Starting transcription for: {audio_path}")
    
    # Verify audio file exists and has content
    if not os.path.exists(audio_path):
        logger.error(f"Audio file not found: {audio_path}")
        return []
        
    file_size = os.path.getsize(audio_path)
    if file_size == 0:
        logger.error("Audio file is empty")
        return []
    logger.info(f"Audio file size: {file_size / (1024*1024):.2f} MB")
    
    # Initialize cache
    cache = TranscriptionCache()
    cache_key = cache.get_cache_key(audio_path)
    
    # Check cache first
    cached_result = cache.get_cached_transcription(cache_key)
    if cached_result is not None:
        logger.info(f"Retrieved {len(cached_result)} segments from cache")
        return cached_result
    
    logger.info("No cache found, transcribing audio...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")
    
    try:
        logger.info("Loading Whisper model...")
        model = WhisperModel("base.en", device=device)
        logger.info("Model loaded successfully")
        
        # Transcribe audio
        logger.info("Starting transcription process...")
        segments, info = model.transcribe(
            audio=audio_path,
            beam_size=5,
            language="en"
        )
        logger.info(f"Transcription completed. Language detection info: {info}")
        
        # Convert segments to list and log some stats
        segments_list = list(segments)  # Convert generator to list
        logger.info(f"Number of segments transcribed: {len(segments_list)}")
        
        if not segments_list:
            logger.warning("No segments were transcribed!")
            return []
            
        extracted_texts = []
        for segment in segments_list:
            text = segment.text.strip()
            if text:  # Only add non-empty segments
                extracted_texts.append([text, segment.start, segment.end])
                logger.debug(f"Segment {segment.start:.2f}-{segment.end:.2f}: {text}")
        
        logger.info(f"Extracted {len(extracted_texts)} text segments")
        
        if extracted_texts:
            formatted_text = format_transcription(extracted_texts)
            # Save to cache
            cache.save_transcription(cache_key, formatted_text)
            logger.info("Transcription cached successfully")
            
            # Print a sample of transcription
            logger.info("Sample of transcription:")
            for i, (text, start, end) in enumerate(extracted_texts[:3]):
                logger.info(f"Segment {i+1}: {start:.2f}-{end:.2f}: {text}")
            
            return extracted_texts
        else:
            logger.warning("No text was extracted from the segments")
            return []
        
    except Exception as e:
        logger.error(f"Transcription Error: {str(e)}", exc_info=True)
        return []

def format_transcription(transcriptions):
    """Format transcriptions into a readable string"""
    if not transcriptions:
        logger.warning("No transcriptions to format")
        return ""
        
    formatted = "\n".join([f"{start:.2f} - {end:.2f}: {text}" for text, start, end in transcriptions])
    logger.debug(f"Formatted transcription:\n{formatted[:500]}...")  # Log first 500 chars as sample
    return formatted

if __name__ == "__main__":
    audio_path = "audio.wav"
    
    try:
        # Get transcriptions
        transcriptions = transcribe_audio(audio_path)
        
        if transcriptions:
            # Format and save the text output
            trans_text = format_transcription(transcriptions)
            
            # Save formatted output to file
            output_file = "transcription_output.txt"
            with open(output_file, "w", encoding='utf-8') as f:
                f.write(trans_text)
            
            print(f"\nTranscription completed and saved to {output_file}")
            print("\nFirst few lines of transcription:")
            print("\n".join(trans_text.split("\n")[:5]))
            
            # Print some statistics
            print(f"\nTotal segments: {len(transcriptions)}")
            total_duration = transcriptions[-1][2] - transcriptions[0][1]
            print(f"Total duration: {total_duration:.2f} seconds")
        else:
            print("No transcription available.")
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}", exc_info=True)