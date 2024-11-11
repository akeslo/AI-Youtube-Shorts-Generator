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
import pyperclip

# Set up device
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

def copy_to_clipboard(text: str):
    """Copy text to system clipboard"""
    try:
        pyperclip.copy(text)
        console.print("[success]✓ Copied to clipboard[/success]")
    except Exception as e:
        console.print(f"[error]Failed to copy to clipboard: {e}[/error]")

def print_section(title: str, content: str, style: str = "info"):
    """Print a nicely formatted section"""
    console.print(Panel(content, title=title, style=style))

def reformat_transcript(transcriptions: List[List]) -> str:
    """Convert the transcriptions into a cleaner, timestamp-based format"""

    formatted_events = []
    skipped_lines = 0
    
    try:
        for segment in transcriptions:
            if isinstance(segment, list) and len(segment) == 3:
                text, start, end = segment[0], segment[1], segment[2]
                try:
                    start_sec = int(float(start))
                    formatted_events.append(f"[{start_sec}s] {text.strip()}\n")
                except (ValueError, TypeError) as e:
                    skipped_lines += 1
                    logger.warning(f"Error processing segment times: {e}")
            else:
                skipped_lines += 1
                logger.warning(f"Invalid segment format: {segment}")
    except Exception as e:
        logger.error(f"Error during transcript reformatting: {e}")
        return ""
    
    formatted_text = "".join(formatted_events)
    
    if not formatted_text:
        logger.warning("No events could be formatted from transcriptions")
    
    return formatted_text

def getSegments(transcriptions: List[List], num_clips: int = 2) -> List[Tuple[int, int]]:
    """Prompt user for segment source choice and handle accordingly"""
    console.print("\n[bold cyan]🎬 Video Highlight Extractor[/bold cyan]")
    
    # Debug logging for first few segments
    logger.info(f"Received {len(transcriptions)} transcription segments")
    logger.info("First few segments:")
    for i, segment in enumerate(transcriptions[:5]):
        logger.info(f"Segment {i}: {segment}")
    
    console.print("\nHow would you like to generate segments?")
    console.print("[1] Use AI (Ollama)")
    console.print("[2] Provide JSON manually")
    
    # Get reformatted transcript and time information upfront
    reformatted_transcript = reformat_transcript(transcriptions)
    
    # Find min and max timestamps directly from the transcriptions
    min_time = float('inf')
    max_time = 0
    for segment in transcriptions:
        if isinstance(segment, list) and len(segment) == 3:
            start_time = float(segment[1])
            end_time = float(segment[2])
            min_time = min(min_time, start_time)
            max_time = max(max_time, end_time)
    
    if min_time == float('inf'):
        min_time = 0
    
    video_length = max_time - min_time
    
    while True:
        choice = console.input("\nEnter your choice (1 or 2): ").strip()
        
        if choice == "1":
            return get_highlight_via_ollama(reformatted_transcript, num_clips=num_clips)
        elif choice == "2":
            console.print(f"""
        [bold]VIDEO INFO:[/bold]
        - Length: {int(video_length)} seconds
        - Contains timestamps from {int(min_time)}s to {int(max_time)}s

        [bold]REQUIREMENTS:[/bold]
        1. JSON must contain EXACTLY {num_clips} clips
        2. Each segment must be between 15 and 60 seconds long
        3. Clips should not overlap, or may overlap by at most 5 seconds
        """)
                    
            if reformatted_transcript.strip():
                print_section("📝 Reformatted Transcript", reformatted_transcript)
            else:
                console.print("[warning]⚠️ No valid transcript content available[/warning]")
            
            console.print("\n[bold]Please provide your JSON data in the following format:[/bold]")
            example_format = {
                "segments": [
                    {
                        "segment start": "<start seconds as integer>",
                        "segment end": "<end seconds as integer>",
                        "content": "<Description of moment>",
                        "duration": "<segment end - segment start>"
                    }
                ] * num_clips
            }
            print_section("📄 Expected JSON Format", json.dumps(example_format, indent=2))
            
            json_data = console.input("\nEnter your JSON data: ").strip()
            return get_highlight_via_json(num_clips, json_data)
        else:
            console.print("[error]Invalid choice. Please enter 1 or 2.[/error]")

def get_highlight_via_ollama(transcription: str | List[str], max_retries: int = 5, num_clips: int = 2) -> List[Tuple[int, int]]:
    """Get multiple highlights from the transcription using Ollama"""
    console.clear()
    console.print("\n[bold cyan]🎬 Video Highlight Extractor (Ollama)[/bold cyan]\n")
    
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

    example_clips = {
        "segments": [
            {
                "segment start": "<start seconds as integer>",
                "segment end": "<end seconds as integer>",
                "content": "<Description of interesting moment 1>",
                "duration": "<segment end - segment start>"
            },
            {
                "segment start": "<start seconds as integer>",
                "segment end": "<end seconds as integer>",
                "content": "<Description of interesting moment 2>",
                "duration": "<segment end - segment start>"
            }
        ]
    }

    example_format = json.dumps(example_clips, indent=4)

    prompt = f'''
    Select exactly {num_clips} of the most interesting segments from the video transcript.
    VIDEO INFO:
    - Length: {max_time - min_time} seconds
    - Contains timestamps from {min_time}s to {max_time}s

    REQUIREMENTS:
    1. Return EXACTLY {num_clips} CLIPS inside a JSON object with a key "segments" containing an array.
    2. Each segment must be between 15 and 60 seconds long.
    3. Segments should be interesting, intense, viral, funny, or unusual moments only.
    4. Clips should not overlap, or may overlap by at most 5 seconds.

    NOTE: The below format is an example of what I'd like you to return. Use actual timestamps from the transcript provided.
    {example_format}

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
                model="llama3.2:latest",
                messages=[
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
                    
                    duration = end_time - start_time
                    if start_time < end_time and 15 <= duration <= 60:
                        if not any(t in used_times for t in range(start_time, end_time + 1)) or end_time - start_time <= 3:
                            valid_clips.append((start_time, end_time))
                            used_times.update(range(start_time, end_time + 1))
                            print_section(
                                "🎯 Valid Clip",
                                f"Start: {start_time}s\nEnd: {end_time}s\nDuration: {duration}s\nContent: {clip.get('content', 'N/A')}",
                                "success"
                            )
                            if len(valid_clips) == num_clips:
                                break
                
                if len(valid_clips) >= num_clips:
                    return sorted(valid_clips[:num_clips])
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
        console.print("\n[warning]⚠️ Sleeping 5 seconds")
        time.sleep(5)
    
    console.print("\n[warning]⚠️ All attempts failed")
    return []

def get_highlight_via_json(num_clips: int, json_data: str) -> List[Tuple[int, int]]:
    """Accept raw JSON input for highlights"""
    try:
        # Parse JSON directly without modification
        data = json.loads(json_data)
        highlights = data.get("segments", [])
        
        valid_clips = []
        for clip in highlights:
            try:
                start_time = int(clip["segment start"])
                end_time = int(clip["segment end"])
                duration = end_time - start_time
                
                if 15 <= duration <= 60:
                    valid_clips.append((start_time, end_time))
                    print_section(
                        "🎯 Valid Clip",
                        f"Start: {start_time}s\nEnd: {end_time}s\nDuration: {duration}s\nContent: {clip.get('content', 'N/A')}",
                        "success"
                    )
                else:
                    console.print(f"[warning]Skipping clip (invalid duration: {duration}s)[/warning]")
                
                if len(valid_clips) == num_clips:
                    break
            except (KeyError, ValueError) as e:
                console.print(f"[warning]Skipping invalid clip: {e}[/warning]")
                continue
        
        if not valid_clips:
            console.print("[error]No valid clips found in input[/error]")
        return valid_clips
        
    except json.JSONDecodeError as e:
        console.print(f"[error]Invalid JSON format: {e}[/error]")
        return []

def get_multiline_input(prompt: str = "") -> str:
    """Get multi-line input from user until they enter a blank line"""
    console.print(prompt)
    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "":
                break
            lines.append(line)
        except EOFError:
            break
    return "\n".join(lines)

def getSegments(transcription: str | List[str], num_clips: int = 2) -> List[Tuple[int, int]]:
    """Prompt user for segment source choice and handle accordingly"""
    console.print("\n[bold cyan]🎬 Video Highlight Extractor[/bold cyan]")
    console.print("\nHow would you like to generate segments?")
    console.print("[1] Use AI (Ollama)")
    console.print("[2] Provide JSON manually")
    
    # Get reformatted transcript and time information upfront
    reformatted_transcript = reformat_transcript(transcription)

    time_matches = re.findall(r'\[(\d+)s\]', reformatted_transcript)
    valid_times = [int(t) for t in time_matches]

    
    if valid_times:
        min_time = min(valid_times)
        max_time = max(valid_times)
        video_length = max_time - min_time
    else:
        min_time = 0
        max_time = 0
        video_length = 0
        logger.warning("No valid timestamps found in transcript")
    
    while True:
        choice = console.input("\nEnter your choice (1 or 2): ").strip()
        
        if choice == "1":
            return get_highlight_via_ollama(transcription, num_clips=num_clips)
        elif choice == "2":
            example_format = {
                "segments": [
                    {
                        "segment start": "<start seconds as integer>",
                        "segment end": "<end seconds as integer>",
                        "content": "<Description of moment>",
                        "duration": "<segment end - segment start>"
                    }
                ] * num_clips
            }

            full_text = f"""VIDEO INFO:
- Length: {video_length} seconds
- Contains timestamps from {min_time}s to {max_time}s

REQUIREMENTS:
1. JSON must contain EXACTLY {num_clips} clips
2. Each segment must be between 15 and 60 seconds long
3. Clips should not overlap, or may overlap by at most 5 seconds

TRANSCRIPT:
{reformatted_transcript if reformatted_transcript.strip() else "No valid transcript content available"}

Please provide your JSON data in the below format.

EXPECTED JSON FORMAT:
{json.dumps(example_format, indent=2)}
"""

            print_section("Video Information and Requirements", full_text)
            
            try:
                pyperclip.copy(full_text)
                console.print("[success]✓ Info and requirements copied to clipboard[/success]")
            except Exception as e:
                console.print(f"[error]Failed to copy to clipboard: {e}[/error]")
            
            json_data = get_multiline_input("\nEnter your JSON data (press Enter twice when done):")
            return get_highlight_via_json(num_clips, json_data)
        else:
            console.print("[error]Invalid choice. Please enter 1 or 2.[/error]")