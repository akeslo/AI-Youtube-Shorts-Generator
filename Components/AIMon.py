import psutil
import time
import threading

def monitor_cpu_usage(process_name="ollama_llama_server"):
    """Periodically prints CPU usage of a specific process by name."""
    while True:
        # Find process by name
        process_found = False
        for proc in psutil.process_iter(['name', 'cpu_percent']):
            if proc.info['name'] == process_name:
                process_found = True
                cpu_usage = proc.cpu_percent(interval=1)  # Get CPU usage over 1 second
                print(f"AI Monitor: Ollama: CPU usage of {process_name}: {cpu_usage}%")
                break
        
        if not process_found:
            print(f"AI Monitor: Ollama Process {process_name} not found.")
        
        time.sleep(5)  # Update every 5 seconds
