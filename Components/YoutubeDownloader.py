import os
from pytubefix import YouTube
import ffmpeg
from rich.console import Console
from rich.progress import Progress
from rich.prompt import Prompt
import hashlib
from pathlib import Path
import logging
import json
from rich.table import Table
from typing import Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

console = Console()

class DownloadCache:
    def __init__(self, cache_dir="shorts/cache/yt_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
    def get_cache_key(self, url):
        """Generate a unique cache key based on the YouTube URL"""
        logger.info(f"Generating cache key for {url}")
        return hashlib.md5(url.encode()).hexdigest()
    
    def get_cached_download(self, cache_key):
        """Retrieve cached download info if it exists"""
        if not cache_key:
            logger.error("Invalid cache key")
            return None
            
        cache_file = self.cache_dir / f"{cache_key}_info.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    video_file = self.cache_dir / cache_data['filename']
                    if video_file.exists():
                        logger.info(f"Found cached video: {cache_data['title']}")
                        return str(video_file)
            except Exception as e:
                logger.error(f"Error reading cache file: {e}")
        
        return None

    def save_download_info(self, cache_key, title, filename, url=None):
        """Save download information to cache"""
        if not cache_key:
            logger.error("Cannot save: Invalid cache key")
            return False
            
        try:
            cache_data = {
                'title': title,
                'filename': filename,
                'url': url,
                'timestamp': os.path.getmtime(self.cache_dir / filename)
            }
            
            cache_file = self.cache_dir / f"{cache_key}_info.json"
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
            
            logger.info(f"Saved download info for: {title}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save download info: {e}")
            return False

    def list_cached_videos(self) -> list:
        """
        List all cached videos with their details.
        Returns a list of dictionaries containing video information.
        """
        cached_videos = []
        try:
            for file in self.cache_dir.glob("*_info.json"):
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        info = json.load(f)
                        video_file = self.cache_dir / info['filename']
                        if video_file.exists():
                            info['size'] = video_file.stat().st_size / (1024 * 1024)  # Size in MB
                            info['cache_key'] = file.stem.replace('_info', '')
                            cached_videos.append(info)
                except Exception as e:
                    logger.error(f"Error reading cache file {file}: {e}")
                    continue
                    
            # Sort by timestamp, most recent first
            cached_videos.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            return cached_videos
            
        except Exception as e:
            logger.error(f"Error listing cached videos: {e}")
            return []

def get_video_size(stream):
    """Calculate video size in MB."""
    return stream.filesize / (1024 * 1024)

def download_youtube_video(url):
    """
    Downloads a YouTube video, merging video and audio streams if needed.
    Implements caching to avoid re-downloading previously downloaded videos.

    Args:
    - url (str): URL of the YouTube video.

    Returns:
    - str: Path to the final video file.
    """
    try:
        # Initialize cache and check for existing download
        cache = DownloadCache()
        cache_key = cache.get_cache_key(url)
        
        if cached_file := cache.get_cached_download(cache_key):
            console.log(f"[green]Using cached video: {cached_file}[/green]")
            return cached_file

        yt = YouTube(url)
        video_streams = yt.streams.filter(type="video").order_by('resolution').desc()
        audio_stream = yt.streams.filter(only_audio=True).first()

        console.log("[cyan]Available video streams:[/cyan]")
        for i, stream in enumerate(video_streams):
            size = get_video_size(stream)
            stream_type = "Progressive" if stream.is_progressive else "Adaptive"
            console.log(f"[blue]{i}.[/blue] Resolution: {stream.resolution}, Size: {size:.2f} MB, Type: {stream_type}")

        choice = Prompt.ask("[bold yellow]Enter the number of the video stream to download[/bold yellow]", 
                          choices=[str(i) for i in range(len(video_streams))])
        selected_stream = video_streams[int(choice)]

        # Use cache directory for downloads
        output_dir = cache.cache_dir
        output_dir.mkdir(exist_ok=True)

        console.log(f"[green]Downloading video: {yt.title}[/green]")
        with Progress(console=console) as progress:
            download_task = progress.add_task("[cyan]Downloading video stream...", total=100)
            video_file = selected_stream.download(
                output_path=str(output_dir),
                filename_prefix=f"{cache_key}_video_"
            )
            progress.update(download_task, completed=100)

        final_filename = f"{cache_key}_{yt.title}.mp4"
        output_file = str(output_dir / final_filename)

        # Handle separate audio download and merge if needed
        if not selected_stream.is_progressive:
            console.log("[yellow]Downloading audio...[/yellow]")
            audio_file = audio_stream.download(
                output_path=str(output_dir),
                filename_prefix=f"{cache_key}_audio_"
            )

            console.log("[yellow]Merging video and audio...[/yellow]")
            stream = ffmpeg.input(video_file)
            audio = ffmpeg.input(audio_file)
            merged_stream = ffmpeg.output(
                stream, audio, output_file,
                vcodec='libx264',
                acodec='aac',
                strict='experimental'
            )
            ffmpeg.run(merged_stream, overwrite_output=True)

            # Cleanup temporary files
            os.remove(video_file)
            os.remove(audio_file)
        else:
            # For progressive streams, just rename the file
            os.rename(video_file, output_file)

        # Save download info to cache
        cache.save_download_info(cache_key, yt.title, final_filename, url)

        console.log(f"[green]Downloaded: {yt.title}[/green]")
        console.log(f"[blue]File path:[/blue] {output_file}")
        return output_file

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)
        console.log(f"[red]An error occurred: {str(e)}[/red]")
        console.log("[red]Please make sure you have the latest version of pytube and ffmpeg-python installed.[/red]")
        console.log("You can update them by running:")
        console.print("[bold green]pip install --upgrade pytube ffmpeg-python[/bold green]")
        console.log("[red]Also, ensure that ffmpeg is installed on your system and available in your PATH.[/red]")
        return None

def get_video_input() -> Optional[str]:
    """
    Display cached videos and allow user to either select one or input a URL.
    Returns the selected video path or downloads a new video.
    """
    cache = DownloadCache()
    cached_videos = cache.list_cached_videos()
    
    # Create table of cached videos
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim")
    table.add_column("Title")
    table.add_column("Size (MB)")
    table.add_column("URL", style="dim")
    
    # Add cached videos to table
    for idx, video in enumerate(cached_videos, 1):
        table.add_row(
            str(idx),
            video['title'],
            f"{video.get('size', 0):.1f}",
            video.get('url', 'N/A')
        )
    
    console.print("\n[cyan]Cached Videos (enter number to select) or paste URL for new download:[/cyan]")
    console.print(table)
    
    # Get user input
    response = Prompt.ask("\n[yellow]Enter selection number or paste URL[/yellow]")
    
    # Check if input is a number (selecting from cache)
    try:
        idx = int(response)
        if 1 <= idx <= len(cached_videos):
            selected = cached_videos[idx - 1]
            video_path = cache.cache_dir / selected['filename']
            console.print(f"[green]Using cached video: {selected['title']}[/green]")
            return str(video_path)
    except ValueError:
        # Input is not a number, treat it as URL
        if response.startswith(('http://', 'https://', 'www.')):
            return download_youtube_video(response)
        else:
            console.print("[red]Invalid input. Please enter a number or valid URL.[/red]")
            return get_video_input()  # Recursively try again
            
    console.print("[red]Invalid selection number.[/red]")
    return get_video_input()  # Recursively try again

if __name__ == "__main__":
    Vid = get_video_input()
    if Vid:
        console.print(f"[green]Video ready at: {Vid}[/green]")
    else:
        console.print("[red]Failed to get video.[/red]")