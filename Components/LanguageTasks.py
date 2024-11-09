from typing import List, Tuple
import json
import time
import re
import logging
import ollama
from rich.console import Console
from rich.panel import Panel
from rich.theme import Theme
import torch
device = torch.device("mps") if torch.backends.mps.is_available() else torch.device("cpu")


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Rich console
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red",
    "success": "green",
    "highlight": "bold magenta"
})

console = Console(theme=custom_theme)

def print_section(title: str, content: str, style: str = "info"):
    """Print a nicely formatted section"""
    console.print(Panel(content, title=title, style=style))

def reformat_transcript(transcript: str) -> str:
    """Convert the transcript into a cleaner, timestamp-based format"""
    logger.info("Starting transcript reformatting")
    lines = transcript.strip().split('\n')
    formatted_events = []
    skipped_lines = 0
    
    for line_num, line in enumerate(lines, 1):
        if not line.strip():
            continue
        
        try:
            # Try parsing as "start - end: text" format
            if ' - ' in line and ': ' in line:
                time_part, text = line.strip().split(': ', 1)
                start, end = time_part.split(' - ')
                try:
                    start_sec = int(float(start))
                    formatted_events.append(f"[{start_sec}s] {text.strip()}\n")
                    continue
                except ValueError as e:
                    logger.warning(f"Line {line_num}: Invalid timestamp format: {e}")
            
            # Try parsing with regex for more flexible format
            match = re.match(r'(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\s*:\s*(.+)', line.strip())
            if match:
                start, end, text = match.groups()
                try:
                    start_sec = int(float(start))
                    formatted_events.append(f"[{start_sec}s] {text.strip()}\n")
                except ValueError as e:
                    logger.warning(f"Line {line_num}: Invalid timestamp conversion: {e}")
            else:
                skipped_lines += 1
                logger.debug(f"Line {line_num}: Could not parse line format: {line.strip()}")
        
        except Exception as e:
            skipped_lines += 1
            logger.warning(f"Line {line_num}: Unexpected error parsing line: {e}")
    
    formatted_text = "".join(formatted_events)
    
    if not formatted_text:
        logger.warning("No events could be formatted from transcript")
    else:
        logger.info(f"Successfully formatted {len(formatted_events)} events. Skipped {skipped_lines} lines.")
    
    return formatted_text

def GetHighlight(transcription: str, max_retries: int = 3, num_clips: int = 3) -> List[Tuple[int, int]]:
    """Get multiple highlights from the transcription"""
    console.clear()
    console.print("\n[bold cyan]🎬 Video Highlight Extractor[/bold cyan]\n")
    
    reformatted_transcript = reformat_transcript(transcription)
    if not reformatted_transcript.strip():
        logger.error("No valid transcript content to analyze")
        return [(0, 30)]
    
    time_matches = re.findall(r'\[(\d+)s\]', reformatted_transcript)
    valid_times = [int(t) for t in time_matches]
    
    if not valid_times:
        logger.warning("No valid timestamps found in transcript")
        return [(0, 30)]
    
    min_time = min(valid_times)
    max_time = max(valid_times)

    # Example output format with "segments" containing highlights directly
    example_clips = {
        "segments": [
            {
                "segment start": "<start seconds as integer>",
                "segment end": "<end seconds as integer>",
                "content": "<Description of interesting moment 1>",
                "duration": "<segment end - segment start> # This cannot be higher than 60 seconds"
            },
            {
                "segment start": "<start seconds as integer>",
                "segment end": "<end second as integer>",
                "content": "<Description of interesting moment 2>",
                "duration": "<segment end - segment start> # This cannot be higher than 60 seconds"
            },
            {
                "segment start": "<start seconds as integer>",
                "segment end": "<end seconds as integer>",
                "content": "<Description of interesting moment 3>",
                "duration": "<segment end - segment start> # This cannot be higher than 60 seconds"
            }
        ]
    }

    example_format = json.dumps(example_clips, indent=4)

    # Updated prompt including the new format with "segments" directly containing highlights
    prompt = f'''You MUST select exactly {num_clips}  most interesting clips from this video transcript.

VIDEO INFO:
- Length: {max_time - min_time} seconds
- Contains timestamps from {min_time}s to {max_time}s

REQUIREMENTS:
1. Return AT LEAST {num_clips} CLIPS inside a JSON object with a key "segments" containing an array.
2. Each clip must be 15 - 60 seconds long.  DO NOT GO OVER 60 SECONDS OR UNDER 15 SECONDS ON THE CLIP.
3. Clips must not overlap or overlap by at most 1 second.
4. Select the most interesting/intense moments only.

NOTE: The above format is just an example. Use actual timestamps from the transcript provided.

TRANSCRIPT:
{reformatted_transcript}

YOUR RESPONSE MUST BE IN THIS EXACT FORMAT (RETURN YOUR REPLACEMENT FOR THE TEXT IN BRACKETS <>):
{example_format}'''

    print_section("📝 Reformatted Transcript", reformatted_transcript)
    print_section("📤 Prompt", prompt)
    
    client = ollama.Client()
    retries_left = max_retries
    
    while retries_left > 0:
        console.print(f"\n[bold]Attempt {max_retries - retries_left + 1}/{max_retries}[/bold]")
        console.print("─" * 50)
        
        try:
            response = client.chat(
                model="mistral:latest",
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a JSON generator that MUST return exactly {num_clips} clips inside a JSON object with a key 'segments'. Only return the JSON object in the required format. No extra text."
                    },
                    {"role": "user", "content": prompt}
                ],
                format="json"
            )
            
            if not response or 'message' not in response or 'content' not in response['message']:
                retries_left -= 1
                continue
            
            content = response['message']['content'].strip()
            print_section("📄 Raw Response", content)
            
            try:
                data = json.loads(content)
                highlights = data.get("segments", [])
                
                valid_clips = []
                used_times = set()
                
                for clip in highlights:
                    if not isinstance(clip, dict) or 'segment start' not in clip or 'segment end' not in clip:
                        continue
                    
                    try:
                        start_time = int(clip.get("segment start"))
                        end_time = int(clip.get("segment end"))
                    except ValueError:
                        logger.warning(f"Clip with invalid time format encountered. Skipping: {clip}")
                        continue
                    
                    # Ensure the clip duration and no overlap or minimal overlap
                    duration = end_time - start_time
                    if start_time < end_time and 15 <= duration <= 60:
                        # Check for minimal overlap tolerance of 1 second
                        if not any(t in used_times for t in range(start_time, end_time + 1)) or end_time - start_time <= 3:
                            valid_clips.append((start_time, end_time))
                            used_times.update(range(start_time, end_time + 1))
                            print_section(
                                "🎯 Valid Clip",
                                f"Start: {start_time}s\nEnd: {end_time}s\nDuration: {duration}s\nContent: {clip.get('content', 'N/A')}",
                                "success"
                            )
                            # Stop if we have enough clips
                            if len(valid_clips) == num_clips:
                                break
                
                # Ensure we have the exact number of clips requested
                if len(valid_clips) >= num_clips:
                    return sorted(valid_clips[:num_clips])  # Trim excess clips if necessary
                else:
                    print_section(
                        "⚠️ Wrong Number of Clips",
                        f"Got {len(valid_clips)} clips, need exactly {num_clips}. Retrying...",
                        "warning"
                    )
                
            except json.JSONDecodeError as e:
                console.print(f"[error]❌ Invalid JSON format: {e}[/error]")
                console.print(f"[error]Raw content: {content}[/error]")
            
        except Exception as e:
            console.print(f"[error]❌ Attempt failed: {e}[/error]")
        
        retries_left -= 1
        console.print("\n[warning]⚠️ Sleepying 5")
        time.sleep(5)
    
    # If all retries failed, use the first timestamp as fallback
    console.print("\n[warning]⚠️ All attempts failed, using first timestamp[/warning]")


if __name__ == "__main__":
    test_transcript = """
    0.0 - 2.0: Get back!
    2.0 - 3.0: Get back!
    90.0 - 100.0: He's running! He's running! He's running!
    100.0 - 109.0: Get on the ground!
    109.0 - 124.0: And the woods, he's in the woods.
    """
    
    try:
        clips = GetHighlight(test_transcript, num_clips=3)
        for i, (start, end) in enumerate(clips, 1):
            print_section(
                f"🎥 Clip {i}",
                f"Start: {start} seconds\nEnd: {end} seconds\nDuration: {end - start} seconds",
                "success"
            )
    except Exception as e:
        print_section("❌ Error", str(e), "error")
        logger.exception("Error in main execution")