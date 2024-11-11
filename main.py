from Components.YoutubeDownloader import get_video_input
from Components.Edit import extract_audio, crop_video, generate_multiple_shorts
from Components.Transcription import transcribe_audio
from Components.LanguageTasks import get_highlight_via_json, get_highlight_via_ollama, getSegments
from Components.FaceCrop import crop_to_vertical
from Components.AddLogo import add_logo_to_video
from Components.EndScreen import add_endscreen
from Components.Captions import add_captions_to_video
from rich.console import Console
import os
import shutil
import threading
import re

console = Console()

def get_safe_filename(url):
    """Extract video title from URL and make it filename safe."""
    video_id = url.split('/')[-1]
    if 'watch?v=' in url:
        video_id = url.split('watch?v=')[-1].split('&')[0]
    
    safe_name = re.sub(r'[<>:"/\\|?*]', '', video_id)
    return safe_name

def main():
    output_dir = "shorts"
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs("shorts/cache", exist_ok=True)
    
    # Input Video
    Vid = get_video_input()
    video_name = get_safe_filename(Vid)

    if Vid:

        Vid = Vid.replace(".webm", ".mp4")
        console.log(f"[green]Downloaded video at[/green] {Vid}")

        Audio = extract_audio(Vid)
        if Audio:
            transcriptions = transcribe_audio(Audio)
            if transcriptions:
                TransText = ""
                for transcription in transcriptions:
                    if len(transcription) == 3:
                        text, start, end = transcription
                        TransText += f"{start} - {end}: {text}\n"
                    elif len(transcription) == 2:
                        text, start = transcription
                        TransText += f"{start}: {text}\n"
                    else:
                        console.log("[red]Unexpected transcription format[/red]")

                segments = getSegments(transcriptions, num_clips=1)
                
                if segments:
                    console.log(f"[blue]Creating shorts for segments:[/blue] {segments}")
                    video_name = video_name[:10]  # Get the first 10 characters of video_name
                    generate_multiple_shorts(Vid, segments, output_dir=output_dir, filename=video_name)
                    
                    for i, (start, end) in enumerate(segments):
                        initial_short = os.path.join(output_dir, f"{video_name}_{i+1}.mp4")
                        cropped_short = os.path.join(output_dir, f"{video_name}_cropped_{i+1}.mp4")
                        logoed_short = os.path.join(output_dir, f"{video_name}_logoed_{i+1}.mp4")
                        endscreen_short = os.path.join(output_dir, f"{video_name}_endscreen_{i+1}.mp4")
                        captioned_short = os.path.join(output_dir, f"{video_name}_captioned_{i+1}.mp4")
                        final_short = os.path.join(output_dir, f"{video_name}_short_{i+1}.mp4")
                        logo_path = "templates/logo/logo.png"

                        try:
                            with console.status(f"[cyan]Processing short {i+1}...[/cyan]"):
                                crop_to_vertical(initial_short, cropped_short)
                                if not os.path.exists(cropped_short):
                                    console.log(f"[red]Failed to crop short {i+1}[/red]")
                                    continue

                                add_logo_to_video(cropped_video_path=cropped_short,
                                                logo_path=logo_path,
                                                output_filename=logoed_short)
                                console.log(f"[green]Logo added to short {i+1}[/green]")
                                
                                endscreen_added = add_endscreen(video_path=logoed_short,
                                                            output_path=endscreen_short, 
                                                            max_duration=60.0)
                                if not endscreen_added:
                                    console.log(f"[yellow]Using video without endscreen for short {i+1}[/yellow]")
                                    shutil.copy2(logoed_short, endscreen_short)

                                caption_success = add_captions_to_video(input_path=endscreen_short,
                                                                    output_path=captioned_short)
                                
                                if caption_success:
                                    console.log(f"[green]Successfully added captions to short {i+1}[/green]")
                                    shutil.move(captioned_short, final_short)
                                    if os.path.exists(final_short) and os.path.getsize(final_short) > 0:
                                        console.log(f"[green]Final short {i+1} successfully created at {final_short}[/green]")
                                    else:
                                        console.log(f"[red]Failed to create final short {i+1}[/red]")

                                    
                                    # Cleanup
                                    for file in [initial_short, cropped_short, logoed_short, endscreen_short]:
                                        if os.path.exists(file):
                                            os.remove(file)
                                    
                                    if os.path.exists("temp"):
                                        shutil.rmtree("temp")
                                else:
                                    console.log(f"[yellow]Failed to add captions to short {i+1}, keeping uncaptioned version[/yellow]")
                                    os.replace(endscreen_short, final_short)

                        except Exception as e:
                            console.log(f"[red]Error processing short {i+1}: {str(e)}[/red]")
                            # Cleanup on error
                            for file in [initial_short, cropped_short, logoed_short, endscreen_short]:
                                if os.path.exists(file):
                                    os.remove(file)
                            
                            if os.path.exists("temp"):
                                shutil.rmtree("temp")
                            continue

                    console.log("[green]Processing complete:[/green] Final shorts are available in the output directory")
                else:
                    console.log("[yellow]No highlights found for creating shorts.[/yellow]")
            else:
                console.log("[red]Transcription returned no results.[/red]")
        else:
            console.log("[red]Failed to extract audio from the video.[/red]")
    else:
        console.log("[red]Failed to download the video.[/red]")

if __name__ == "__main__":
    main()
