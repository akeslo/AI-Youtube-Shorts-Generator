import psutil
import time
import threading
from datetime import datetime, timedelta
import platform
import os
from rich.console import Console
from rich.progress import Progress
from rich import print

console = Console()

try:
    import GPUtil
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False
try:
    import nvidia_smi
    NVIDIA_SMI_AVAILABLE = True
except ImportError:
    NVIDIA_SMI_AVAILABLE = False

def get_color_for_usage(usage):
    if usage < 30:
        return "[green]"
    elif usage < 70:
        return "[yellow]"
    else:
        return "[red]"

def format_timedelta(td):
    hours = td.seconds // 3600
    minutes = (td.seconds % 3600) // 60
    seconds = td.seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def monitor_resources(process_name="ollama_llama_server"):
    last_status = False  # Track if process was found in last iteration
    while True:
        try:
            process_found = False
            for proc in psutil.process_iter(['name', 'cpu_percent', 'create_time']):
                if proc.info['name'] == process_name:
                    process_found = True
                    cpu_usage = proc.cpu_percent(interval=1)
                    memory_info = proc.memory_info()
                    memory_usage_mb = memory_info.rss / 1024 / 1024
                    memory_percent = proc.memory_percent()
                    process_start_time = datetime.fromtimestamp(proc.create_time())
                    runtime = datetime.now() - process_start_time
                    
                    console.print(
                        f"[bold cyan]*Ollama AI Monitor:*[/bold cyan] "
                        f"CPU: {get_color_for_usage(cpu_usage)}{cpu_usage:.1f}%[/] | "
                        f"Memory: {get_color_for_usage(memory_percent)}{memory_usage_mb:.0f}MB[/] | "
                        f"Runtime: [cyan]{format_timedelta(runtime)}[/]", 
                        end='\r', style="bold"
                    )

                    last_status = True
                    break
            
            if not process_found and last_status:
                # Clear the line if process not found but was running before
                console.print(" " * 100, end='\r', flush=True)
                last_status = False
            
            time.sleep(2)
        except Exception as e:
            if last_status:
                console.print(" " * 100, end='\r', flush=True)
                last_status = False
            time.sleep(2)

def start_monitoring(process_name="ollama_llama_server"):
    """Start the resource monitoring in a separate thread."""
    monitor_thread = threading.Thread(target=monitor_resources, args=(process_name,), daemon=True)
    monitor_thread.start()
    return monitor_thread

if __name__ == "__main__":
    try:
        monitor_thread = start_monitoring()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoring stopped by user.[/yellow]")
